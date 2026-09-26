"""Business ID generation — 总纲 §4.1.

Format (总纲 §4.1.2)::

    <前缀>_<yyyymmdd>_<6位十进制序号>
    req_20260925_000001

The prefix list is a **closed set** (总纲 §4.1.3): only the 14 prefixes in
:data:`app.core.constants.ID_PREFIXES` are accepted.

The date component is the **UTC** calendar day, consistent with 总纲 §4.5.1
("存储：UTC") — an ID minted at 2026-09-25T23:30+08:00 carries ``20260925``
because that instant is 2026-09-25T15:30Z.

Sequences are process-local, reset per ``(prefix, day)`` and guarded by a lock.
The counter is not persisted; a restart re-uses numbers already present in the
database, so uniqueness ultimately rests on the ``UNIQUE`` constraint of the
business-ID column (e.g. ``tasks.task_id``). Callers that must be crash-safe
should retry on ``IntegrityError``.
"""

import re
import threading
from datetime import date, datetime, timezone

from app.core.constants import ID_PREFIX_VALUES

__all__ = [
    "new_id",
    "parse_id",
    "is_valid_id",
    "reset_counters",
    "ID_PATTERN",
    "MAX_SEQUENCE",
]

#: ``<prefix>_<yyyymmdd>_<6 digits>`` — 总纲 §4.1.2.
ID_PATTERN = re.compile(r"^(?P<prefix>[a-z][a-z0-9]*_)(?P<day>\d{8})_(?P<seq>\d{6})$")

MAX_SEQUENCE = 999_999

_LOCK = threading.Lock()
_COUNTERS: dict[tuple[str, str], int] = {}


def _normalize_prefix(prefix: str) -> str:
    """Lower-case the prefix, append ``_`` when missing and validate the closed set."""
    if not isinstance(prefix, str) or not prefix.strip():
        raise ValueError("prefix must be a non-empty string")
    normalized = prefix.strip().lower()
    if not normalized.endswith("_"):
        normalized += "_"
    if normalized not in ID_PREFIX_VALUES:
        raise ValueError(
            f"unknown ID prefix {normalized!r}; 总纲 §4.1.3 defines the closed set "
            f"{ID_PREFIX_VALUES}"
        )
    return normalized


def _utc_day(when: datetime | None) -> str:
    """Return the ``yyyymmdd`` UTC day component for ``when`` (default: now)."""
    if when is None:
        moment = datetime.now(timezone.utc)
    elif when.tzinfo is None:
        moment = when.replace(tzinfo=timezone.utc)
    else:
        moment = when.astimezone(timezone.utc)
    return moment.strftime("%Y%m%d")


def new_id(prefix: str, when: datetime | None = None) -> str:
    """Mint a new business ID such as ``task_20260925_000001``.

    :param prefix: one of the 总纲 §4.1.3 prefixes, with or without the ``_``.
    :param when: instant used for the date component (UTC); defaults to now.
    :raises ValueError: the prefix is not part of the closed set.
    :raises OverflowError: more than 999999 IDs were minted for this prefix/day.
    """
    normalized = _normalize_prefix(prefix)
    day = _utc_day(when)
    key = (normalized, day)
    with _LOCK:
        sequence = _COUNTERS.get(key, 0) + 1
        if sequence > MAX_SEQUENCE:
            raise OverflowError(
                f"sequence exhausted for prefix {normalized!r} on {day} "
                f"(max {MAX_SEQUENCE})"
            )
        _COUNTERS[key] = sequence
    return f"{normalized}{day}_{sequence:06d}"


def parse_id(value: str) -> tuple[str, date, int]:
    """Split a business ID into ``(prefix, date, sequence)``.

    The returned prefix keeps its trailing underscore so it can be fed straight
    back into :func:`new_id` / :func:`is_valid_id`.

    :raises ValueError: ``value`` is not a well-formed business ID.
    """
    match = ID_PATTERN.match(value or "")
    if match is None:
        raise ValueError(
            f"{value!r} is not a StructAI business ID "
            "(expected <prefix>_<yyyymmdd>_<6 digits>, 总纲 §4.1.2)"
        )
    try:
        parsed_day = datetime.strptime(match.group("day"), "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"{value!r} carries an invalid date component") from exc
    return match.group("prefix"), parsed_day, int(match.group("seq"))


def is_valid_id(value: str, prefix: str | None = None) -> bool:
    """Validate a business ID, optionally requiring a specific prefix.

    A valid ID must match 总纲 §4.1.2 *and* use a prefix from the closed set of
    总纲 §4.1.3. When ``prefix`` is given it is normalized (``"task"`` and
    ``"task_"`` are equivalent) and compared exactly.
    """
    if not isinstance(value, str):
        return False
    match = ID_PATTERN.match(value)
    if match is None:
        return False
    if match.group("prefix") not in ID_PREFIX_VALUES:
        return False
    try:
        datetime.strptime(match.group("day"), "%Y%m%d")
    except ValueError:
        return False
    if prefix is None:
        return True
    try:
        return match.group("prefix") == _normalize_prefix(prefix)
    except ValueError:
        return False


def reset_counters() -> None:
    """Clear all in-process sequence counters (test helper)."""
    with _LOCK:
        _COUNTERS.clear()
