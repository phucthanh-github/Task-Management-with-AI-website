from datetime import datetime, timezone
from typing import Optional

def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

def make_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Converts a datetime object to timezone-aware UTC.
    - If dt is None: returns None
    - If dt is offset-naive: attaches timezone.utc
    - If dt is offset-aware: converts to timezone.utc (astimezone)
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
