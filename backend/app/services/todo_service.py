from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException, status

from ..models import TodoCreate, TodoUpdate, serialize_doc
from ..utils import utc_now, make_utc, encode_cursor, decode_cursor

class TodoService:
    @staticmethod
    async def get_user_todos(
        db,
        user_id: str,
        limit: int = 10,
        cursor: Optional[str] = None,
        status_filter: Optional[str] = None,
        sort: str = "created_at",
        order: str = "desc"
    ) -> dict:
        """
        Pure read-only query fetching paginated todos owned by user_id.
        Supports limit, cursor, status filter, sort allowlist, order asc/desc.
        Returns {"items": [...], "next_cursor": str | None}.
        """
        # Validate limit
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tham số limit phải nằm trong khoảng từ 1 đến 100."
            )

        # Validate status filter
        allowed_statuses = ["pending", "in_progress", "completed", "overdue"]
        clean_status = None
        if status_filter:
            clean_status = status_filter.strip().lower()
            if clean_status not in allowed_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Trạng thái không hợp lệ. Chỉ chấp nhận: {', '.join(allowed_statuses)}"
                )

        # Validate sort allowlist
        allowed_sorts = ["created_at", "updated_at", "deadline"]
        clean_sort = sort.strip().lower()
        if clean_sort not in allowed_sorts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Trường sắp xếp không hợp lệ. Chỉ chấp nhận: {', '.join(allowed_sorts)}"
            )

        # Validate order
        clean_order = order.strip().lower()
        if clean_order not in ["asc", "desc"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thứ tự sắp xếp không hợp lệ. Chỉ chấp nhận: asc hoặc desc"
            )

        sort_dir = -1 if clean_order == "desc" else 1

        # Base query scoped by user_id
        query = {"user_id": user_id}
        if clean_status:
            query["status"] = clean_status

        # Validate and decode cursor if provided
        if cursor:
            try:
                cursor_v, cursor_id_str = decode_cursor(cursor)
                cursor_obj_id = ObjectId(cursor_id_str)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cursor không hợp lệ"
                )

            # Build cursor query clause
            if clean_sort in ["created_at", "updated_at"]:
                if sort_dir == -1:  # desc
                    cursor_clause = {
                        "$or": [
                            {clean_sort: {"$lt": cursor_v}},
                            {clean_sort: cursor_v, "_id": {"$lt": cursor_obj_id}}
                        ]
                    }
                else:  # asc
                    cursor_clause = {
                        "$or": [
                            {clean_sort: {"$gt": cursor_v}},
                            {clean_sort: cursor_v, "_id": {"$gt": cursor_obj_id}}
                        ]
                    }
            elif clean_sort == "deadline":
                if sort_dir == -1:  # desc: datetimes > null
                    if cursor_v is not None:
                        cursor_clause = {
                            "$or": [
                                {"deadline": {"$lt": cursor_v}},
                                {"deadline": cursor_v, "_id": {"$lt": cursor_obj_id}}
                            ]
                        }
                    else:
                        cursor_clause = {
                            "deadline": None,
                            "_id": {"$lt": cursor_obj_id}
                        }
                else:  # asc: null < datetimes
                    if cursor_v is None:
                        cursor_clause = {
                            "$or": [
                                {"deadline": None, "_id": {"$gt": cursor_obj_id}},
                                {"deadline": {"$ne": None}}
                            ]
                        }
                    else:
                        cursor_clause = {
                            "$or": [
                                {"deadline": {"$gt": cursor_v}},
                                {"deadline": cursor_v, "_id": {"$gt": cursor_obj_id}}
                            ]
                        }

            query = {"$and": [query, cursor_clause]}

        # Sort criteria: [(sort_field, sort_dir), ("_id", sort_dir)]
        sort_spec = [(clean_sort, sort_dir), ("_id", sort_dir)]

        # Fetch limit + 1 items to check for next page
        cursor_obj = db.todos.find(query).sort(sort_spec).limit(limit + 1)
        raw_todos = await cursor_obj.to_list(length=limit + 1)

        next_cursor = None
        if len(raw_todos) > limit:
            page_todos = raw_todos[:limit]
            last_item = page_todos[-1]
            last_sort_val = last_item.get(clean_sort)
            next_cursor = encode_cursor(last_sort_val, str(last_item["_id"]))
        else:
            page_todos = raw_todos

        return {
            "items": [serialize_doc(t) for t in page_todos],
            "next_cursor": next_cursor
        }


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
