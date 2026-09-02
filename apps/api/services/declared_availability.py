"""Evaluate declared availability using site-local wall-clock time.

Shift timestamps carry a UTC label as storage notation, while availability values are
bare ``TIME`` values. They are compared as site-local wall-clock values without timezone
conversion. See D054 for the convention and its exit condition.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from enum import Enum
import hashlib
import struct
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.models.availability_entry import AvailabilityEntry
from apps.api.models.shift import Shift


HARD_POSITIVE_TYPES = frozenset({"available", "available_extra"})
HARD_NEGATIVE_TYPE = "unavailable"
SOFT_TYPE = "preferred_off"


class AvailabilityExclusionCause(str, Enum):
    UNAVAILABLE = "unavailable"
    NO_DECLARATION = "no_declaration"
    SOURCE_CONFLICT = "source_conflict"
    SAME_SOURCE_CONFLICT = "same_source_conflict"
    UNKNOWN_PROVENANCE = "unknown_provenance"


@dataclass(frozen=True)
class DeclaredAvailabilityResult:
    eligible: bool
    preferred_off: bool
    exclusion_cause: AvailabilityExclusionCause | None
    would_be_eligible_without_source_conflict: bool = False


@dataclass(frozen=True)
class _Interval:
    start: datetime
    end: datetime


def _as_site_local_label(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _entry_interval(entry: AvailabilityEntry) -> _Interval | None:
    day_start = datetime.combine(entry.date, time.min, tzinfo=timezone.utc)
    if entry.start_time is None and entry.end_time is None:
        return _Interval(day_start, day_start + timedelta(days=1))
    if entry.start_time is None or entry.end_time is None:
        return None
    end_date = (
        entry.date + timedelta(days=1)
        if entry.end_time < entry.start_time
        else entry.date
    )
    return _Interval(
        datetime.combine(entry.date, entry.start_time, tzinfo=timezone.utc),
        datetime.combine(end_date, entry.end_time, tzinfo=timezone.utc),
    )


def intervals_overlap(
    first_start: datetime,
    first_end: datetime,
    second_start: datetime,
    second_end: datetime,
) -> bool:
    """Return whether two half-open intervals overlap."""
    return first_start < second_end and second_start < first_end


def availability_entries_overlap(
    first: AvailabilityEntry,
    second: AvailabilityEntry,
) -> bool:
    first_interval = _entry_interval(first)
    second_interval = _entry_interval(second)
    if first_interval is None or second_interval is None:
        return False
    return intervals_overlap(
        first_interval.start,
        first_interval.end,
        second_interval.start,
        second_interval.end,
    )


def has_hard_contradiction(entries: list[AvailabilityEntry]) -> bool:
    positives = [entry for entry in entries if entry.type in HARD_POSITIVE_TYPES]
    negatives = [entry for entry in entries if entry.type == HARD_NEGATIVE_TYPE]
    return any(
        availability_entries_overlap(positive, negative)
        for positive in positives
        for negative in negatives
    )


def _contradiction_intersects_shift(
    positive: AvailabilityEntry,
    negative: AvailabilityEntry,
    shift_interval: _Interval,
) -> bool:
    positive_interval = _entry_interval(positive)
    negative_interval = _entry_interval(negative)
    if positive_interval is None or negative_interval is None:
        return False
    intersection_start = max(positive_interval.start, negative_interval.start)
    intersection_end = min(positive_interval.end, negative_interval.end)
    return intervals_overlap(
        intersection_start,
        intersection_end,
        shift_interval.start,
        shift_interval.end,
    )


def evaluate_declared_availability(
    entries: list[AvailabilityEntry],
    shift: Shift,
) -> DeclaredAvailabilityResult:
    shift_start = _as_site_local_label(shift.start_at)
    shift_end = _as_site_local_label(shift.end_at)
    shift_date = shift_start.date()

    relevant_entries = [
        entry
        for entry in entries
        if shift_date - timedelta(days=1) <= entry.date <= shift_end.date()
    ]
    shift_interval = _Interval(shift_start, shift_end)
    applicable_positives: list[AvailabilityEntry] = []
    overlapping_negatives: list[AvailabilityEntry] = []
    preferred_off = False

    for entry in relevant_entries:
        interval = _entry_interval(entry)
        if interval is None:
            continue
        if entry.type in HARD_POSITIVE_TYPES:
            if interval.start <= shift_start and interval.end >= shift_end:
                applicable_positives.append(entry)
        elif entry.type == HARD_NEGATIVE_TYPE:
            if intervals_overlap(interval.start, interval.end, shift_start, shift_end):
                overlapping_negatives.append(entry)
        elif entry.type == SOFT_TYPE:
            if intervals_overlap(interval.start, interval.end, shift_start, shift_end):
                preferred_off = True

    all_positives = [entry for entry in relevant_entries if entry.type in HARD_POSITIVE_TYPES]
    conflicting_negative_ids: set[int] = set()
    has_cross_source_conflict = False
    has_same_source_conflict = False
    has_unknown_provenance_conflict = False

    for positive in all_positives:
        for negative in overlapping_negatives:
            if not _contradiction_intersects_shift(positive, negative, shift_interval):
                continue
            if positive.source is None or negative.source is None:
                has_unknown_provenance_conflict = True
            elif positive.source == negative.source:
                has_same_source_conflict = True
            else:
                has_cross_source_conflict = True
                conflicting_negative_ids.add(id(negative))

    if has_unknown_provenance_conflict:
        return DeclaredAvailabilityResult(
            eligible=False,
            preferred_off=preferred_off,
            exclusion_cause=AvailabilityExclusionCause.UNKNOWN_PROVENANCE,
        )
    if has_same_source_conflict:
        return DeclaredAvailabilityResult(
            eligible=False,
            preferred_off=preferred_off,
            exclusion_cause=AvailabilityExclusionCause.SAME_SOURCE_CONFLICT,
        )
    if has_cross_source_conflict:
        independent_negative = any(
            id(entry) not in conflicting_negative_ids for entry in overlapping_negatives
        )
        return DeclaredAvailabilityResult(
            eligible=False,
            preferred_off=preferred_off,
            exclusion_cause=AvailabilityExclusionCause.SOURCE_CONFLICT,
            would_be_eligible_without_source_conflict=bool(applicable_positives)
            and not independent_negative,
        )
    if overlapping_negatives:
        return DeclaredAvailabilityResult(
            eligible=False,
            preferred_off=preferred_off,
            exclusion_cause=AvailabilityExclusionCause.UNAVAILABLE,
        )
    if not applicable_positives:
        return DeclaredAvailabilityResult(
            eligible=False,
            preferred_off=preferred_off,
            exclusion_cause=AvailabilityExclusionCause.NO_DECLARATION,
        )
    return DeclaredAvailabilityResult(
        eligible=True,
        preferred_off=preferred_off,
        exclusion_cause=None,
    )


def acquire_availability_write_lock(
    db: Session,
    *,
    writer_identity: str,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Serialize an availability writer/subject key for this transaction.

    PostgreSQL uses the repository's deterministic transaction-scoped advisory-lock
    pattern. SQLite has no equivalent and is intentionally a no-op; PostgreSQL-backed
    coverage is required for concurrency evidence.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    lock_material = f"availability:{writer_identity}:{tenant_id}:{user_id}".encode()
    lock_key_1, lock_key_2 = struct.unpack(">ii", hashlib.sha256(lock_material).digest()[:8])
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key_1, :lock_key_2)"),
        {"lock_key_1": lock_key_1, "lock_key_2": lock_key_2},
    )
