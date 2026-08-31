from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ProjectTemplate(Base):
    __tablename__ = "project_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(64), index=True)
    anchor_type: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))

    milestones: Mapped[list[Milestone]] = relationship(back_populates="template")


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (UniqueConstraint("template_id", "code"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("project_templates.id"), index=True)
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    phase: Mapped[str] = mapped_column(String(100))
    offset_days: Mapped[int] = mapped_column(Integer)
    required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    risk_if_missing: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_rule_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer)

    template: Mapped[ProjectTemplate] = relationship(back_populates="milestones")
    tasks: Mapped[list[TemplateTask]] = relationship(back_populates="milestone")


class TemplateTask(Base):
    __tablename__ = "template_tasks"
    __table_args__ = (UniqueConstraint("template_id", "code"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("project_templates.id"), index=True)
    milestone_id: Mapped[str] = mapped_column(ForeignKey("milestones.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(300))
    required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer)

    milestone: Mapped[Milestone] = relationship(back_populates="tasks")


class RiskRule(Base):
    __tablename__ = "risk_rules"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    risk_type: Mapped[str] = mapped_column(String(64))
    target_milestone_id: Mapped[str] = mapped_column(ForeignKey("milestones.id"))
    trigger_type: Mapped[str] = mapped_column(String(100))
    trigger_config: Mapped[dict[str, Any]] = mapped_column(JSON)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    severity_strategy: Mapped[str] = mapped_column(String(32))
    recommended_action: Mapped[str] = mapped_column(Text)
    source_trigger: Mapped[str] = mapped_column(Text)


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    program_type: Mapped[str] = mapped_column(String(64), default="annual_continuous", index=True)
    owner_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    current_phase: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    participant_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cohorts: Mapped[list[Cohort]] = relationship(back_populates="program", cascade="all, delete-orphan")
    activities: Mapped[list[Project]] = relationship(back_populates="program")
    budget_sheets: Mapped[list[BudgetSheet]] = relationship(back_populates="program", cascade="all, delete-orphan")
    material_requirements: Mapped[list[MaterialRequirement]] = relationship(back_populates="program", cascade="all, delete-orphan")
    publicity_requirements: Mapped[list[PublicityRequirement]] = relationship(back_populates="program", cascade="all, delete-orphan")
    alerts: Mapped[list[Alert]] = relationship(back_populates="program", cascade="all, delete-orphan")
    classes: Mapped[list[TrainingClass]] = relationship(back_populates="program", cascade="all, delete-orphan", order_by="TrainingClass.start_date")


class Cohort(Base):
    __tablename__ = "cohorts"
    __table_args__ = (UniqueConstraint("program_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    business_unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    participant_count: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    graduated: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    program: Mapped[Program] = relationship(back_populates="cohorts")
    activities: Mapped[list[Project]] = relationship(back_populates="cohort")


class TrainingClass(Base):
    __tablename__ = "training_classes"
    __table_args__ = (UniqueConstraint("program_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    participant_count: Mapped[int] = mapped_column(Integer, default=0)
    business_unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    program: Mapped[Program] = relationship(back_populates="classes")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[date] = mapped_column(Date)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    template_id: Mapped[str | None] = mapped_column(ForeignKey("project_templates.id"), nullable=True)
    program_id: Mapped[str | None] = mapped_column(ForeignKey("programs.id"), nullable=True, index=True)
    cohort_id: Mapped[str | None] = mapped_column(ForeignKey("cohorts.id"), nullable=True, index=True)
    activity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    owner_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    business_unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    participant_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_phase: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    program: Mapped[Program | None] = relationship(back_populates="activities")
    cohort: Mapped[Cohort | None] = relationship(back_populates="activities")
    tasks: Mapped[list[ProjectTask]] = relationship(back_populates="project", cascade="all, delete-orphan")
    milestones: Mapped[list[ProjectMilestone]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectMilestone.sort_order"
    )
    budget_sheets: Mapped[list[BudgetSheet]] = relationship(back_populates="activity")
    material_requirements: Mapped[list[MaterialRequirement]] = relationship(back_populates="activity")
    publicity_requirements: Mapped[list[PublicityRequirement]] = relationship(back_populates="activity")


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"
    __table_args__ = (UniqueConstraint("project_id", "template_milestone_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    template_milestone_id: Mapped[str | None] = mapped_column(ForeignKey("milestones.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    phase: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date)
    deadline: Mapped[date] = mapped_column(Date)
    required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    sort_order: Mapped[int] = mapped_column(Integer)

    project: Mapped[Project] = relationship(back_populates="milestones")
    tasks: Mapped[list[ProjectTask]] = relationship(back_populates="project_milestone")


class ProjectTask(Base):
    __tablename__ = "project_tasks"
    __table_args__ = (UniqueConstraint("project_id", "template_task_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    template_task_id: Mapped[str | None] = mapped_column(ForeignKey("template_tasks.id"), nullable=True)
    milestone_id: Mapped[str | None] = mapped_column(ForeignKey("milestones.id"), nullable=True)
    project_milestone_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_milestones.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="todo")
    start_date: Mapped[date] = mapped_column(Date)
    deadline: Mapped[date] = mapped_column(Date)
    required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    progress_mode: Mapped[str] = mapped_column(String(16), default="manual")
    progress_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrospective_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_progress_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="tasks")
    milestone: Mapped[Milestone] = relationship()
    project_milestone: Mapped[ProjectMilestone | None] = relationship(back_populates="tasks")
    subtasks: Mapped[list[Subtask]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="Subtask.sort_order"
    )
    resource_links: Mapped[list[TaskResourceLink]] = relationship(back_populates="task", cascade="all, delete-orphan")

    @property
    def milestone_code(self) -> str:
        return self.project_milestone.code if self.project_milestone else self.milestone.code

    @property
    def milestone_name(self) -> str:
        return self.project_milestone.name if self.project_milestone else self.milestone.name

    @property
    def auto_progress_percent(self) -> int:
        active = [item for item in self.subtasks if item.status != "cancelled"]
        if not active:
            return 100 if self.status == "done" else self.progress_percent
        return round(sum(item.progress_percent for item in active) / len(active))

    @property
    def effective_progress_percent(self) -> int:
        return self.auto_progress_percent if self.progress_mode == "auto" else self.progress_percent

    @property
    def resource_count(self) -> int:
        return len(self.resource_links)


class Subtask(Base):
    __tablename__ = "subtasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("project_tasks.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    owner: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="todo")
    start_date: Mapped[date] = mapped_column(Date)
    deadline: Mapped[date] = mapped_column(Date)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    task: Mapped[ProjectTask] = relationship(back_populates="subtasks")


class ProjectActivityLog(Base):
    __tablename__ = "project_activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    cohort_id: Mapped[str | None] = mapped_column(ForeignKey("cohorts.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_name: Mapped[str] = mapped_column(String(100), default="系统用户")
    module: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    changes_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(32), default="system")
    is_manual_entry: Mapped[bool] = mapped_column(Boolean, default=False)


class ReferencePrice(Base):
    __tablename__ = "reference_prices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    expense_name: Mapped[str] = mapped_column(String(200), index=True)
    price_type: Mapped[str] = mapped_column(String(16), default="unit")
    unit_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BudgetSheet(Base):
    __tablename__ = "budget_sheets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    owner_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    planned_apply_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_apply_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_confirmation", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    program: Mapped[Program] = relationship(back_populates="budget_sheets")
    activity: Mapped[Project | None] = relationship(back_populates="budget_sheets")
    items: Mapped[list[BudgetItem]] = relationship(back_populates="budget_sheet", cascade="all, delete-orphan", order_by="BudgetItem.sort_order")

    @property
    def estimated_total(self):
        return sum((item.estimated_amount for item in self.items if item.is_involved), start=0)


class BudgetItem(Base):
    __tablename__ = "budget_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    budget_sheet_id: Mapped[str] = mapped_column(ForeignKey("budget_sheets.id"), index=True)
    expense_name: Mapped[str] = mapped_column(String(200))
    is_involved: Mapped[bool] = mapped_column(Boolean, default=True)
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), default=1)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_price_id: Mapped[str | None] = mapped_column(ForeignKey("reference_prices.id"), nullable=True)
    reference_unit_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    reference_min_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    reference_max_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_unit_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    amount_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="pending_submission", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    budget_sheet: Mapped[BudgetSheet] = relationship(back_populates="items")
    reference_price: Mapped[ReferencePrice | None] = relationship()


class MaterialRequirement(Base):
    __tablename__ = "material_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    budget_item_id: Mapped[str | None] = mapped_column(ForeignKey("budget_items.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    specification: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    content_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_confirmation", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_in_budget: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    program: Mapped[Program] = relationship(back_populates="material_requirements")
    activity: Mapped[Project | None] = relationship(back_populates="material_requirements")
    budget_item: Mapped[BudgetItem | None] = relationship()


class PublicityRequirement(Base):
    __tablename__ = "publicity_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    budget_item_id: Mapped[str | None] = mapped_column(ForeignKey("budget_items.id"), nullable=True)
    content_type: Mapped[str] = mapped_column(String(100))
    format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    owner_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="requirement_confirmation", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    program: Mapped[Program] = relationship(back_populates="publicity_requirements")
    activity: Mapped[Project | None] = relationship(back_populates="publicity_requirements")
    budget_item: Mapped[BudgetItem | None] = relationship()


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("program_id", "rule_code", "source_entity_type", "source_entity_id", name="uq_open_alert_source"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    rule_code: Mapped[str] = mapped_column(String(64), index=True)
    alert_type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    current_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recommended_action: Mapped[str] = mapped_column(Text)
    source_entity_type: Mapped[str] = mapped_column(String(32))
    source_entity_id: Mapped[str] = mapped_column(String(36))
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    program: Mapped[Program] = relationship(back_populates="alerts")


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    resource_type: Mapped[str] = mapped_column(String(32), default="link")
    url: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    file_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    task_links: Mapped[list[TaskResourceLink]] = relationship(back_populates="resource", cascade="all, delete-orphan")


class TaskResourceLink(Base):
    __tablename__ = "task_resource_links"
    __table_args__ = (UniqueConstraint("task_id", "resource_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("project_tasks.id"), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    relation_type: Mapped[str] = mapped_column(String(32), default="reference")

    task: Mapped[ProjectTask] = relationship(back_populates="resource_links")
    resource: Mapped[Resource] = relationship(back_populates="task_links")
