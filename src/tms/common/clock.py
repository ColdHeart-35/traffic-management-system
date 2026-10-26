"""Single source of time for the whole system (naive UTC datetimes).

Live code calls ``clock.now()``. Tests can ``freeze`` and ``advance`` the clock so
signal timing is deterministic and a one-hour simulation does not take an hour.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

_fixed: datetime | None = None


def _real_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now() -> datetime:
    return _fixed if _fixed is not None else _real_now()


def freeze(at: datetime | None = None) -> datetime:
    global _fixed
    _fixed = at if at is not None else _real_now()
    return _fixed


def advance(seconds: float) -> datetime:
    global _fixed
    if _fixed is None:
        _fixed = _real_now()
    _fixed = _fixed + timedelta(seconds=seconds)
    return _fixed


def unfreeze() -> None:
    global _fixed
    _fixed = None


def is_frozen() -> bool:
    return _fixed is not None


def to_naive_utc(value: datetime) -> datetime:
    """Convert any datetime to naive UTC (what the database stores)."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value
