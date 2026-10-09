from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a naive datetime for DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
