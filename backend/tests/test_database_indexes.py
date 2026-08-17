import pytest
from unittest.mock import AsyncMock, MagicMock
from pymongo.errors import DuplicateKeyError
from fastapi.testclient import TestClient

from app.database import db_helper, init_indexes, get_db
from app.main import app

@pytest.mark.asyncio
async def test_init_indexes_creates_all_indexes_idempotently():
    """Verify init_indexes creates all 4 specified indexes without errors and is idempotent."""
    mock_db = MagicMock()
    mock_db.users.create_index = AsyncMock()
    mock_db.todos.create_index = AsyncMock()
    mock_db.chat_messages.create_index = AsyncMock()

    db_helper.db = mock_db

    # First call
    await init_indexes()

    assert mock_db.users.create_index.call_count == 1
    assert mock_db.todos.create_index.call_count == 2
    assert mock_db.chat_messages.create_index.call_count == 1

    # Verify parameters
    mock_db.users.create_index.assert_called_with([("email", 1)], unique=True)
    mock_db.todos.create_index.assert_any_call([("user_id", 1), ("created_at", -1)])
    mock_db.todos.create_index.assert_any_call([("user_id", 1), ("status", 1), ("deadline", 1)])
    mock_db.chat_messages.create_index.assert_called_with([("user_id", 1), ("timestamp", -1)])

    # Second call (idempotency check)
    await init_indexes()

    assert mock_db.users.create_index.call_count == 2
    assert mock_db.todos.create_index.call_count == 4
    assert mock_db.chat_messages.create_index.call_count == 2


@pytest.mark.asyncio
async def test_init_indexes_handles_duplicate_key_error_gracefully():
    """Verify init_indexes handles pre-existing duplicate data gracefully without throwing exceptions."""
    mock_db = MagicMock()
    mock_db.users.create_index = AsyncMock(side_effect=DuplicateKeyError("E11000 duplicate key error"))
    mock_db.todos.create_index = AsyncMock()
    mock_db.chat_messages.create_index = AsyncMock()

    db_helper.db = mock_db

    # Should not raise exception
    await init_indexes()
    assert mock_db.users.create_index.call_count == 1


def test_register_user_handles_duplicate_key_error():
    """Registering a user that triggers DuplicateKeyError must safely return HTTP 400."""
    mock_db = MagicMock()
    mock_db.users.find_one = AsyncMock(return_value=None)
    mock_db.users.insert_one = AsyncMock(side_effect=DuplicateKeyError("E11000 duplicate key error"))

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/auth/register",
            json={"email": "duplicate@gmail.com", "password": "password123"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Tài khoản Gmail này đã được đăng ký trước đó."
    finally:
        app.dependency_overrides.clear()
