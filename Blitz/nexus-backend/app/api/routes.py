from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
import uuid
from app.db.database import get_session
from app.models.schemas import Task

router = APIRouter()

@router.get("/tasks", response_model=List[Task])
def get_tasks(session: Session = Depends(get_session)):
    return session.exec(select(Task)).all()

@router.post("/tasks", response_model=Task)
def create_task(task: Task, session: Session = Depends(get_session)):
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@router.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: uuid.UUID, task_update: dict, session: Session = Depends(get_session)):
    db_task = session.get(Task, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in task_update.items():
        if hasattr(db_task, key):
            setattr(db_task, key, value)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task

@router.delete("/tasks/{task_id}")
def delete_task(task_id: uuid.UUID, session: Session = Depends(get_session)):
    db_task = session.get(Task, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(db_task)
    session.commit()
    return {"ok": True, "message": "Task deleted successfully"}
