from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    template_id: str
    start_date: date
    event_date: date


class ProjectTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_task_id: str | None
    milestone_id: str | None
    project_milestone_id: str | None
    title: str
    owner: str | None
    status: str
    deadline: date
    required: bool | None
    completed_at: datetime | None
    milestone_code: str
    milestone_name: str


class TaskStatusUpdate(BaseModel):
    status: Literal["todo", "done"]


class TaskOwnerUpdate(BaseModel):
    owner: str | None = Field(default=None, max_length=200)


class TaskRequiredUpdate(BaseModel):
    required: bool


class ProjectTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    project_milestone_id: str
    owner: str | None = Field(default=None, max_length=200)
    required: bool = False


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    start_date: date
    event_date: date
    status: str
    template_id: str
    milestones: list[ProjectMilestoneRead]
    tasks: list[ProjectTaskRead]


class ProjectMilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_milestone_id: str | None
    code: str
    name: str
    phase: str
    deadline: date
    required: bool | None
    status: str
    sort_order: int


class ProjectMilestoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    deadline: date
    required: bool = False


class ProjectMilestoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    deadline: date | None = None
    required: bool | None = None


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    start_date: date
    event_date: date
    status: str
    template_id: str
