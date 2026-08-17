from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from .utils import utc_now

# Helper to serialize MongoDB object IDs
def serialize_doc(doc) -> dict:
    if not doc:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

def serialize_list(docs) -> list:
    return [serialize_doc(doc) for doc in docs]

# Auth Schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Mật khẩu từ 8 đến 128 ký tự")

    @field_validator("email")
    @classmethod
    def validate_gmail(cls, v: str) -> str:
        v = v.lower().strip()
        if not v.endswith("@gmail.com"):
            raise ValueError("Chỉ chấp nhận đăng ký tài khoản bằng định dạng Gmail (@gmail.com)")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Mật khẩu không được chứa toàn khoảng trắng")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Mật khẩu không được chứa toàn khoảng trắng")
        return v

class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    has_hf_token: bool = False

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Todo Schemas
class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Tiêu đề công việc")
    description: Optional[str] = Field(default="", max_length=2000, description="Mô tả chi tiết công việc")
    deadline: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Tiêu đề công việc không được chỉ chứa khoảng trắng")
        return s

class TodoUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = None  # pending, in_progress, completed
    deadline: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Tiêu đề công việc không được chỉ chứa khoảng trắng")
            return s
        return v

class TodoResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    status: str  # pending, in_progress, completed, overdue
    deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    reminded: bool

# Chat Schemas
class ChatMessagePayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Nội dung tin nhắn chat")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Nội dung chat không được chứa toàn khoảng trắng")
        return s

class ChatMessageModel(BaseModel):
    sender: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=utc_now)

class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessageModel]

