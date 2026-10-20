"""Expand a recurrence rule into occurrence start times.

Occurrences are computed in the series' IANA timezone so a weekly 09:00 meeting stays at
09:00 local time across DST changes, then converted back to UTC.
"""
import calendar
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models import Frequency
from app.timeutil import as_utc

MAX_OCCURRENCES = 200


def get_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown timezone: {name}")


def _add_months(d: datetime, months: int) -> datetime | None:
    """Same day-of-month `months` later, or None when that day doesn't exist (e.g. 31 Feb)."""
    m = d.month - 1 + months
    year, month = d.year + m // 12, m % 12 + 1
    if d.day > calendar.monthrange(year, month)[1]:
        return None
    return d.replace(year=year, month=month)


def _candidates(first: datetime, frequency: Frequency, interval: int, weekdays: list[int]) -> Iterator[datetime]:
    if frequency == Frequency.daily:
        i = 0
        while True:
            yield first + timedelta(days=i * interval)
            i += 1
    elif frequency == Frequency.weekly:
        days = sorted(set(weekdays or [first.weekday()]))
        week_start = first - timedelta(days=first.weekday())
        w = 0
        while True:
            for wd in days:
                d = week_start + timedelta(weeks=w * interval, days=wd)
                if d >= first:
                    yield d
            w += 1
    else:
        i = 0
        while True:
            d = _add_months(first, i * interval)
            if d is not None:
                yield d
            i += 1
            if i > MAX_OCCURRENCES * 12:  # safety net for rules that rarely match
                return


def expand(
    starts_at: datetime,
    *,
    frequency: Frequency,
    interval: int = 1,
    weekdays: list[int] | None = None,
    until: date | None = None,
    count: int | None = None,
    timezone: str = "UTC",
) -> list[datetime]:
    """Return UTC start datetimes of every occurrence (the first one included)."""
    if until is None and count is None:
        raise ValueError("Recurrence needs an end: 'until' or 'count'")
    zone = get_zone(timezone)
    # Work on naive local wall-clock time, then attach the zone per occurrence.
    local_first = as_utc(starts_at).astimezone(zone).replace(tzinfo=None)
    limit = min(count or MAX_OCCURRENCES, MAX_OCCURRENCES)

    out: list[datetime] = []
    for local in _candidates(local_first, frequency, interval, weekdays or []):
        if until is not None and local.date() > until:
            break
        out.append(as_utc(local.replace(tzinfo=zone)))
        if len(out) >= limit:
            break
    return out
