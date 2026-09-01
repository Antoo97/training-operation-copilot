from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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
    start_date: date
    deadline: date
    required: bool | None
    progress_percent: int
    progress_mode: str
    auto_progress_percent: int
    effective_progress_percent: int
    progress_note: str | None
    completion_criteria: str | None
    notes: str | None
    quality_score: int | None
    retrospective_note: str | None
    resource_count: int
    completed_at: datetime | None
    subtasks: list[SubtaskRead]
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
    event_date: date | None
    end_date: date | None
    status: str
    template_id: str | None
    program_id: str | None
    cohort_id: str | None
    activity_type: str | None
    owner_name: str | None
    milestones: list[ProjectMilestoneRead]
    tasks: list[ProjectTaskRead]


class ProjectMilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_milestone_id: str | None
    code: str
    name: str
    phase: str
    start_date: date
    deadline: date
    required: bool | None
    status: str
    sort_order: int


class ProjectMilestoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    start_date: date | None = None
    deadline: date
    required: bool = False


class ProjectMilestoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    deadline: date | None = None
    required: bool | None = None


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    start_date: date
    event_date: date | None
    end_date: date | None
    status: str
    template_id: str | None
    program_id: str | None
    cohort_id: str | None
    activity_type: str | None
    owner_name: str | None


ProgramType = Literal["annual_comprehensive", "multi_cohort", "annual_continuous"]
ProgramStatus = Literal["planning", "active", "on_hold", "completed", "archived"]
ActivityType = Literal[
    "offline_training", "online_training", "assignment", "practice", "research",
    "certification", "opening", "closing", "other",
]


class ProgramCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    program_type: ProgramType
    owner_name: str | None = Field(default=None, max_length=500)
    start_date: date
    end_date: date
    description: str | None = None
    business_unit: str | None = Field(default=None, max_length=200)
    participant_count: int | None = Field(default=None, ge=0)


class ProgramUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    owner_name: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    status: ProgramStatus | None = None
    current_phase: str | None = Field(default=None, max_length=100)
    description: str | None = None
    business_unit: str | None = Field(default=None, max_length=200)
    participant_count: int | None = Field(default=None, ge=0)


class ProgramSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    program_type: str
    owner_name: str | None
    start_date: date
    end_date: date
    status: str
    current_phase: str | None
    business_unit: str | None
    participant_count: int | None


class CohortCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    business_unit: str | None = Field(default=None, max_length=200)
    participant_count: int = Field(default=0, ge=0)
    start_date: date
    end_date: date


class CohortUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    business_unit: str | None = Field(default=None, max_length=200)
    participant_count: int | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    status: Literal["planning", "active", "completed", "archived"] | None = None
    graduated: bool | None = None
    progress_override: int | None = Field(default=None, ge=0, le=100)


class CohortRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    program_id: str
    name: str
    business_unit: str | None
    participant_count: int
    start_date: date
    end_date: date
    status: str
    graduated: bool
    progress_override: int | None


class TrainingClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    participant_count: int = Field(default=0, ge=0)
    business_unit: str | None = Field(default=None, max_length=200)


class TrainingClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    participant_count: int | None = Field(default=None, ge=0)
    business_unit: str | None = Field(default=None, max_length=200)


class TrainingClassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    program_id: str
    name: str
    start_date: date
    end_date: date
    participant_count: int
    business_unit: str | None


class ActivityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    activity_type: ActivityType
    start_date: date
    end_date: date
    event_date: date | None = None
    template_id: str | None = None
    cohort_id: str | None = None
    owner_name: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=300)
    business_unit: str | None = Field(default=None, max_length=200)
    participant_count: int | None = Field(default=None, ge=0)


class ActivityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    cohort_id: str | None = None
    owner_name: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=300)
    business_unit: str | None = Field(default=None, max_length=200)
    participant_count: int | None = Field(default=None, ge=0)


class ProgramRead(ProgramSummary):
    description: str | None
    cohorts: list[CohortRead]
    activities: list[ProjectSummary]
    classes: list[TrainingClassRead]


WorkStatus = Literal["todo", "in_progress", "blocked", "done", "cancelled"]


class SubtaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    owner: str | None = Field(default=None, max_length=500)
    start_date: date
    deadline: date
    notes: str | None = None


class SubtaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    owner: str | None = Field(default=None, max_length=500)
    status: WorkStatus | None = None
    start_date: date | None = None
    deadline: date | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = None


class SubtaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    title: str
    owner: str | None
    status: str
    start_date: date
    deadline: date
    progress_percent: int
    notes: str | None
    sort_order: int
    completed_at: datetime | None


