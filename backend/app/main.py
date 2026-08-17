import logging
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from bson import ObjectId
from typing import List, Optional

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pymongo.errors import DuplicateKeyError

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from .config import settings
from .database import connect_to_mongo, close_mongo_connection, get_db
from .utils import utc_now
from .models import (
    UserRegister, UserLogin, UserResponse, Token, TodoCreate, TodoUpdate, TodoResponse,
    ChatMessagePayload, ChatMessageModel, ChatHistoryResponse, serialize_doc, serialize_list
)
from .auth import get_password_hash, verify_password, create_access_token, get_current_user
from .scheduler import start_scheduler, shutdown_scheduler
from .agent.graph import agent_graph
from .routers.todos import router as todos_router

# Logging Configuration with Credential Redaction
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("todolist_api")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="To Do List AI Assistant", version="1.0.0")
app.state.limiter = limiter

app.include_router(todos_router)

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau ít phút."}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers if hasattr(exc, "headers") else None
        )
    logger.error(f"[Unhandled Error] Path: {request.url.path} | Error: {exc.__class__.__name__}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Đã xảy ra lỗi máy chủ nội bộ. Vui lòng thử lại sau."}
    )

# Setup Strict CORS without regex wildcards
cors_origins = settings.get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Startup and Shutdown Lifecycle Hooks
@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()
    shutdown_scheduler()

@app.get("/")
def read_root():
    return {"message": "Welcome to To Do List AI API"}

# ==========================================
# AUTH ENDPOINTS
# ==========================================

@app.post("/api/auth/register", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register_user(request: Request, user_in: UserRegister, db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_in.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản Gmail này đã được đăng ký trước đó."
        )
        
    hashed_password = get_password_hash(user_in.password)
    new_user = {
        "email": user_in.email,
        "hashed_password": hashed_password,
        "created_at": utc_now()
    }
    
    try:
        result = await db.users.insert_one(new_user)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản Gmail này đã được đăng ký trước đó."
        )
    created_user = await db.users.find_one({"_id": result.inserted_id})
    return serialize_doc(created_user)

@app.post("/api/auth/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login_user(request: Request, user_in: UserLogin, db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    # Check user email
    user = await db.users.find_one({"email": user_in.email})
    if not user or not verify_password(user_in.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác."
        )
        
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
    user_doc = await db.users.find_one({"_id": ObjectId(current_user["id"])})
    has_token = bool(user_doc.get("hf_token")) if user_doc else False
    return {
        **current_user,
        "has_hf_token": has_token
    }

class HFTokenPayload(BaseModel):
    hf_token: str

@app.put("/api/users/hf-token")
async def update_hf_token(payload: HFTokenPayload, current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
    
    token_val = payload.hf_token.strip()
    if not token_val:
        raise HTTPException(status_code=400, detail="Token không được để trống")
        
    await db.users.update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$set": {"hf_token": token_val}}
    )
    return {"message": "Đã cập nhật Hugging Face Token thành công"}

@app.delete("/api/users/hf-token")
async def delete_hf_token(current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
    
    await db.users.update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$unset": {"hf_token": ""}}
    )
    return {"message": "Đã xóa Hugging Face Token"}

class GoogleTokenPayload(BaseModel):
    token: str

@app.post("/api/auth/google-login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def google_login(request: Request, payload: GoogleTokenPayload, db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    google_token = payload.token.strip()
    if not google_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã xác thực Google ID Token không được để trống."
        )
    
    # 1. Verify Google token using official google-auth library
    try:
        req = google_requests.Request()
        target_aud = settings.GOOGLE_CLIENT_ID if settings.GOOGLE_CLIENT_ID and "your_google_client_id" not in settings.GOOGLE_CLIENT_ID else None
        
        google_info = id_token.verify_oauth2_token(google_token, req, audience=target_aud)
        
        # Verify issuer
        iss = google_info.get("iss", "")
        if iss not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError(f"Invalid Google token issuer: {iss}")
            
        # Verify email_verified status
        email_verified = google_info.get("email_verified")
        if email_verified is not True and email_verified != "true":
            raise ValueError("Google email not verified")
            
    except Exception as exc:
        logger.warning(f"[Google Auth Verification Error]: {exc.__class__.__name__}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã xác thực Google ID Token không hợp lệ hoặc đã bị từ chối."
        )
        
    email = google_info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không tìm thấy email từ mã Google trả về."
        )
        
    email = email.lower().strip()
    if not email.endswith("@gmail.com"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận tài khoản Gmail (@gmail.com)."
        )
        
    # 2. Check if user already exists. If not, auto register them
    user = await db.users.find_one({"email": email})
    if not user:
        new_user = {
            "email": email,
            "hashed_password": get_password_hash("google_signed_in_oauth_account"),
            "created_at": utc_now()
        }
        try:
            await db.users.insert_one(new_user)
            logger.info(f"[Google Auth] Registered new user from Google Sign-In: {email}")
        except DuplicateKeyError:
            logger.info(f"[Google Auth] Concurrent registration caught DuplicateKeyError for email: {email}")
        user = await db.users.find_one({"email": email})
    else:
        logger.info(f"[Google Auth] Logged in existing user from Google Sign-In: {email}")
        
    # 3. Create app JWT access token
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}


