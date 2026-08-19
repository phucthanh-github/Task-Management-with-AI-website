import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta, timezone
from jose import jwt
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.auth import create_access_token
from app.models import UserRegister, TodoCreate, ChatMessagePayload, UserLogin
from app.database import get_db
from app.utils import utc_now
from app.main import app

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.users.find_one = AsyncMock(return_value=None)
    db.users.insert_one = AsyncMock(return_value=MagicMock(inserted_id="507f1f77bcf86cd799439011"))
    db.todos.find_one = AsyncMock(return_value=None)
    db.chat_messages.insert_one = AsyncMock(return_value=MagicMock(inserted_id="507f1f77bcf86cd799439012"))
    return db

@pytest.fixture(autouse=True)
def override_db_dependency(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.clear()

def test_production_fails_fast_on_invalid_secret_key():
    """Production mode must fail fast if SECRET_KEY is missing, too short, or unsafe placeholder."""
    with pytest.raises(ValueError, match="SECURITY ERROR"):
        Settings(
            APP_ENV="production",
            SECRET_KEY="short",
            MONGODB_URL="mongodb://localhost:27017",
            FRONTEND_URL="http://localhost:5173",
            GOOGLE_CLIENT_ID="valid_google_client_id_12345.apps.googleusercontent.com"
        )

    with pytest.raises(ValueError, match="SECURITY ERROR"):
        Settings(
            APP_ENV="production",
            SECRET_KEY="supersecretkey1234567890abcdefghijklmnopqrstuv",
            MONGODB_URL="mongodb://localhost:27017",
            FRONTEND_URL="http://localhost:5173",
            GOOGLE_CLIENT_ID="valid_google_client_id_12345.apps.googleusercontent.com"
        )

def test_jwt_ttl_from_config():
    """JWT expiration time must accurately reflect ACCESS_TOKEN_EXPIRE_MINUTES setting."""
    start_time = utc_now()
    token = create_access_token({"sub": "test@gmail.com"})
    
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    expected_exp = start_time + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    assert abs((exp - expected_exp).total_seconds()) < 10

def test_cors_origin_allowlist():
    """CORS origins must only allow explicit configured origins and localhost in dev."""
    dev_settings = Settings(
        APP_ENV="development",
        FRONTEND_URL="http://localhost:5173",
        CORS_ALLOWED_ORIGINS="https://myapp.com"
    )
    origins = dev_settings.get_cors_origins()
    assert "https://myapp.com" in origins
    assert "http://localhost:5173" in origins
    assert "http://evil-attacker.com" not in origins

    prod_settings = Settings(
        APP_ENV="production",
        SECRET_KEY="production_secret_key_very_secure_and_long_enough_32chars",
        MONGODB_URL="mongodb://atlas:27017",
        FRONTEND_URL="https://myapp.com",
        CORS_ALLOWED_ORIGINS="https://dashboard.myapp.com",
        GOOGLE_CLIENT_ID="123456.apps.googleusercontent.com"
    )
    prod_origins = prod_settings.get_cors_origins()
    assert "https://myapp.com" in prod_origins
    assert "https://dashboard.myapp.com" in prod_origins
    assert "http://localhost:5173" not in prod_origins

def test_input_validation_password_length():
    """Password must be between 8 and 128 characters."""
    with pytest.raises(ValidationError):
        UserRegister(email="user@gmail.com", password="123")

    with pytest.raises(ValidationError):
        UserRegister(email="user@gmail.com", password="   ")

def test_input_validation_title_and_message():
    """Title and chat message must reject whitespace-only or oversized strings."""
    with pytest.raises(ValidationError):
        TodoCreate(title="   ")

    with pytest.raises(ValidationError):
        TodoCreate(title="a" * 201)

    with pytest.raises(ValidationError):
        ChatMessagePayload(message="   ")

    with pytest.raises(ValidationError):
        ChatMessagePayload(message="x" * 2001)

def test_google_login_rejects_empty_or_invalid_token():
    """Google login route should reject empty/invalid token without leaking raw stacktrace."""
    client = TestClient(app)
    response = client.post("/api/auth/google-login", json={"token": "invalid_fake_token"})
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "Google ID Token" in detail
    assert "Traceback" not in detail
    assert "Exception" not in detail

def test_rate_limit_auth_endpoints():
    """Auth endpoint should enforce rate limiting (HTTP 429) on excessive requests."""
    client = TestClient(app)
    responses = []
    # Send requests exceeding the limit (5 per minute)
    for i in range(10):
        res = client.post("/api/auth/login", json={"email": "invalid@gmail.com", "password": "wrongpassword123"})
        responses.append(res.status_code)
    
    assert 429 in responses
