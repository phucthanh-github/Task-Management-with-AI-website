import os
from typing import Literal, List
from pydantic import model_validator
from pydantic_settings import BaseSettings

PLACEHOLDER_SECRETS = {
    "e83a45a30a7d519b5d2bbde4be3db88e5d3c8c7bb86de27d096a605f2c4187f5",
    "supersecretkey1234567890abcdefghijklmnopqrstuv",
    "your_secret_key_here",
    "change_me",
    "secret",
    "12345678901234567890123456789012"
}

class Settings(BaseSettings):
    APP_ENV: Literal["development", "test", "production"] = "development"
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "todolist_db"
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    HF_TOKEN: str = ""
    HF_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_EMAIL: str = ""
    SMTP_PASSWORD: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ALLOWED_ORIGINS: str = ""
    GOOGLE_CLIENT_ID: str = ""
    DEV_DEMO_ENABLED: bool = False
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_CHAT: str = "20/minute"

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        # In development or test, allow dev fallback if SECRET_KEY is omitted
        if self.APP_ENV in ["development", "test"] and not self.SECRET_KEY:
            self.SECRET_KEY = "dev_only_secret_key_must_change_in_production_environment_32chars"

        if self.APP_ENV == "production":
            if not self.SECRET_KEY or len(self.SECRET_KEY) < 32 or self.SECRET_KEY in PLACEHOLDER_SECRETS:
                raise ValueError("SECURITY ERROR: SECRET_KEY is missing, too short (<32 chars), or using unsafe default/placeholder in production.")

            if not self.MONGODB_URL or "your_" in self.MONGODB_URL:
                raise ValueError("SECURITY ERROR: MONGODB_URL must be configured in production.")

            if not self.FRONTEND_URL or "your_" in self.FRONTEND_URL:
                raise ValueError("SECURITY ERROR: FRONTEND_URL must be configured in production.")

            if not self.GOOGLE_CLIENT_ID or "your_google_client_id" in self.GOOGLE_CLIENT_ID:
                raise ValueError("SECURITY ERROR: GOOGLE_CLIENT_ID must be configured in production.")

        return self

    def get_cors_origins(self) -> List[str]:
        origins = set()
        if self.FRONTEND_URL:
            origins.add(self.FRONTEND_URL.rstrip("/"))
        if self.CORS_ALLOWED_ORIGINS:
            for item in self.CORS_ALLOWED_ORIGINS.split(","):
                item_str = item.strip().rstrip("/")
                if item_str:
                    origins.add(item_str)
        if self.APP_ENV == "development":
            origins.update([
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000"
            ])
        return list(origins)

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        extra = "ignore"

settings = Settings()