# ==========================================
# CHAT / AGENT ENDPOINTS
# ==========================================

@app.get("/api/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    # Get last 10 chat messages in chronological order
    cursor = db.chat_messages.find({"user_id": current_user["id"]}).sort("timestamp", -1).limit(10)
    messages = await cursor.to_list(length=10)
    # Reverse to make it oldest to newest
    messages.reverse()
    
    return {"messages": serialize_list(messages)}

@app.post("/api/chat")
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def send_chat_message(request: Request, payload: ChatMessagePayload, current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    user_id = current_user["id"]
    user_message = payload.message.strip()
    
    if not user_message:
        raise HTTPException(status_code=400, detail="Nội dung chat không được trống")
        
    # 1. Save User Message to database
    await db.chat_messages.insert_one({
        "user_id": user_id,
        "sender": "user",
        "content": user_message,
        "timestamp": utc_now()
    })
    
    # 2. Retrieve last 10 chat messages for Agent history context
    cursor = db.chat_messages.find({"user_id": user_id}).sort("timestamp", -1).limit(10)
    history = await cursor.to_list(length=10)
    history.reverse()
    
    # Standard format for AgentState
    formatted_history = [
        {"sender": msg["sender"], "content": msg["content"]} for msg in history
    ]
    
    # 3. Retrieve user's hf_token
    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    hf_token = user_doc.get("hf_token", "") if user_doc else ""
    
    # 4. Retrieve current active todos for Context injection
    todo_cursor = db.todos.find({"user_id": user_id}).sort("created_at", -1)
    raw_todos = await todo_cursor.to_list(length=100)
    todos = serialize_list(raw_todos)
    
    # 5. Invoke Agent Graph
    initial_state = {
        "messages": formatted_history,
        "user_id": user_id,
        "todos": todos,
        "tool_calls": [],
        "final_response": "",
        "should_refresh": False,
        "hf_token": hf_token
    }
    
    try:
        final_state = await agent_graph.ainvoke(initial_state)
        ai_response = final_state.get("final_response", "Xin lỗi, tôi đã gặp sự cố khi xử lý thông tin.")
        should_refresh = final_state.get("should_refresh", False)
    except Exception as e:
        logger.error(f"[Chat API] Graph execution error: {e.__class__.__name__}")
        ai_response = "Đã xảy ra lỗi trong quá trình xử lý câu hỏi với AI. Vui lòng thử lại sau."
        should_refresh = False

    # 6. Save Agent Response to database
    await db.chat_messages.insert_one({
        "user_id": user_id,
        "sender": "assistant",
        "content": ai_response,
        "timestamp": utc_now()
    })
    
    return {
        "response": ai_response,
        "should_refresh": should_refresh
    }


@app.delete("/api/chat/history")
async def clear_chat_history(current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    await db.chat_messages.delete_many({"user_id": current_user["id"]})
    return {"message": "Đã xóa toàn bộ lịch sử trò chuyện"}
