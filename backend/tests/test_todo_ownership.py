import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from datetime import datetime
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.services.todo_service import TodoService

USER_A_ID = "507f1f77bcf86cd799439011"
USER_A_EMAIL = "user_a@gmail.com"

USER_B_ID = "507f1f77bcf86cd799439022"
USER_B_EMAIL = "user_b@gmail.com"

TODO_B_ID = "507f1f77bcf86cd799439033"

@pytest.fixture
def mock_db_with_ownership():
    db = MagicMock()
    
    # User B's Todo doc
    todo_b_doc = {
        "_id": ObjectId(TODO_B_ID),
        "user_id": USER_B_ID,
        "title": "User B Todo",
        "description": "Private todo of User B",
        "status": "pending",
        "deadline": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "reminded": False
    }

    # Query routing based on user_id
    async def mock_find_one(query):
        # Must match both _id and user_id
        if query.get("user_id") == USER_B_ID and (str(query.get("_id")) == TODO_B_ID or query.get("_id") == ObjectId(TODO_B_ID)):
            return todo_b_doc
        return None

    async def mock_delete_one(query):
        result = MagicMock()
        if query.get("user_id") == USER_B_ID and (str(query.get("_id")) == TODO_B_ID or query.get("_id") == ObjectId(TODO_B_ID)):
            result.deleted_count = 1
        else:
            result.deleted_count = 0
        return result

    async def mock_update_one(query, update):
        result = MagicMock()
        if query.get("user_id") == USER_B_ID and (str(query.get("_id")) == TODO_B_ID or query.get("_id") == ObjectId(TODO_B_ID)):
            result.matched_count = 1
        else:
            result.matched_count = 0
        return result

    db.todos.find_one = AsyncMock(side_effect=mock_find_one)
    db.todos.delete_one = AsyncMock(side_effect=mock_delete_one)
    db.todos.update_one = AsyncMock(side_effect=mock_update_one)
    
    # Cursor mock for find()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])
    db.todos.find = MagicMock(return_value=mock_cursor)
    
    return db

def test_user_a_cannot_update_user_b_todo(mock_db_with_ownership):
    """User A attempting to update User B's todo must receive HTTP 404."""
    app.dependency_overrides[get_db] = lambda: mock_db_with_ownership
    app.dependency_overrides[get_current_user] = lambda: {"id": USER_A_ID, "email": USER_A_EMAIL}
    
    try:
        client = TestClient(app)
        res = client.put(
            f"/api/todos/{TODO_B_ID}",
            json={"title": "Hacked Title by User A"}
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "Không tìm thấy công việc"
    finally:
        app.dependency_overrides.clear()

def test_user_a_cannot_delete_user_b_todo(mock_db_with_ownership):
    """User A attempting to delete User B's todo must receive HTTP 404."""
    app.dependency_overrides[get_db] = lambda: mock_db_with_ownership
    app.dependency_overrides[get_current_user] = lambda: {"id": USER_A_ID, "email": USER_A_EMAIL}
    
    try:
        client = TestClient(app)
        res = client.delete(f"/api/todos/{TODO_B_ID}")
        assert res.status_code == 404
        assert res.json()["detail"] == "Không tìm thấy công việc cần xóa"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_update_todo_service_verifies_user_id_in_read_and_update_queries():
    """Verify TodoService.update_todo passes both _id and user_id in update_one and find_one calls."""
    mock_db = MagicMock()
    mock_db.todos.find_one = AsyncMock(return_value={
        "_id": ObjectId(TODO_B_ID),
        "user_id": USER_B_ID,
        "title": "Title",
        "description": "",
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "reminded": False
    })
    mock_db.todos.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    
    mock_update_payload = MagicMock()
    mock_update_payload.title = "New Title"
    mock_update_payload.description = None
    mock_update_payload.status = None
    mock_update_payload.deadline = None

    await TodoService.update_todo(mock_db, USER_B_ID, TODO_B_ID, mock_update_payload)

    # Check find_one before update
    first_find_call_query = mock_db.todos.find_one.call_args_list[0][0][0]
    assert first_find_call_query == {"_id": ObjectId(TODO_B_ID), "user_id": USER_B_ID}

    # Check update_one query
    update_call_query = mock_db.todos.update_one.call_args_list[0][0][0]
    assert update_call_query == {"_id": ObjectId(TODO_B_ID), "user_id": USER_B_ID}

    # Check read-after-update find_one query
    second_find_call_query = mock_db.todos.find_one.call_args_list[1][0][0]
    assert second_find_call_query == {"_id": ObjectId(TODO_B_ID), "user_id": USER_B_ID}
