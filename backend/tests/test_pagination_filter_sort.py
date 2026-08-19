import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.utils import utc_now, encode_cursor, decode_cursor
from app.services.todo_service import TodoService

USER_A_ID = "507f1f77bcf86cd799439011"
USER_A_EMAIL = "user_a@gmail.com"

USER_B_ID = "507f1f77bcf86cd799439022"
USER_B_EMAIL = "user_b@gmail.com"

def create_mock_todo(id_str, user_id, title, status="pending", created_at=None, deadline=None):
    now = utc_now()
    return {
        "_id": ObjectId(id_str),
        "user_id": user_id,
        "title": title,
        "description": f"Desc for {title}",
        "status": status,
        "deadline": deadline,
        "created_at": created_at or now,
        "updated_at": now,
        "reminded": False
    }

def test_encode_decode_cursor_valid_and_invalid():
    dt = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    doc_id = "507f1f77bcf86cd799439011"
    
    encoded = encode_cursor(dt, doc_id)
    assert isinstance(encoded, str)
    
    decoded_v, decoded_id = decode_cursor(encoded)
    assert decoded_v == dt
    assert decoded_id == doc_id
    
    # Test invalid cursor inputs raise ValueError
    with pytest.raises(ValueError):
        decode_cursor("invalid_base64!!!")
        
    with pytest.raises(ValueError):
        decode_cursor("")

def test_get_todos_invalid_query_parameters_return_400():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"id": USER_A_ID, "email": USER_A_EMAIL}

    try:
        client = TestClient(app)

        # Invalid limit < 1
        res = client.get("/api/todos?limit=0")
        assert res.status_code == 400
        assert "limit" in res.json()["detail"].lower()

        # Invalid limit > 100
        res = client.get("/api/todos?limit=101")
        assert res.status_code == 400

        # Invalid status filter
        res = client.get("/api/todos?status=invalid_status")
        assert res.status_code == 400

        # Invalid sort allowlist
        res = client.get("/api/todos?sort=invalid_column")
        assert res.status_code == 400

        # Invalid order
        res = client.get("/api/todos?order=sideways")
        assert res.status_code == 400

        # Invalid cursor
        res = client.get("/api/todos?cursor=bad_cursor_token")
        assert res.status_code == 400
        assert res.json()["detail"] == "Cursor không hợp lệ"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_user_todos_multi_page_pagination():
    t1 = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 2, 10, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 3, 10, 0, 0, tzinfo=timezone.utc)

    doc3 = create_mock_todo("507f1f77bcf86cd799439003", USER_A_ID, "Todo 3", created_at=t3)
    doc2 = create_mock_todo("507f1f77bcf86cd799439002", USER_A_ID, "Todo 2", created_at=t2)
    doc1 = create_mock_todo("507f1f77bcf86cd799439001", USER_A_ID, "Todo 1", created_at=t1)

    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    
    # Page 1 fetch with limit=2 (returns 3 docs, meaning next page exists)
    mock_cursor.to_list = AsyncMock(return_value=[doc3, doc2, doc1])
    mock_db.todos.find = MagicMock(return_value=mock_cursor)

    res_page1 = await TodoService.get_user_todos(mock_db, USER_A_ID, limit=2)
    assert len(res_page1["items"]) == 2
    assert res_page1["items"][0]["id"] == "507f1f77bcf86cd799439003"
    assert res_page1["items"][1]["id"] == "507f1f77bcf86cd799439002"
    assert res_page1["next_cursor"] is not None

    # Page 2 fetch with cursor (returns 1 doc, no next page)
    mock_cursor.to_list = AsyncMock(return_value=[doc1])
    cursor_token = res_page1["next_cursor"]

    res_page2 = await TodoService.get_user_todos(mock_db, USER_A_ID, limit=2, cursor=cursor_token)
    assert len(res_page2["items"]) == 1
    assert res_page2["items"][0]["id"] == "507f1f77bcf86cd799439001"
    assert res_page2["next_cursor"] is None

@pytest.mark.asyncio
async def test_get_user_todos_status_filter_and_sort_construction():
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_db.todos.find = MagicMock(return_value=mock_cursor)

    await TodoService.get_user_todos(
        mock_db,
        USER_A_ID,
        limit=5,
        status_filter="completed",
        sort="deadline",
        order="asc"
    )

    find_call_query = mock_db.todos.find.call_args[0][0]
    sort_call_spec = mock_cursor.sort.call_args[0][0]

    assert find_call_query["user_id"] == USER_A_ID
    assert find_call_query["status"] == "completed"
    assert sort_call_spec == [("deadline", 1), ("_id", 1)]

@pytest.mark.asyncio
async def test_get_user_todos_always_scopes_by_authenticated_user_id():
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_db.todos.find = MagicMock(return_value=mock_cursor)

    await TodoService.get_user_todos(mock_db, USER_A_ID)

    find_query = mock_db.todos.find.call_args[0][0]
    assert find_query["user_id"] == USER_A_ID

def test_get_chat_history_paginated_and_old_to_new_order():
    t1 = datetime(2026, 8, 19, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 19, 10, 1, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 19, 10, 2, 0, tzinfo=timezone.utc)

    msg3 = {"_id": ObjectId("507f1f77bcf86cd799439003"), "user_id": USER_A_ID, "sender": "assistant", "content": "Reply 2", "timestamp": t3}
    msg2 = {"_id": ObjectId("507f1f77bcf86cd799439002"), "user_id": USER_A_ID, "sender": "user", "content": "Question 2", "timestamp": t2}
    msg1 = {"_id": ObjectId("507f1f77bcf86cd799439001"), "user_id": USER_A_ID, "sender": "user", "content": "Question 1", "timestamp": t1}

    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    
    # DB find returning in desc order: [msg3, msg2, msg1]
    mock_cursor.to_list = AsyncMock(return_value=[msg3, msg2, msg1])
    mock_db.chat_messages.find = MagicMock(return_value=mock_cursor)

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"id": USER_A_ID, "email": USER_A_EMAIL}

    try:
        client = TestClient(app)
        res = client.get("/api/chat/history?limit=2")

        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "next_cursor" in data
        assert len(data["items"]) == 2
        # Verify old-to-new chronological ordering within page
        assert data["items"][0]["content"] == "Question 2"
        assert data["items"][1]["content"] == "Reply 2"
        assert data["next_cursor"] is not None

        # Test invalid chat cursor returns HTTP 400
        bad_res = client.get("/api/chat/history?cursor=invalid_cursor")
        assert bad_res.status_code == 400
        assert bad_res.json()["detail"] == "Cursor không hợp lệ"
    finally:
        app.dependency_overrides.clear()
