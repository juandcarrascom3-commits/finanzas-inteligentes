import enum
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from sqlmodel import Field, Relationship, SQLModel

class StatusEnum(str, enum.Enum):
    todo = "todo"
    in_progress = "in-progress"
    review = "review"
    done = "done"

class PriorityEnum(str, enum.Enum):
    critical = "critical"
    medium = "medium"
    low = "low"

class Subtask(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    isCompleted: bool = Field(default=False)
    task_id: uuid.UUID = Field(foreign_key="task.id")
    task: "Task" = Relationship(back_populates="subtasks")

class Note(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    content_markdown: str = Field(default="")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: uuid.UUID = Field(foreign_key="task.id", unique=True)
    task: "Task" = Relationship(back_populates="note")

class Task(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    description: Optional[str] = Field(default=None)
    status: StatusEnum = Field(default=StatusEnum.todo)
    priority: PriorityEnum = Field(default=PriorityEnum.low)
    deadline: Optional[str] = Field(default=None)
    hasNotes: bool = Field(default=False)
    subtasks: List[Subtask] = Relationship(back_populates="task")
    note: Optional[Note] = Relationship(back_populates="task")
