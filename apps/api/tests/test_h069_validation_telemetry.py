import copy
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.exceptions import RequestValidationError

from apps.api.core import observability


PIPELINE_SCRIPT = r'''
import json
import os
from pathlib import Path

from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
import sentry_sdk
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.transport import Transport

from apps.api.core import observability
from apps.api.main import app


class CapturingTransport(Transport):
    def __init__(self):
        super().__init__({})
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope.serialize().decode("utf-8", errors="replace"))


sdk_client = sentry_sdk.get_client()
transport = CapturingTransport()
sdk_client.transport = transport
entry_events = []
returned_events = []
production_before_send = observability._before_send


def recording_before_send(event, hint):
    entry_events.append(json.dumps(copy_event(event), sort_keys=True, default=str))
    returned = production_before_send(event, hint)
    returned_events.append(json.dumps(returned, sort_keys=True, default=str))
    return returned


def copy_event(event):
    return json.loads(json.dumps(event, default=str))


sdk_client.options["before_send"] = recording_before_send
if os.environ["H069_CAPTURE_MODE"] == "forced":
    integration = sdk_client.get_integration(StarletteIntegration)
    integration.failed_request_status_codes = {422}
    RequestValidationError.status_code = 422

marker = os.environ["H069_MARKER"]
response = TestClient(app).post(
    "/api/v1/auth/refresh",
    json={"portal": "admin", "refresh_token": marker},
)
sentry_sdk.flush(timeout=2)
Path(os.environ["H069_RESULT_PATH"]).write_text(json.dumps({
    "status": response.status_code,
    "response": response.text,
    "entry_events": entry_events,
    "returned_events": returned_events,
    "envelopes": transport.envelopes,
}))
'''


def _run_pipeline(tmp_path: Path, mode: str) -> tuple[str, dict]:
    marker = f"h069-sentry-{mode}-{os.urandom(16).hex()}"
    result_path = tmp_path / f"{mode}.json"
    environment = {
        **os.environ,
        "ENV": "test",
        "EMAIL_BACKEND": "test_capture",
        "RATE_LIMIT_ENABLED": "false",
        "SENTRY_DSN": "https://public@example.invalid/1",
        "H069_CAPTURE_MODE": mode,
        "H069_MARKER": marker,
        "H069_RESULT_PATH": str(result_path),
        "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
    }
    completed = subprocess.run(
        [sys.executable, "-c", PIPELINE_SCRIPT],
        cwd=Path(__file__).resolve().parents[3],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    return marker, json.loads(result_path.read_text())


def test_production_sentry_configuration_does_not_capture_validation_error(tmp_path) -> None:
    marker, result = _run_pipeline(tmp_path, "production")

    assert result["status"] == 422
    assert marker not in result["response"]
    assert result["entry_events"] == []
    assert result["returned_events"] == []
    assert result["envelopes"] == []


def test_forced_real_sentry_pipeline_strips_credential_exception_value(tmp_path) -> None:
    marker, result = _run_pipeline(tmp_path, "forced")

    assert result["status"] == 422
    assert marker not in result["response"]
    assert len(result["entry_events"]) == 1
    assert marker in result["entry_events"][0]
    assert marker not in result["returned_events"][0]
    assert len(result["envelopes"]) == 1
    assert marker not in result["envelopes"][0]


def _validation_error(field: str, value: str) -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "extra_forbidden",
                "loc": ("body", field),
                "msg": "Extra inputs are not permitted",
                "input": value,
            }
        ],
        body={field: value},
    )


def test_before_send_scopes_exception_value_strip_to_refresh_validation() -> None:
    marker = f"h069-pure-{os.urandom(16).hex()}"
    subject_event = {
        "exception": {"values": [{"type": "RequestValidationError", "value": marker}]}
    }
    control_event = copy.deepcopy(subject_event)

    subject = observability._before_send(
        subject_event,
        {"exc_info": (RequestValidationError, _validation_error("refresh_token", marker), None)},
    )
    control = observability._before_send(
        control_event,
        {"exc_info": (RequestValidationError, _validation_error("portal", marker), None)},
    )

    assert "value" not in subject["exception"]["values"][0]
    assert control["exception"]["values"][0]["value"] == marker
