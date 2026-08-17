from fastapi import APIRouter, Depends, HTTPException
from typing import List

from ..database import get_db
from ..models import TodoCreate, TodoUpdate, TodoResponse
from ..auth import get_current_user
from ..services.todo_service import TodoService

router = APIRouter(prefix="/api/todos", tags=["Todos"])

@router.get("", response_model=List[TodoResponse])
async def get_todos(current_user = Depends(get_current_user), db = Depends(get_db)):
    if db is None:
        raise HTTPException(status_code=503, detail="Cơ sở dữ liệu chưa sẵn sàng")
    return await TodoService.get_user_todos(db, current_user["id"])

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
