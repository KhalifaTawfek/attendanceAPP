from datetime import UTC, datetime


def as_utc(dt: datetime) -> datetime:
    """Normalise a datetime to aware UTC (SQLite returns naive values)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)
