from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from llama_index.core.tools import FunctionTool

from ..database import get_db
from ..utils import utc_now, make_utc

def parse_deadline_str(deadline: Optional[str]) -> Optional[datetime]:
    if not deadline:
        return None
    cleaned = str(deadline).strip().lower()
    if cleaned in ["", "none", "null", "không có", "không", "undefined", "n/a"]:
        return None
    
    # Try different formats
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
        try:
            val = str(deadline).strip().replace("Z", "+00:00")
            if "t" in val.lower():
                dt = datetime.fromisoformat(val)
                return make_utc(dt)
            dt = datetime.strptime(str(deadline).strip(), fmt)
            return make_utc(dt)
        except Exception:
            continue
            
    # Try parsing direct fromisoformat
    try:
        dt = datetime.fromisoformat(str(deadline).strip().replace("Z", "+00:00"))
        return make_utc(dt)
    except Exception:
        raise ValueError("Không thể phân tích định dạng deadline. Vui lòng gửi định dạng ISO (YYYY-MM-DDTHH:MM:SS).")

async def execute_info_tool(response: str) -> str:
    """
    InforTool: Trả lời các câu hỏi về công việc hoặc chitchat xã giao.
    Đầu vào 'response' là văn bản phản hồi đã được LLM chuẩn bị sẵn.
    """
    return response

async def execute_action_tool(
    action: str,
    user_id: str,
    title: Optional[str] = None,
    description: Optional[str] = "",
    status: Optional[str] = None,
    deadline: Optional[str] = None,
    todo_id: Optional[str] = None,
    id: Optional[str] = None  # Fallback alias for model parameter mismatch
) -> str:
    """
    ActionTool: Thực hiện các thay đổi (tạo, cập nhật, xóa) công việc trong cơ sở dữ liệu.
    - action: 'create' | 'update' | 'delete'
    - user_id: ID của người dùng sở hữu công việc
    - title: Tiêu đề công việc (dành cho create/update)
    - description: Mô tả công việc (dành cho create/update)
    - status: Trạng thái công việc ('pending' | 'in_progress' | 'completed' | 'overdue')
    - deadline: Thời hạn hoàn thành (Định dạng ISO 8601, ví dụ: 2026-06-20T18:00:00)
    - todo_id: ID của công việc dạng chuỗi hex MongoDB ObjectId (bắt buộc cho update/delete)
    """
    if not todo_id and id:
        todo_id = id
        
    db = get_db()
    if db is None:
        return "Lỗi: Kết nối cơ sở dữ liệu MongoDB hiện không khả dụng."
        
    try:
        # 1. TẠO MỚI CÔNG VIỆC (CREATE)
        if action == "create":
            if not title or not title.strip():
                return "Lỗi: Tiêu đề công việc không được để trống khi tạo mới."
            
            try:
                parsed_deadline = parse_deadline_str(deadline)
            except ValueError as e:
                return f"Lỗi: {str(e)}"
            
            now = utc_now()
            new_todo = {
                "user_id": user_id,
                "title": title.strip(),
                "description": (description or "").strip(),
                "status": "pending",
                "deadline": parsed_deadline,
                "created_at": now,
                "updated_at": now,
                "reminded": False
            }
            result = await db.todos.insert_one(new_todo)
            deadline_str = f" với hạn chót là {parsed_deadline.strftime('%H:%M %d/%m/%Y')}" if parsed_deadline else " (không có deadline)"
            return f"✅ Đã thêm công việc thành công: '{title.strip()}'{deadline_str}."
            
        # 2. CẬP NHẬT CÔNG VIỆC (UPDATE)
        elif action == "update":
            if not todo_id:
                return "Lỗi: Thiếu ID công việc (`todo_id`) cần cập nhật."
                
            # Kiểm tra xem ID có hợp lệ không
            try:
                obj_id = ObjectId(todo_id)
            except Exception:
                return f"Lỗi: Định dạng ID công việc '{todo_id}' không hợp lệ."
                
            update_data = {}
            if title is not None:
                update_data["title"] = title.strip()
            if description is not None:
                update_data["description"] = description.strip()
            if status is not None:
                status_clean = status.strip().lower()
                if status_clean in ["pending", "in_progress", "completed", "overdue"]:
                    update_data["status"] = status_clean
                else:
                    return f"Lỗi: Trạng thái '{status}' không hợp lệ. Chỉ chấp nhận: pending, in_progress, completed, overdue."
            
            if deadline is not None:
                try:
                    update_data["deadline"] = parse_deadline_str(deadline)
                except ValueError as e:
                    return f"Lỗi: {str(e)}"
            
            if not update_data:
                return "⚠️ Không có thông tin thay đổi nào được gửi lên để cập nhật."
                
            update_data["updated_at"] = utc_now()
            # Reset flag reminded khi cập nhật deadline mới
            if "deadline" in update_data:
                update_data["reminded"] = False
                
            result = await db.todos.update_one(
                {"_id": obj_id, "user_id": user_id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                return f"❌ Không tìm thấy công việc nào có ID '{todo_id}' thuộc tài khoản của bạn."
            
            changes = ", ".join(update_data.keys())
            return f"📝 Đã cập nhật thành công công việc (các trường thay đổi: {changes})."
            
        # 3. XÓA CÔNG VIỆC (DELETE)
        elif action == "delete":
            if not todo_id:
                return "Lỗi: Thiếu ID công việc (`todo_id`) cần xóa."
                
            try:
                obj_id = ObjectId(todo_id)
            except Exception:
                return f"Lỗi: Định dạng ID công việc '{todo_id}' không hợp lệ."
                
            result = await db.todos.delete_one({"_id": obj_id, "user_id": user_id})
            if result.deleted_count == 0:
                return f"❌ Không tìm thấy công việc nào có ID '{todo_id}' thuộc tài khoản của bạn để xóa."
            return f"🗑️ Đã xóa thành công công việc."
            
        else:
            return f"Lỗi: Hành động '{action}' không hợp lệ. Chỉ hỗ trợ: 'create', 'update', 'delete'."
            
    except Exception as e:
        return f"❌ Đã xảy ra lỗi khi thực hiện ActionTool: {str(e)}"

# Đóng gói thành LlamaIndex FunctionTool để đáp ứng yêu cầu framework
InforTool = FunctionTool.from_defaults(
    async_fn=execute_info_tool,
    name="InforTool",
    description="Dùng để giải đáp các câu hỏi, thắc mắc hoặc trò chuyện xã giao với người dùng."
)

ActionTool = FunctionTool.from_defaults(
    async_fn=execute_action_tool,
    name="ActionTool",
    description="Thực hiện các thao tác ghi dữ liệu với database bao gồm: tạo mới, cập nhật trạng thái/thông tin hoặc xóa công việc."
)
