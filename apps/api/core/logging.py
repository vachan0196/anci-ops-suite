import contextvars
import logging

from apps.api.core.settings import settings

request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get()
        return True


def configure_logging() -> None:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [request_id=%(request_id)s] %(name)s: %(message)s"
        )
    )
    handler.addFilter(RequestIdFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
