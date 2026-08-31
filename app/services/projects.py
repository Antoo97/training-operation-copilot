from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cohort, Milestone, Program, Project, ProjectMilestone, ProjectTask, ProjectTemplate, TemplateTask
from app.schemas import ActivityCreate, ProgramCreate, ProjectCreate


class TemplateNotFoundError(ValueError):
    pass


def create_project(db: Session, payload: ProjectCreate) -> Project:
    template = db.get(ProjectTemplate, payload.template_id)
    if template is None:
        raise TemplateNotFoundError(payload.template_id)
    if payload.event_date < payload.start_date:
        raise ValueError("event_date must be on or after start_date")

    template_milestones = db.scalars(
        select(Milestone)
        .where(Milestone.template_id == payload.template_id)
        .order_by(Milestone.sort_order)
    ).all()
    template_tasks = db.scalars(
        select(TemplateTask)
        .where(TemplateTask.template_id == payload.template_id)
        .order_by(TemplateTask.milestone_id, TemplateTask.sort_order)
    ).all()

    program = Program(
        id=str(uuid4()),
        name=payload.name,
        program_type="annual_continuous",
        start_date=payload.start_date,
        end_date=payload.event_date,
        status="active",
    )
    db.add(program)
    project = Project(
        id=str(uuid4()),
        name=payload.name,
        type=template.type,
        start_date=payload.start_date,
        event_date=payload.event_date,
        status="active",
        template_id=template.id,
        program=program,
        activity_type=template.type,
        end_date=payload.event_date,
    )
    db.add(project)

    project_milestones: dict[str, ProjectMilestone] = {}
    for milestone in template_milestones:
        instance = ProjectMilestone(
            id=str(uuid4()),
            template_milestone_id=milestone.id,
            code=milestone.code,
            name=milestone.name,
            phase=milestone.phase,
            start_date=payload.event_date + timedelta(days=milestone.offset_days),
            deadline=payload.event_date + timedelta(days=milestone.offset_days),
            required=milestone.required,
            status="active",
            sort_order=milestone.sort_order,
        )
        project.milestones.append(instance)
        project_milestones[milestone.id] = instance

    for template_task in template_tasks:
        milestone = project_milestones[template_task.milestone_id]
        project.tasks.append(
            ProjectTask(
                id=str(uuid4()),
                template_task_id=template_task.id,
                milestone_id=template_task.milestone_id,
                project_milestone=milestone,
                title=template_task.title,
                status="todo",
                start_date=milestone.deadline,
                deadline=milestone.deadline,
                required=template_task.required,
                sort_order=template_task.sort_order,
            )
        )

    db.commit()
    db.refresh(project)
    return project


def create_program(db: Session, payload: ProgramCreate) -> Program:
    if payload.end_date < payload.start_date:
        raise ValueError("end_date must be on or after start_date")
    program = Program(id=str(uuid4()), status="active", **payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


def create_activity(db: Session, program: Program, payload: ActivityCreate) -> Project:
    if payload.end_date < payload.start_date:
        raise ValueError("end_date must be on or after start_date")
    if payload.cohort_id:
        cohort = db.get(Cohort, payload.cohort_id)
        if cohort is None or cohort.program_id != program.id:
            raise ValueError("cohort does not belong to program")
    if payload.activity_type == "offline_training":
        if not payload.template_id or not payload.event_date:
            raise ValueError("offline training requires template_id and event_date")
        template = db.get(ProjectTemplate, payload.template_id)
        if template is None or template.type != "offline_training":
            raise TemplateNotFoundError(payload.template_id)
        base = create_project(
            db,
            ProjectCreate(
                name=payload.name,
                template_id=payload.template_id,
                start_date=payload.start_date,
                event_date=payload.event_date,
            ),
        )
        # create_project keeps the v1 standalone behavior; v2 re-parents the
        # Activity and removes the empty compatibility Program it created.
        compatibility_program = base.program
        base.program = program
        base.program_id = program.id
        base.cohort_id = payload.cohort_id
        base.end_date = payload.end_date
        base.owner_name = payload.owner_name
        base.location = payload.location
        base.business_unit = payload.business_unit
        base.participant_count = payload.participant_count
        if compatibility_program is not None:
            db.delete(compatibility_program)
        db.commit()
        db.refresh(base)
        return base
    if payload.template_id is not None or payload.event_date is not None:
        raise ValueError("lightweight activity must not use template_id or event_date")
    activity = Project(
        id=str(uuid4()),
        program_id=program.id,
        cohort_id=payload.cohort_id,
        name=payload.name.strip(),
        type=payload.activity_type,
        activity_type=payload.activity_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        event_date=None,
        template_id=None,
        owner_name=payload.owner_name,
        location=payload.location,
        business_unit=payload.business_unit,
        participant_count=payload.participant_count,
        status="active",
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def backfill_project_milestones(db: Session) -> None:
    """Create project milestone instances for projects created before this model existed."""
    projects = db.scalars(select(Project)).all()
    for project in projects:
        existing = {
            item.template_milestone_id: item
            for item in db.scalars(
                select(ProjectMilestone).where(ProjectMilestone.project_id == project.id)
            ).all()
            if item.template_milestone_id
        }
        template_milestones = db.scalars(
            select(Milestone)
            .where(Milestone.template_id == project.template_id)
            .order_by(Milestone.sort_order)
        ).all()
        for milestone in template_milestones:
            instance = existing.get(milestone.id)
            if instance is None:
                instance = ProjectMilestone(
                    id=str(uuid4()),
                    project_id=project.id,
                    template_milestone_id=milestone.id,
                    code=milestone.code,
                    name=milestone.name,
                    phase=milestone.phase,
                    start_date=project.event_date + timedelta(days=milestone.offset_days),
                    deadline=project.event_date + timedelta(days=milestone.offset_days),
                    required=milestone.required,
                    status="active",
                    sort_order=milestone.sort_order,
                )
                db.add(instance)
                db.flush()
                existing[milestone.id] = instance
            tasks = db.scalars(
                select(ProjectTask).where(
                    ProjectTask.project_id == project.id,
                    ProjectTask.milestone_id == milestone.id,
                    ProjectTask.project_milestone_id.is_(None),
                )
            ).all()
            for task in tasks:
                task.project_milestone_id = instance.id
    db.commit()
