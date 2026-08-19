from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from ..database import get_db
from ..models import TodoCreate, TodoUpdate, TodoResponse, PaginatedTodoResponse
from ..auth import get_current_user
from ..services.todo_service import TodoService

router = APIRouter(prefix="/api/todos", tags=["Todos"])

@router.get("", response_model=PaginatedTodoResponse)
async def get_todos(
    limit: int = Query(default=10, description="Số lượng công việc trả về trong 1 trang (1-100)"),
    cursor: Optional[str] = Query(default=None, description="Con trỏ phân trang"),
    status: Optional[str] = Query(default=None, description="Lọc theo trạng thái: pending, in_progress, completed, overdue"),
    sort: str = Query(default="created_at", description="Trường sắp xếp: created_at, updated_at, deadline"),
    order: str = Query(default="desc", description="Thứ tự sắp xếp: asc, desc"),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
    return await TodoService.get_user_todos(
        db,
        user_id=current_user["id"],
        limit=limit,
        cursor=cursor,
        status_filter=status,
        sort=sort,
        order=order
    )


@router.post("", response_model=TodoResponse)
async def create_todo(todo_in: TodoCreate, current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
    return await TodoService.create_todo(db, current_user["id"], todo_in)

@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: str, todo_in: TodoUpdate, current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
    return await TodoService.update_todo(db, current_user["id"], todo_id, todo_in)

@router.delete("/{todo_id}")
async def delete_todo(todo_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
    return await TodoService.delete_todo(db, current_user["id"], todo_id)