class TaskV2Update(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    owner: str | None = Field(default=None, max_length=500)
    status: WorkStatus | None = None
    start_date: date | None = None
    deadline: date | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    progress_mode: Literal["auto", "manual"] | None = None
    progress_note: str | None = None
    completion_criteria: str | None = None
    notes: str | None = None
    quality_score: int | None = Field(default=None, ge=1, le=5)
    retrospective_note: str | None = None


class TaskV2Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    project_milestone_id: str | None
    title: str
    owner: str | None
    status: str
    start_date: date
    deadline: date
    required: bool | None
    progress_percent: int
    progress_mode: str
    auto_progress_percent: int
    effective_progress_percent: int
    progress_note: str | None
    completion_criteria: str | None
    notes: str | None
    quality_score: int | None
    retrospective_note: str | None
    completed_at: datetime | None
    subtasks: list[SubtaskRead]
    resource_count: int


class TaskBulkUpdate(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=200)
    action: Literal["complete"]


class ActivityLogCreate(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)


class ActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    program_id: str
    activity_id: str | None
    cohort_id: str | None
    occurred_at: datetime
    actor_name: str
    module: str
    action: str
    entity_type: str | None
    entity_id: str | None
    summary: str
    changes_json: dict
    source: str
    is_manual_entry: bool


BudgetStatus = Literal["pending_submission", "in_review", "approved"]
RequirementStatus = Literal["pending", "in_progress", "done"]
MaterialStatus = RequirementStatus
PublicityStatus = RequirementStatus


class ReferencePriceCreate(BaseModel):
    expense_name: str = Field(min_length=1, max_length=200)
    price_type: Literal["unit", "range"] = "unit"
    unit_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    min_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    unit: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    source_note: str | None = None
    is_active: bool = True


class ReferencePriceUpdate(BaseModel):
    expense_name: str | None = Field(default=None, min_length=1, max_length=200)
    price_type: Literal["unit", "range"] | None = None
    unit_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    min_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    unit: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    source_note: str | None = None
    is_active: bool | None = None


class ReferencePriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    expense_name: str
    price_type: str
    unit_price: Decimal | None
    min_price: Decimal | None
    max_price: Decimal | None
    unit: str | None
    notes: str | None
    source_note: str | None
    is_active: bool
    updated_at: datetime


class BudgetSheetCreate(BaseModel):
    program_id: str
    activity_id: str | None = None
    owner_name: str | None = Field(default=None, max_length=500)
    planned_apply_date: date | None = None
    actual_apply_date: date | None = None
    status: BudgetStatus = "pending_submission"
    notes: str | None = None


class BudgetSheetUpdate(BaseModel):
    owner_name: str | None = Field(default=None, max_length=500)
    planned_apply_date: date | None = None
    actual_apply_date: date | None = None
    status: BudgetStatus | None = None
    notes: str | None = None


class BudgetItemCreate(BaseModel):
    expense_name: str = Field(min_length=1, max_length=200)
    is_involved: bool = True
    quantity: Decimal = Field(default=Decimal("1"), ge=0, decimal_places=2)
    unit: str | None = Field(default=None, max_length=50)
    reference_price_id: str | None = None
    estimated_unit_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    estimated_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    is_confirmed: bool = False
    status: BudgetStatus = "pending_submission"
    notes: str | None = None
    sort_order: int = 0


class BudgetItemUpdate(BaseModel):
    expense_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_involved: bool | None = None
    quantity: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    unit: str | None = Field(default=None, max_length=50)
    reference_price_id: str | None = None
    estimated_unit_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    estimated_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    is_confirmed: bool | None = None
    status: BudgetStatus | None = None
    notes: str | None = None
    sort_order: int | None = None


class BudgetItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    budget_sheet_id: str
    expense_name: str
    is_involved: bool
    quantity: Decimal
    unit: str | None
    reference_price_id: str | None
    reference_unit_price: Decimal | None
    reference_min_price: Decimal | None
    reference_max_price: Decimal | None
    estimated_unit_price: Decimal | None
    estimated_amount: Decimal
    amount_overridden: bool
    is_confirmed: bool
    status: str
    notes: str | None
    sort_order: int


class BudgetSheetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    program_id: str
    activity_id: str | None
    owner_name: str | None
    planned_apply_date: date | None
    actual_apply_date: date | None
    status: str
    notes: str | None
    items: list[BudgetItemRead]
    estimated_total: Decimal


class MaterialRequirementCreate(BaseModel):
    program_id: str
    activity_id: str | None = None
    budget_item_id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    quantity: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    specification: str | None = Field(default=None, max_length=500)
    owner_name: str | None = Field(default=None, max_length=500)
    content_due_date: date | None = None
    expected_delivery_date: date | None = None
    status: MaterialStatus = "pending"
    notes: str | None = None
    include_in_budget: bool = False


class MaterialRequirementUpdate(BaseModel):
    activity_id: str | None = None
    budget_item_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    specification: str | None = Field(default=None, max_length=500)
    owner_name: str | None = Field(default=None, max_length=500)
    content_due_date: date | None = None
    expected_delivery_date: date | None = None
    status: MaterialStatus | None = None
    notes: str | None = None
    include_in_budget: bool | None = None


class MaterialRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    program_id: str
    activity_id: str | None
    budget_item_id: str | None
    name: str
    quantity: Decimal | None
    specification: str | None
    owner_name: str | None
    content_due_date: date | None
    expected_delivery_date: date | None
    status: str
    notes: str | None
    include_in_budget: bool


class PublicityRequirementCreate(BaseModel):
    program_id: str
    activity_id: str | None = None
    budget_item_id: str | None = None
    content_type: str = Field(min_length=1, max_length=100)
    format: str | None = Field(default=None, max_length=100)
    quantity: int = Field(default=1, ge=1)
    owner_name: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    expected_completion_date: date | None = None
    publish_date: date | None = None
    status: PublicityStatus = "pending"
    notes: str | None = None


class PublicityRequirementUpdate(BaseModel):
    activity_id: str | None = None
    budget_item_id: str | None = None
    content_type: str | None = Field(default=None, min_length=1, max_length=100)
    format: str | None = Field(default=None, max_length=100)
    quantity: int | None = Field(default=None, ge=1)
    owner_name: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    expected_completion_date: date | None = None
    publish_date: date | None = None
    status: PublicityStatus | None = None
    notes: str | None = None


class PublicityRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    program_id: str
    activity_id: str | None
    budget_item_id: str | None
    content_type: str
    format: str | None
    quantity: int
    owner_name: str | None
    start_date: date | None
    expected_completion_date: date | None
    publish_date: date | None
    status: str
    notes: str | None


class RequirementsSummary(BaseModel):
    program_id: str
    budget_total: Decimal
    budget_sheet_count: int
    material_total: int
    material_open: int
    material_done: int
    publicity_total: int
    publicity_open: int
    publicity_done: int
