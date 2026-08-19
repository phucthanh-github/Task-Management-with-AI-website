import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from app.services.todo_service import TodoService
from app.models import TodoCreate, TodoUpdate
from app.utils import utc_now, make_utc

USER_ID = "507f1f77bcf86cd799439011"
TODO_ID = "507f1f77bcf86cd799439022"

@pytest.mark.asyncio
async def test_create_todo_normalizes_plus_07_timezone_to_utc():
    """Client sending ISO deadline with +07:00 offset must be accurately normalized to UTC."""
    mock_db = MagicMock()
    mock_db.todos.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId(TODO_ID)))
    mock_db.todos.find_one = AsyncMock(return_value={
        "_id": ObjectId(TODO_ID),
        "user_id": USER_ID,
        "title": "Task with +07:00 timezone",
        "description": "",
        "status": "pending",
        "deadline": datetime(2026, 8, 20, 13, 0, 0, tzinfo=timezone.utc),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "reminded": False
    })

    # 20:00 UTC+7 is 13:00 UTC
    dt_plus7 = datetime(2026, 8, 20, 20, 0, 0, tzinfo=timezone(timedelta(hours=7)))
    todo_in = TodoCreate(title="Task with +07:00 timezone", deadline=dt_plus7)

    result = await TodoService.create_todo(mock_db, USER_ID, todo_in)

    # Check inserted doc sent to MongoDB
    inserted_doc = mock_db.todos.insert_one.call_args[0][0]
    stored_deadline = inserted_doc["deadline"]

    assert stored_deadline.tzinfo == timezone.utc
    assert stored_deadline.hour == 13
    assert stored_deadline.day == 20

@pytest.mark.asyncio
async def test_update_todo_deadline_null_clears_deadline_and_resets_reminded():
    """Updating deadline to null must clear the deadline and reset reminded flag to False."""
    mock_db = MagicMock()
    mock_db.todos.find_one = AsyncMock(return_value={
        "_id": ObjectId(TODO_ID),
        "user_id": USER_ID,
        "title": "Task with deadline",
        "description": "",
        "status": "pending",
        "deadline": datetime(2026, 8, 20, 13, 0, 0, tzinfo=timezone.utc),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "reminded": True
    })
    mock_db.todos.update_one = AsyncMock(return_value=MagicMock(matched_count=1))

    todo_update = TodoUpdate(deadline=None)
    
    await TodoService.update_todo(mock_db, USER_ID, TODO_ID, todo_update)

    update_call_args = mock_db.todos.update_one.call_args[0][1]["$set"]
    assert update_call_args["deadline"] is None
    assert update_call_args["reminded"] is False

@pytest.mark.asyncio
async def test_get_todos_is_strictly_read_only():
    """GET /api/todos must be strictly read-only and never trigger DB write operations."""
    mock_db = MagicMock()
    
    past_due_todo = {
        "_id": ObjectId(TODO_ID),
        "user_id": USER_ID,
        "title": "Past due task",
        "description": "",
        "status": "pending",
        "deadline": utc_now() - timedelta(days=1),
        "created_at": utc_now() - timedelta(days=2),
        "updated_at": utc_now() - timedelta(days=2),
        "reminded": False
    }

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[past_due_todo])
    mock_db.todos.find = MagicMock(return_value=mock_cursor)
    mock_db.todos.update_one = AsyncMock()


    result = await TodoService.get_user_todos(mock_db, USER_ID)

    assert len(result["items"]) == 1
    assert result["next_cursor"] is None
    # Verify update_one was NEVER called during GET
    assert mock_db.todos.update_one.call_count == 0


@pytest.mark.asyncio
async def test_update_overdue_todos_job_transitions_pending_tasks_not_completed():
    """Overdue job must update pending/in_progress tasks past deadline to overdue, ignoring completed tasks."""
    mock_db = MagicMock()
    mock_db.todos.update_many = AsyncMock(return_value=MagicMock(modified_count=2))

    modified_count = await TodoService.update_overdue_todos(mock_db)

    assert modified_count == 2
    assert mock_db.todos.update_many.call_count == 1
    
    query = mock_db.todos.update_many.call_args[0][0]
    update_payload = mock_db.todos.update_many.call_args[0][1]["$set"]

    # Verify query filters only pending and in_progress
    assert query["status"] == {"$in": ["pending", "in_progress"]}
    assert query["deadline"]["$ne"] is None
    assert update_payload["status"] == "overdue"
