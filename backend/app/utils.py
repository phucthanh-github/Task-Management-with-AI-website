from datetime import datetime, timezone
from typing import Optional, Tuple, Any
import base64
import json
from bson import ObjectId

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

def encode_cursor(val: Any, doc_id: str) -> str:
    """
    Encodes sort value `val` and document ID `doc_id` into a URL-safe base64 string.
    """
    if isinstance(val, datetime):
        val_str = make_utc(val).isoformat()
    else:
        val_str = val
        
    payload = {"v": val_str, "id": str(doc_id)}
    dumped = json.dumps(payload)
    return base64.urlsafe_b64encode(dumped.encode("utf-8")).decode("utf-8")

def decode_cursor(cursor_str: str) -> Tuple[Optional[Any], str]:
    """
    Decodes a base64 cursor string into (sort_val, doc_id).
    Raises ValueError if cursor string is malformed or contains invalid data.
    """
    if not cursor_str or not isinstance(cursor_str, str):
        raise ValueError("Cursor không hợp lệ")
    try:
        decoded_bytes = base64.urlsafe_b64decode(cursor_str.encode("utf-8"))
        payload = json.loads(decoded_bytes.decode("utf-8"))
        if not isinstance(payload, dict) or "id" not in payload or "v" not in payload:
            raise ValueError("Cursor không hợp lệ")
            
        doc_id = str(payload["id"])
        if not ObjectId.is_valid(doc_id):
            raise ValueError("Cursor không hợp lệ")
            
        raw_v = payload["v"]
        if raw_v is None:
            sort_val = None
        elif isinstance(raw_v, str):
            try:
                dt = datetime.fromisoformat(raw_v)
                sort_val = make_utc(dt)
            except Exception:
                sort_val = raw_v
        else:
            sort_val = raw_v
            
        return sort_val, doc_id
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError("Cursor không hợp lệ") from e

