from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException, status

from ..models import TodoCreate, TodoUpdate, serialize_doc
from ..utils import utc_now, make_utc

class TodoService:
    @staticmethod
    async def get_user_todos(db, user_id: str) -> List[dict]:
        """
        Pure read-only query fetching todos owned by user_id.
        No database side-effect write operations allowed during GET requests.
        """
        cursor = db.todos.find({"user_id": user_id}).sort("created_at", -1)
        todos = await cursor.to_list(length=100)
        return [serialize_doc(todo) for todo in todos]

    @staticmethod
    async def create_todo(db, user_id: str, todo_in: TodoCreate) -> dict:
        deadline_utc = make_utc(todo_in.deadline)
        now = utc_now()
            
        new_todo = {
            "user_id": user_id,
            "title": todo_in.title.strip(),
            "description": todo_in.description.strip() if todo_in.description else "",
            "status": "pending",
            "deadline": deadline_utc,
            "created_at": now,
            "updated_at": now,
            "reminded": False
        }
        
        result = await db.todos.insert_one(new_todo)
        created_todo = await db.todos.find_one({"_id": result.inserted_id, "user_id": user_id})
        return serialize_doc(created_todo)

    @staticmethod
    async def update_todo(db, user_id: str, todo_id: str, todo_in: TodoUpdate) -> dict:
        try:
            obj_id = ObjectId(todo_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã công việc không hợp lệ")
            
        todo = await db.todos.find_one({"_id": obj_id, "user_id": user_id})
        if not todo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc")
            
        update_data = {}
        
        # Title validation: if provided, trimmed string must not be empty
        if todo_in.title is not None:
            trimmed_title = todo_in.title.strip()
            if not trimmed_title:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tiêu đề công việc không được chỉ chứa khoảng trắng")
            update_data["title"] = trimmed_title
            
        if todo_in.description is not None:
            update_data["description"] = todo_in.description.strip()
            
        if todo_in.status is not None:
            status_clean = todo_in.status.strip().lower()
            if status_clean not in ["pending", "in_progress", "completed", "overdue"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trạng thái không hợp lệ")
            update_data["status"] = status_clean
            
        # Deadline semantics: check if deadline was explicitly provided in model_fields_set or as argument
        # Pydantic model_fields_set allows distinguishing between omitted field vs explicit None
        fields_set = getattr(todo_in, "__pydantic_fields_set__", set())
        if "deadline" in fields_set or todo_in.deadline is not None:
            new_deadline = make_utc(todo_in.deadline) if todo_in.deadline else None
            update_data["deadline"] = new_deadline
            update_data["reminded"] = False

        if update_data:
            now = utc_now()
            update_data["updated_at"] = now
            await db.todos.update_one(
                {"_id": obj_id, "user_id": user_id},
                {"$set": update_data}
            )
            
        updated_todo = await db.todos.find_one({"_id": obj_id, "user_id": user_id})
        return serialize_doc(updated_todo)

    @staticmethod
    async def delete_todo(db, user_id: str, todo_id: str) -> dict:
        try:
            obj_id = ObjectId(todo_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã công việc không hợp lệ")
            
        result = await db.todos.delete_one({"_id": obj_id, "user_id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc cần xóa")
            
        return {"message": "Đã xóa công việc thành công"}

    @staticmethod
    async def update_overdue_todos(db) -> int:
        """
        Standalone job to transition pending and in_progress tasks past deadline to overdue.
        Does NOT touch completed tasks.
        """
        if db is None:
            return 0
        now = utc_now()
        query = {
            "status": {"$in": ["pending", "in_progress"]},
            "deadline": {"$ne": None, "$lt": now}
        }
        result = await db.todos.update_many(
            query,
            {"$set": {"status": "overdue", "updated_at": now}}
        )
        return result.modified_count
