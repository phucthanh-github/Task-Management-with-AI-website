import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from typing import Optional
from bson import ObjectId

from ..database import get_db
from ..models import ChatMessagePayload, ChatMessageModel, PaginatedChatHistoryResponse, serialize_list
from ..auth import get_current_user
from ..utils import utc_now, encode_cursor, decode_cursor
from ..agent.graph import agent_graph
from ..config import settings
from ..limiter import limiter

logger = logging.getLogger("todolist_api")

router = APIRouter(prefix="/api/chat", tags=["Chat"])

@router.get("/history", response_model=PaginatedChatHistoryResponse)
async def get_chat_history(
    limit: int = Query(default=10, description="Số lượng tin nhắn trả về trong 1 trang (1-100)"),
    cursor: Optional[str] = Query(default=None, description="Con trỏ phân trang"),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tham số limit phải nằm trong khoảng từ 1 đến 100."
        )

    user_id = current_user["id"]
    query = {"user_id": user_id}

    if cursor:
        try:
            cursor_ts, cursor_id_str = decode_cursor(cursor)
            cursor_obj_id = ObjectId(cursor_id_str)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cursor không hợp lệ"
            )

        cursor_clause = {
            "$or": [
                {"timestamp": {"$lt": cursor_ts}},
                {"timestamp": cursor_ts, "_id": {"$lt": cursor_obj_id}}
            ]
        }
        query = {"$and": [query, cursor_clause]}

    # Sort descending by timestamp and _id to fetch older chunk relative to cursor
    sort_spec = [("timestamp", -1), ("_id", -1)]
    cursor_obj = db.chat_messages.find(query).sort(sort_spec).limit(limit + 1)
    raw_messages = await cursor_obj.to_list(length=limit + 1)

    next_cursor = None
    if len(raw_messages) > limit:
        page_messages = raw_messages[:limit]
        last_item = page_messages[-1]
        next_cursor = encode_cursor(last_item["timestamp"], str(last_item["_id"]))
    else:
        page_messages = raw_messages

    # Reverse page_messages so the items are returned in old-to-new chronological order for UI display
    page_messages.reverse()

    return {
        "items": serialize_list(page_messages),
        "next_cursor": next_cursor
    }

@router.post("")
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def send_chat_message(request: Request, payload: ChatMessagePayload, current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    user_id = current_user["id"]
    user_message = payload.message.strip()
    
    if not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nội dung chat không được trống")
        
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

@router.delete("/history")
async def clear_chat_history(current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cơ sở dữ liệu chưa sẵn sàng")
        
    await db.chat_messages.delete_many({"user_id": current_user["id"]})
    return {"message": "Đã xóa toàn bộ lịch sử trò chuyện"}
