from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(64))
    start_date: Mapped[date] = mapped_column(Date)
    event_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active")
    template_id: Mapped[str] = mapped_column(ForeignKey("project_templates.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    tasks: Mapped[list[ProjectTask]] = relationship(back_populates="project", cascade="all, delete-orphan")
    milestones: Mapped[list[ProjectMilestone]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectMilestone.sort_order"
    )


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"
    __table_args__ = (UniqueConstraint("project_id", "template_milestone_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    template_milestone_id: Mapped[str | None] = mapped_column(ForeignKey("milestones.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    phase: Mapped[str] = mapped_column(String(100))
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
    deadline: Mapped[date] = mapped_column(Date)
    required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="tasks")
    milestone: Mapped[Milestone] = relationship()
    project_milestone: Mapped[ProjectMilestone | None] = relationship(back_populates="tasks")

    @property
    def milestone_code(self) -> str:
        return self.project_milestone.code if self.project_milestone else self.milestone.code

    @property
    def milestone_name(self) -> str:
        return self.project_milestone.name if self.project_milestone else self.milestone.name
