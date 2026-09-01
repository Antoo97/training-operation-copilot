from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
import base64
import os
import secrets
from uuid import uuid4
from pathlib import Path

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import Base, SessionLocal, engine, ensure_schema_compatibility, get_db
from app.models import (
    Alert, BudgetItem, BudgetSheet, Cohort, MaterialRequirement, Program, Project, TrainingClass,
    ProjectActivityLog, ProjectMilestone, ProjectTask, ProjectTemplate,
    PublicityRequirement, ReferencePrice, Resource, Subtask, TaskResourceLink,
)
from app.schemas import (
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectMilestoneCreate,
    ProjectMilestoneRead,
    ProjectMilestoneUpdate,
    ProjectTaskCreate,
    ProjectTaskRead,
    ActivityCreate,
    ActivityUpdate,
    CohortCreate,
    CohortRead,
    CohortUpdate,
    TrainingClassCreate,
    TrainingClassRead,
    TrainingClassUpdate,
    ProgramCreate,
    ProgramRead,
    ProgramSummary,
    ProgramUpdate,
    ActivityLogCreate,
    ActivityLogRead,
    SubtaskCreate,
    SubtaskRead,
    SubtaskUpdate,
    TaskBulkUpdate,
    TaskV2Read,
    TaskV2Update,
    TaskOwnerUpdate,
    TaskRequiredUpdate,
    TaskStatusUpdate,
    BudgetItemCreate,
    BudgetItemRead,
    BudgetItemUpdate,
    BudgetSheetCreate,
    BudgetSheetRead,
    BudgetSheetUpdate,
    MaterialRequirementCreate,
    MaterialRequirementRead,
    MaterialRequirementUpdate,
    PublicityRequirementCreate,
    PublicityRequirementRead,
    PublicityRequirementUpdate,
    ReferencePriceCreate,
    ReferencePriceRead,
    ReferencePriceUpdate,
    RequirementsSummary,
)
from app.services.projects import (
    TemplateNotFoundError,
    backfill_project_milestones,
    create_activity,
    create_program,
    create_project,
)
from app.services.seed import load_offline_training_seed, load_reference_price_seed
from app.services.activity_logs import add_activity_log, clean_actor_name, task_program_id
from app.services.requirements import (
    create_budget_item, create_budget_sheet, get_budget_sheet, program_budget_total,
    requirements_counts, update_budget_item, validate_activity, validate_budget_item_link,
)
from app.services.dashboard import dashboard, focus_items, load_program
from app.services.alerts import evaluate as evaluate_alerts
from app.services.export_ics import calendar as build_calendar


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    with SessionLocal() as db:
        load_offline_training_seed(db)
        load_reference_price_seed(db)
        backfill_project_milestones(db)
    yield


app = FastAPI(title="Training Operation Copilot", version="0.2.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def optional_password_protection(request: Request, call_next):
    """Protect cloud deployments while keeping local development password-free."""
    password = os.getenv("TRAINING_COPILOT_PASSWORD")
    if not password or request.url.path == "/health":
        return await call_next(request)

    expected_user = os.getenv("TRAINING_COPILOT_USERNAME", "admin")
    authorization = request.headers.get("Authorization", "")
    authenticated = False
    if authorization.startswith("Basic "):
        try:
            decoded = base64.b64decode(authorization[6:]).decode("utf-8")
            username, supplied_password = decoded.split(":", 1)
            authenticated = secrets.compare_digest(username, expected_user) and secrets.compare_digest(
                supplied_password, password
            )
        except (ValueError, UnicodeDecodeError):
            authenticated = False
    if not authenticated:
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Training Copilot"'},
            content="需要输入工作台账号和密码",
        )
    return await call_next(request)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/templates")
def list_templates(db: Session = Depends(get_db)) -> list[dict[str, str]]:
    templates = db.scalars(select(ProjectTemplate).order_by(ProjectTemplate.name)).all()
    return [{"id": item.id, "name": item.name, "type": item.type, "version": item.version} for item in templates]


@app.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def post_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    try:
        return create_project(db, payload)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail="template not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/projects", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())).all())


@app.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.scalar(
        select(Project)
        .options(
            selectinload(Project.milestones),
            selectinload(Project.tasks).selectinload(ProjectTask.project_milestone),
            selectinload(Project.tasks).selectinload(ProjectTask.subtasks),
            selectinload(Project.tasks).selectinload(ProjectTask.resource_links),
        )
        .where(Project.id == project_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project(project_id: str, db: Session = Depends(get_db)) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    program = db.get(Program, project.program_id) if project.program_id else None
    sibling_count = db.scalar(
        select(func.count(Project.id)).where(
            Project.program_id == project.program_id,
            Project.id != project.id,
        )
    ) if project.program_id else 0
    db.delete(project)
    # The v1 endpoint represents a whole project. Its automatically-created
    # compatibility Program must not remain as an empty item after deletion.
    if program is not None and not sibling_count:
        db.delete(program)
    db.commit()


@app.patch("/tasks/{task_id}/status", response_model=ProjectTaskRead)
def patch_task_status(task_id: str, payload: TaskStatusUpdate, db: Session = Depends(get_db)) -> ProjectTask:
    task = db.get(ProjectTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    task.status = payload.status
    task.progress_percent = 100 if payload.status == "done" else 0
    task.last_progress_at = datetime.now(UTC)
    task.completed_at = datetime.now(UTC) if payload.status == "done" else None
    db.commit()
    db.refresh(task)
    return task


@app.patch("/tasks/{task_id}/owner", response_model=ProjectTaskRead)
def patch_task_owner(task_id: str, payload: TaskOwnerUpdate, db: Session = Depends(get_db)) -> ProjectTask:
    task = db.get(ProjectTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    owner = payload.owner.strip() if payload.owner else None
    task.owner = owner or None
    db.commit()
    db.refresh(task)
    return task


@app.patch("/tasks/{task_id}/required", response_model=ProjectTaskRead)
def patch_task_required(task_id: str, payload: TaskRequiredUpdate, db: Session = Depends(get_db)) -> ProjectTask:
    task = db.get(ProjectTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    task.required = payload.required
    db.commit()
    db.refresh(task)
    return task


@app.post("/projects/{project_id}/tasks", response_model=ProjectTaskRead, status_code=status.HTTP_201_CREATED)
def post_project_task(project_id: str, payload: ProjectTaskCreate, db: Session = Depends(get_db)) -> ProjectTask:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    milestone = db.get(ProjectMilestone, payload.project_milestone_id)
    if milestone is None or milestone.project_id != project.id or milestone.status != "active":
        raise HTTPException(status_code=422, detail="milestone does not belong to active project milestones")
    owner = payload.owner.strip() if payload.owner else None
    task = ProjectTask(
        id=str(uuid4()),
        project_id=project.id,
        template_task_id=None,
        milestone_id=milestone.template_milestone_id,
        project_milestone_id=milestone.id,
        title=payload.title.strip(),
        owner=owner or None,
        status="todo",
        start_date=milestone.start_date,
        deadline=milestone.deadline,
        required=payload.required,
    )
    db.add(task)
    db.flush()
    _sync_milestone_deadline(db, task.project_milestone_id)
    db.commit()
    db.refresh(task)
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_task(task_id: str, db: Session = Depends(get_db)) -> None:
    task = db.get(ProjectTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    task.status = "cancelled"
    task.completed_at = None
    milestone_id = task.project_milestone_id
    db.flush()
    _sync_milestone_deadline(db, milestone_id)
    db.commit()


@app.post(
    "/projects/{project_id}/milestones",
    response_model=ProjectMilestoneRead,
    status_code=status.HTTP_201_CREATED,
)
def post_project_milestone(
    project_id: str, payload: ProjectMilestoneCreate, db: Session = Depends(get_db)
) -> ProjectMilestone:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    max_order = db.scalar(
        select(func.max(ProjectMilestone.sort_order)).where(ProjectMilestone.project_id == project.id)
    ) or 0
    milestone = ProjectMilestone(
        id=str(uuid4()),
        project_id=project.id,
        template_milestone_id=None,
        code=f"CUSTOM-{max_order + 1}",
        name=payload.name.strip(),
        phase="自定义节点",
        start_date=payload.start_date or payload.deadline,
        deadline=payload.deadline,
        required=payload.required,
        status="active",
        sort_order=max_order + 1,
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@app.patch("/project-milestones/{milestone_id}", response_model=ProjectMilestoneRead)
def patch_project_milestone(
    milestone_id: str, payload: ProjectMilestoneUpdate, db: Session = Depends(get_db)
) -> ProjectMilestone:
    milestone = db.get(ProjectMilestone, milestone_id)
    if milestone is None or milestone.status != "active":
        raise HTTPException(status_code=404, detail="project milestone not found")
    if payload.name is not None:
        milestone.name = payload.name.strip()
    if payload.required is not None:
        milestone.required = payload.required
    if payload.start_date is not None:
        milestone.start_date = payload.start_date
    if payload.deadline is not None and payload.deadline != milestone.deadline:
        milestone.deadline = payload.deadline
        tasks = db.scalars(
            select(ProjectTask).where(
                ProjectTask.project_milestone_id == milestone.id,
                ProjectTask.status != "cancelled",
            )
        ).all()
        for task in tasks:
            task.deadline = payload.deadline
    db.commit()
    db.refresh(milestone)
    return milestone


@app.delete("/project-milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_milestone(milestone_id: str, db: Session = Depends(get_db)) -> None:
    milestone = db.get(ProjectMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="project milestone not found")
    milestone.status = "removed"
    tasks = db.scalars(
        select(ProjectTask).where(ProjectTask.project_milestone_id == milestone.id)
    ).all()
    for task in tasks:
        task.status = "cancelled"
        task.completed_at = None
    db.commit()


@app.get("/api/v2/programs", response_model=list[ProgramSummary])
def list_programs(include_archived: bool = False, db: Session = Depends(get_db)) -> list[Program]:
    query = select(Program)
    if not include_archived:
        query = query.where(Program.status != "archived")
    return list(
        db.scalars(query.order_by(Program.created_at.desc())).all()
    )


@app.post("/api/v2/programs", response_model=ProgramSummary, status_code=status.HTTP_201_CREATED)
def post_program(payload: ProgramCreate, db: Session = Depends(get_db)) -> Program:
    try:
        return create_program(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v2/programs/{program_id}", response_model=ProgramRead)
def get_program(program_id: str, db: Session = Depends(get_db)) -> Program:
    program = db.scalar(
        select(Program)
        .options(selectinload(Program.cohorts), selectinload(Program.activities), selectinload(Program.classes))
        .where(Program.id == program_id)
    )
    if program is None:
        raise HTTPException(status_code=404, detail="program not found")
    return program


@app.patch("/api/v2/programs/{program_id}", response_model=ProgramSummary)
def patch_program(program_id: str, payload: ProgramUpdate, db: Session = Depends(get_db)) -> Program:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="program not found")
    values = payload.model_dump(exclude_unset=True)
    start_date = values.get("start_date", program.start_date)
    end_date = values.get("end_date", program.end_date)
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(program, key, value)
    if values.get("status") and values["status"] != "archived":
        program.archived_at = None
        for activity in program.activities:
            if activity.status == "archived":
                activity.status = "active"
                activity.archived_at = None
    db.commit()
    db.refresh(program)
    return program


@app.delete("/api/v2/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_program(program_id: str, db: Session = Depends(get_db)) -> None:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="program not found")
    program.status = "archived"
    program.archived_at = datetime.now(UTC)
    for activity in program.activities:
        activity.status = "archived"
        activity.archived_at = datetime.now(UTC)
    db.commit()


@app.post(
    "/api/v2/programs/{program_id}/cohorts",
    response_model=CohortRead,
    status_code=status.HTTP_201_CREATED,
)
def post_cohort(program_id: str, payload: CohortCreate, db: Session = Depends(get_db)) -> Cohort:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="program not found")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")
    cohort = Cohort(id=str(uuid4()), program_id=program.id, status="active", **payload.model_dump())
    db.add(cohort)
    db.commit()
    db.refresh(cohort)
    return cohort


@app.patch("/api/v2/cohorts/{cohort_id}", response_model=CohortRead)
def patch_cohort(cohort_id: str, payload: CohortUpdate, db: Session = Depends(get_db)) -> Cohort:
    cohort = db.get(Cohort, cohort_id)
    if cohort is None:
        raise HTTPException(status_code=404, detail="cohort not found")
    values = payload.model_dump(exclude_unset=True)
    start_date = values.get("start_date", cohort.start_date)
    end_date = values.get("end_date", cohort.end_date)
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")
    for key, value in values.items():
        setattr(cohort, key, value)
    db.commit()
    db.refresh(cohort)
    return cohort


@app.post("/api/v2/programs/{program_id}/classes", response_model=TrainingClassRead, status_code=201)
def post_training_class(program_id: str, payload: TrainingClassCreate, db: Session = Depends(get_db)) -> TrainingClass:
    program = db.get(Program, program_id)
    if program is None or program.status == "archived":
        raise HTTPException(status_code=404, detail="培养项目不存在")
    start_date = payload.start_date or program.start_date
    end_date = payload.end_date or program.end_date
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="班级结束日期不能早于开始日期")
    item = TrainingClass(
        id=str(uuid4()), program_id=program.id, name=payload.name.strip(), start_date=start_date,
        end_date=end_date, participant_count=payload.participant_count,
        business_unit=payload.business_unit.strip() if payload.business_unit else None,
    )
    db.add(item)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail="同一项目下班级名称不能重复") from exc
    db.refresh(item)
    return item


@app.patch("/api/v2/classes/{class_id}", response_model=TrainingClassRead)
def patch_training_class(class_id: str, payload: TrainingClassUpdate, db: Session = Depends(get_db)) -> TrainingClass:
    item = db.get(TrainingClass, class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    values = payload.model_dump(exclude_unset=True)
    start_date = values.get("start_date", item.start_date)
    end_date = values.get("end_date", item.end_date)
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="班级结束日期不能早于开始日期")
    for key, value in values.items():
        setattr(item, key, value.strip() or None if isinstance(value, str) else value)
    db.commit(); db.refresh(item)
    return item


@app.delete("/api/v2/classes/{class_id}", status_code=204)
def remove_training_class(class_id: str, db: Session = Depends(get_db)) -> None:
    item = db.get(TrainingClass, class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    db.delete(item); db.commit()


@app.post(
    "/api/v2/programs/{program_id}/activities",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def post_activity(program_id: str, payload: ActivityCreate, db: Session = Depends(get_db)) -> Project:
    program = db.get(Program, program_id)
    if program is None or program.status == "archived":
        raise HTTPException(status_code=404, detail="program not found")
    try:
        return create_activity(db, program, payload)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail="template not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.patch("/api/v2/activities/{activity_id}", response_model=ProjectRead)
def patch_activity(activity_id: str, payload: ActivityUpdate, db: Session = Depends(get_db)) -> Project:
    activity = db.get(Project, activity_id)
    if activity is None or activity.program_id is None:
        raise HTTPException(status_code=404, detail="培养活动不存在")
    values = payload.model_dump(exclude_unset=True)
    start_date = values.get("start_date", activity.start_date)
    end_date = values.get("end_date", activity.end_date or activity.start_date)
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="培养活动结束日期不能早于开始日期")
    if "cohort_id" in values and values["cohort_id"] is not None:
        cohort = db.get(Cohort, values["cohort_id"])
        if cohort is None or cohort.program_id != activity.program_id:
            raise HTTPException(status_code=422, detail="届别不属于当前培养项目")
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(activity, key, value)
    if (activity.activity_type or activity.type) == "offline_training":
        activity.event_date = activity.start_date
    db.commit()
    db.refresh(activity)
    return activity


@app.delete("/api/v2/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_activity(activity_id: str, db: Session = Depends(get_db)) -> None:
    activity = db.get(Project, activity_id)
    if activity is None or activity.program_id is None:
        raise HTTPException(status_code=404, detail="培养活动不存在")
    activity.status = "archived"
    activity.archived_at = datetime.now(UTC)
    db.commit()


@app.get("/api/v2/activities/{activity_id}", response_model=ProjectRead)
def get_activity(activity_id: str, db: Session = Depends(get_db)) -> Project:
    return get_project(activity_id, db)


def _task_v2(db: Session, task_id: str) -> ProjectTask:
    task = db.scalar(
        select(ProjectTask).options(selectinload(ProjectTask.subtasks), selectinload(ProjectTask.resource_links)).where(ProjectTask.id == task_id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


def _sync_milestone_deadline(db: Session, milestone_id: str | None) -> None:
    if not milestone_id:
        return
    latest = db.scalar(select(func.max(ProjectTask.deadline)).where(
        ProjectTask.project_milestone_id == milestone_id,
        ProjectTask.status != "cancelled",
    ))
    milestone = db.get(ProjectMilestone, milestone_id)
    if milestone is not None and latest is not None:
        milestone.deadline = latest


def _sync_task_deadline_from_subtasks(db: Session, task: ProjectTask) -> None:
    """Roll the latest active branch-task deadline up to its parent task and milestone."""
    latest = db.scalar(select(func.max(Subtask.deadline)).where(
        Subtask.task_id == task.id,
        Subtask.status != "cancelled",
    ))
    if latest is not None:
        task.deadline = max(latest, task.start_date)
    _sync_milestone_deadline(db, task.project_milestone_id)


@app.get("/api/v2/tasks/{task_id}", response_model=TaskV2Read)
def get_task_v2(task_id: str, db: Session = Depends(get_db)) -> ProjectTask:
    return _task_v2(db, task_id)


@app.patch("/api/v2/tasks/{task_id}", response_model=TaskV2Read)
def patch_task_v2(
    task_id: str,
    payload: TaskV2Update,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> ProjectTask:
    task = _task_v2(db, task_id)
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return task
    start_date = values.get("start_date", task.start_date)
    deadline = values.get("deadline", task.deadline)
    if deadline < start_date:
        raise HTTPException(status_code=422, detail="deadline must be on or after start_date")
    requested_status = values.get("status", task.status)
    if values.get("quality_score") is not None and requested_status != "done":
        raise HTTPException(status_code=422, detail="quality score is available after task completion")
    changes: dict[str, dict[str, object]] = {}
    for key, value in values.items():
        if isinstance(value, str) and key not in {"status", "progress_mode"}:
            value = value.strip() or None
        old_value = getattr(task, key)
        if old_value != value:
            changes[key] = {"old": old_value.isoformat() if hasattr(old_value, "isoformat") else old_value, "new": value.isoformat() if hasattr(value, "isoformat") else value}
            setattr(task, key, value)
    if "status" in values:
        task.completed_at = datetime.now(UTC) if task.status == "done" else None
        if task.status == "done":
            task.progress_percent = 100
        task.last_progress_at = datetime.now(UTC)
    if any(key in values for key in {"progress_percent", "progress_note", "progress_mode"}):
        task.last_progress_at = datetime.now(UTC)
    if changes:
        program_id = task_program_id(db, task.project_id)
        add_activity_log(
            db,
            program_id=program_id,
            activity_id=task.project_id,
            actor_name=actor_name,
            module="task",
            action="updated",
            summary=f"更新任务：{task.title}",
            entity_type="task",
            entity_id=task.id,
            changes=changes,
            source="task_update",
        )
    _sync_milestone_deadline(db, task.project_milestone_id)
    program_id = task_program_id(db, task.project_id)
    db.commit()
    evaluate_alerts(db, program_id)
    return _task_v2(db, task.id)


@app.post("/api/v2/tasks/bulk", response_model=list[TaskV2Read])
def bulk_update_tasks(
    payload: TaskBulkUpdate,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> list[ProjectTask]:
    unique_ids = list(dict.fromkeys(payload.task_ids))
    tasks = list(
        db.scalars(
            select(ProjectTask).options(selectinload(ProjectTask.subtasks)).where(ProjectTask.id.in_(unique_ids))
        ).all()
    )
    if len(tasks) != len(unique_ids):
        raise HTTPException(status_code=404, detail="one or more tasks not found")
    now = datetime.now(UTC)
    for task in tasks:
        task.status = "done"
        task.progress_percent = 100
        task.completed_at = now
        task.last_progress_at = now
        add_activity_log(
            db,
            program_id=task_program_id(db, task.project_id),
            activity_id=task.project_id,
            actor_name=actor_name,
            module="task",
            action="completed",
            summary=f"批量完成任务：{task.title}",
            entity_type="task",
            entity_id=task.id,
            changes={"status": {"old": "未完成", "new": "done"}},
            source="task_update",
        )
    program_ids = {task_program_id(db, task.project_id) for task in tasks}
    db.commit()
    for program_id in program_ids: evaluate_alerts(db, program_id)
    return [_task_v2(db, task.id) for task in tasks]


@app.post("/api/v2/tasks/{task_id}/subtasks", response_model=SubtaskRead, status_code=status.HTTP_201_CREATED)
def post_subtask(
    task_id: str,
    payload: SubtaskCreate,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> Subtask:
    task = _task_v2(db, task_id)
    if payload.deadline < payload.start_date:
        raise HTTPException(status_code=422, detail="deadline must be on or after start_date")
    subtask = Subtask(
        id=str(uuid4()),
        task_id=task.id,
        status="todo",
        progress_percent=0,
        sort_order=len(task.subtasks) + 1,
        **payload.model_dump(),
    )
    task.progress_mode = "auto"
    if task.status == "done":
        task.status = "in_progress"
        task.completed_at = None
    task.last_progress_at = datetime.now(UTC)
    db.add(subtask)
    db.flush()
    _sync_task_deadline_from_subtasks(db, task)
    add_activity_log(
        db,
        program_id=task_program_id(db, task.project_id),
        activity_id=task.project_id,
        actor_name=actor_name,
        module="subtask",
        action="created",
        summary=f"为任务“{task.title}”新增子任务：{subtask.title}",
        entity_type="subtask",
        entity_id=subtask.id,
        source="task_update",
    )
    program_id = task_program_id(db, task.project_id)
    db.commit()
    evaluate_alerts(db, program_id)
    db.refresh(subtask)
    return subtask


@app.patch("/api/v2/subtasks/{subtask_id}", response_model=SubtaskRead)
def patch_subtask(
    subtask_id: str,
    payload: SubtaskUpdate,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> Subtask:
    subtask = db.get(Subtask, subtask_id)
    if subtask is None:
        raise HTTPException(status_code=404, detail="subtask not found")
    task = _task_v2(db, subtask.task_id)
    values = payload.model_dump(exclude_unset=True)
    start_date = values.get("start_date", subtask.start_date)
    deadline = values.get("deadline", subtask.deadline)
    if deadline < start_date:
        raise HTTPException(status_code=422, detail="deadline must be on or after start_date")
    for key, value in values.items():
        setattr(subtask, key, value.strip() or None if isinstance(value, str) else value)
    if "status" in values:
        subtask.completed_at = datetime.now(UTC) if subtask.status == "done" else None
        if subtask.status == "done":
            subtask.progress_percent = 100
        elif subtask.status == "todo":
            subtask.progress_percent = 0
    task.last_progress_at = datetime.now(UTC)
    db.flush()
    _sync_task_deadline_from_subtasks(db, task)
    if task.progress_mode == "auto":
        active = [item for item in task.subtasks if item.status != "cancelled"]
        if active and all(item.status == "done" for item in active):
            task.status = "done"
            task.completed_at = datetime.now(UTC)
        elif active:
            task.status = "in_progress"
            task.completed_at = None
    add_activity_log(
        db,
        program_id=task_program_id(db, task.project_id),
        activity_id=task.project_id,
        actor_name=actor_name,
        module="subtask",
        action="updated",
        summary=f"更新子任务：{subtask.title}",
        entity_type="subtask",
        entity_id=subtask.id,
        source="task_update",
    )
    program_id = task_program_id(db, task.project_id)
    db.commit()
    evaluate_alerts(db, program_id)
    db.refresh(subtask)
    return subtask


@app.delete("/api/v2/subtasks/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_subtask(
    subtask_id: str,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> None:
    subtask = db.get(Subtask, subtask_id)
    if subtask is None:
        raise HTTPException(status_code=404, detail="subtask not found")
    task = _task_v2(db, subtask.task_id)
    subtask.status = "cancelled"
    subtask.completed_at = None
    db.flush()
    _sync_task_deadline_from_subtasks(db, task)
    add_activity_log(
        db,
        program_id=task_program_id(db, task.project_id),
        activity_id=task.project_id,
        actor_name=actor_name,
        module="subtask",
        action="cancelled",
        summary=f"取消子任务：{subtask.title}",
        entity_type="subtask",
        entity_id=subtask.id,
        source="task_update",
    )
    db.commit()


@app.get("/api/v2/programs/{program_id}/activity-logs", response_model=list[ActivityLogRead])
def list_activity_logs(program_id: str, db: Session = Depends(get_db)) -> list[ProjectActivityLog]:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=404, detail="program not found")
    return list(
        db.scalars(
            select(ProjectActivityLog)
            .where(ProjectActivityLog.program_id == program_id)
            .order_by(ProjectActivityLog.occurred_at.desc())
            .limit(100)
        ).all()
    )


@app.post(
    "/api/v2/programs/{program_id}/activity-logs",
    response_model=ActivityLogRead,
    status_code=status.HTTP_201_CREATED,
)
def post_manual_activity_log(
    program_id: str,
    payload: ActivityLogCreate,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> ProjectActivityLog:
    if db.get(Program, program_id) is None:
        raise HTTPException(status_code=404, detail="program not found")
    log = add_activity_log(
        db,
        program_id=program_id,
        activity_id=None,
        actor_name=actor_name,
        module="program",
        action="manual_note",
        summary=payload.summary.strip(),
        source="manual",
        is_manual_entry=True,
    )
    db.commit()
    db.refresh(log)
    return log


# Phase 2: lightweight budget, material and publicity collaboration.
@app.get("/api/v2/reference-prices", response_model=list[ReferencePriceRead])
def list_reference_prices(include_inactive: bool = False, db: Session = Depends(get_db)) -> list[ReferencePrice]:
    query = select(ReferencePrice)
    if not include_inactive:
        query = query.where(ReferencePrice.is_active.is_(True))
    return list(db.scalars(query.order_by(ReferencePrice.expense_name, ReferencePrice.updated_at.desc())).all())


@app.post("/api/v2/reference-prices", response_model=ReferencePriceRead, status_code=status.HTTP_201_CREATED)
def post_reference_price(payload: ReferencePriceCreate, db: Session = Depends(get_db)) -> ReferencePrice:
    if payload.price_type == "range" and (
        payload.min_price is None or payload.max_price is None or payload.min_price > payload.max_price
    ):
        raise HTTPException(status_code=422, detail="区间价格必须填写有效的最低价和最高价")
    price = ReferencePrice(id=str(uuid4()), **payload.model_dump())
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


@app.patch("/api/v2/reference-prices/{price_id}", response_model=ReferencePriceRead)
def patch_reference_price(price_id: str, payload: ReferencePriceUpdate, db: Session = Depends(get_db)) -> ReferencePrice:
    price = db.get(ReferencePrice, price_id)
    if price is None:
        raise HTTPException(status_code=404, detail="参考价格不存在")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(price, key, value.strip() if isinstance(value, str) else value)
    if price.price_type == "range" and (
        price.min_price is None or price.max_price is None or price.min_price > price.max_price
    ):
        raise HTTPException(status_code=422, detail="区间价格必须填写有效的最低价和最高价")
    db.commit()
    db.refresh(price)
    return price


@app.delete("/api/v2/reference-prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_reference_price(price_id: str, db: Session = Depends(get_db)) -> None:
    price = db.get(ReferencePrice, price_id)
    if price is None or not price.is_active:
        raise HTTPException(status_code=404, detail="参考价格不存在")
    price.is_active = False
    db.commit()


@app.get("/api/v2/budget-sheets", response_model=list[BudgetSheetRead])
def list_budget_sheets(
    program_id: str | None = None,
    activity_id: str | None = None,
    budget_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[BudgetSheet]:
    query = select(BudgetSheet).options(selectinload(BudgetSheet.items))
    if program_id:
        query = query.where(BudgetSheet.program_id == program_id)
    if activity_id:
        query = query.where(BudgetSheet.activity_id == activity_id)
    if budget_status:
        query = query.where(BudgetSheet.status == budget_status)
    return list(db.scalars(query.order_by(BudgetSheet.created_at.desc())).unique().all())


@app.post("/api/v2/budget-sheets", response_model=BudgetSheetRead, status_code=status.HTTP_201_CREATED)
def post_budget_sheet(
    payload: BudgetSheetCreate,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> BudgetSheet:
    try:
        sheet = create_budget_sheet(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_activity_log(db, program_id=sheet.program_id, activity_id=sheet.activity_id, actor_name=actor_name,
                     module="budget", action="created", entity_type="budget_sheet", entity_id=sheet.id,
                     summary="创建预算申请表", source="budget_update")
    db.commit()
    return get_budget_sheet(db, sheet.id)


@app.patch("/api/v2/budget-sheets/{sheet_id}", response_model=BudgetSheetRead)
def patch_budget_sheet(
    sheet_id: str,
    payload: BudgetSheetUpdate,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> BudgetSheet:
    try:
        sheet = get_budget_sheet(db, sheet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(sheet, key, value.strip() if isinstance(value, str) else value)
    add_activity_log(db, program_id=sheet.program_id, activity_id=sheet.activity_id, actor_name=actor_name,
                     module="budget", action="updated", entity_type="budget_sheet", entity_id=sheet.id,
                     summary="更新预算申请进度", changes=values, source="budget_update")
    db.commit()
    return get_budget_sheet(db, sheet.id)


@app.delete("/api/v2/budget-sheets/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_budget_sheet(
    sheet_id: str,
    db: Session = Depends(get_db),
    x_actor_name: str | None = Header(default=None),
) -> None:
    try:
        sheet = get_budget_sheet(db, sheet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    item_ids = [item.id for item in sheet.items]
    if item_ids:
        db.query(MaterialRequirement).filter(MaterialRequirement.budget_item_id.in_(item_ids)).update(
            {MaterialRequirement.budget_item_id: None}, synchronize_session=False
        )
        db.query(PublicityRequirement).filter(PublicityRequirement.budget_item_id.in_(item_ids)).update(
            {PublicityRequirement.budget_item_id: None}, synchronize_session=False
        )
    program_id, activity_id = sheet.program_id, sheet.activity_id
    db.delete(sheet)
    db.flush()
    add_activity_log(
        db, program_id=program_id, activity_id=activity_id, actor_name=x_actor_name, module="budget", action="deleted",
        entity_type="budget_sheet", entity_id=sheet_id, summary="删除预算申请表", source="budget_update",
    )
    db.commit()


@app.post("/api/v2/budget-sheets/{sheet_id}/items", response_model=BudgetItemRead, status_code=status.HTTP_201_CREATED)
def post_budget_item(
    sheet_id: str,
    payload: BudgetItemCreate,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> BudgetItem:
    try:
        item = create_budget_item(db, sheet_id, payload)
        sheet = get_budget_sheet(db, sheet_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_activity_log(db, program_id=sheet.program_id, activity_id=sheet.activity_id, actor_name=actor_name,
                     module="budget", action="created", entity_type="budget_item", entity_id=item.id,
                     summary=f"新增预算项：{item.expense_name}", source="budget_update")
    db.commit()
    return item


@app.patch("/api/v2/budget-items/{item_id}", response_model=BudgetItemRead)
def patch_budget_item(
    item_id: str,
    payload: BudgetItemUpdate,
    db: Session = Depends(get_db),
    actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> BudgetItem:
    item = db.get(BudgetItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="预算项不存在")
    try:
        item = update_budget_item(db, item, payload)
        sheet = get_budget_sheet(db, item.budget_sheet_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_activity_log(db, program_id=sheet.program_id, activity_id=sheet.activity_id, actor_name=actor_name,
                     module="budget", action="updated", entity_type="budget_item", entity_id=item.id,
                     summary=f"更新预算项：{item.expense_name}", source="budget_update")
    db.commit()
    return item


@app.delete("/api/v2/budget-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_budget_item(item_id: str, db: Session = Depends(get_db)) -> None:
    item = db.get(BudgetItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="预算项不存在")
    db.delete(item)
    db.commit()


def _filtered_requirements(query, model, program_id, activity_id, requirement_status, owner):
    if program_id:
        query = query.where(model.program_id == program_id)
    if activity_id:
        query = query.where(model.activity_id == activity_id)
    if requirement_status:
        query = query.where(model.status == requirement_status)
    if owner:
        query = query.where(model.owner_name.contains(owner))
    return query.order_by(model.updated_at.desc())


@app.get("/api/v2/material-requirements", response_model=list[MaterialRequirementRead])
def list_material_requirements(program_id: str | None = None, activity_id: str | None = None,
                               requirement_status: str | None = Query(default=None, alias="status"), owner: str | None = None,
                               db: Session = Depends(get_db)) -> list[MaterialRequirement]:
    query = _filtered_requirements(select(MaterialRequirement), MaterialRequirement, program_id, activity_id, requirement_status, owner)
    return list(db.scalars(query).all())


@app.post("/api/v2/material-requirements", response_model=MaterialRequirementRead, status_code=status.HTTP_201_CREATED)
def post_material_requirement(payload: MaterialRequirementCreate, db: Session = Depends(get_db),
                              actor_name: str | None = Header(default=None, alias="X-Actor-Name")) -> MaterialRequirement:
    try:
        validate_activity(db, payload.program_id, payload.activity_id)
        validate_budget_item_link(db, payload.program_id, payload.budget_item_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    item = MaterialRequirement(id=str(uuid4()), **payload.model_dump())
    db.add(item)
    add_activity_log(db, program_id=item.program_id, activity_id=item.activity_id, actor_name=actor_name,
                     module="material", action="created", entity_type="material_requirement", entity_id=item.id,
                     summary=f"新增物料需求：{item.name}", source="requirement_update")
    db.commit(); db.refresh(item)
    return item


@app.patch("/api/v2/material-requirements/{item_id}", response_model=MaterialRequirementRead)
def patch_material_requirement(item_id: str, payload: MaterialRequirementUpdate, db: Session = Depends(get_db),
                               actor_name: str | None = Header(default=None, alias="X-Actor-Name")) -> MaterialRequirement:
    item = db.get(MaterialRequirement, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="物料需求不存在")
    values = payload.model_dump(exclude_unset=True)
    try:
        if "activity_id" in values:
            validate_activity(db, item.program_id, values["activity_id"])
        if "budget_item_id" in values:
            validate_budget_item_link(db, item.program_id, values["budget_item_id"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for key, value in values.items(): setattr(item, key, value.strip() if isinstance(value, str) else value)
    add_activity_log(db, program_id=item.program_id, activity_id=item.activity_id, actor_name=actor_name,
                     module="material", action="updated", entity_type="material_requirement", entity_id=item.id,
                     summary=f"更新物料需求：{item.name}", changes=values, source="requirement_update")
    db.commit(); db.refresh(item)
    return item


@app.delete("/api/v2/material-requirements/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material_requirement(item_id: str, db: Session = Depends(get_db),
                                actor_name: str | None = Header(default=None, alias="X-Actor-Name")) -> None:
    item = db.get(MaterialRequirement, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="物料需求不存在")
    add_activity_log(db, program_id=item.program_id, activity_id=item.activity_id, actor_name=actor_name,
                     module="material", action="deleted", entity_type="material_requirement", entity_id=item.id,
                     summary=f"删除物料需求：{item.name}", source="requirement_update")
    db.delete(item); db.commit()


@app.get("/api/v2/publicity-requirements", response_model=list[PublicityRequirementRead])
def list_publicity_requirements(program_id: str | None = None, activity_id: str | None = None,
                                requirement_status: str | None = Query(default=None, alias="status"), owner: str | None = None,
                                db: Session = Depends(get_db)) -> list[PublicityRequirement]:
    query = _filtered_requirements(select(PublicityRequirement), PublicityRequirement, program_id, activity_id, requirement_status, owner)
    return list(db.scalars(query).all())


@app.post("/api/v2/publicity-requirements", response_model=PublicityRequirementRead, status_code=status.HTTP_201_CREATED)
def post_publicity_requirement(payload: PublicityRequirementCreate, db: Session = Depends(get_db),
                               actor_name: str | None = Header(default=None, alias="X-Actor-Name")) -> PublicityRequirement:
    try:
        validate_activity(db, payload.program_id, payload.activity_id)
        validate_budget_item_link(db, payload.program_id, payload.budget_item_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    item = PublicityRequirement(id=str(uuid4()), **payload.model_dump())
    db.add(item)
    add_activity_log(db, program_id=item.program_id, activity_id=item.activity_id, actor_name=actor_name,
                     module="publicity", action="created", entity_type="publicity_requirement", entity_id=item.id,
                     summary=f"新增宣传需求：{item.content_type}", source="requirement_update")
    db.commit(); db.refresh(item)
    return item


@app.patch("/api/v2/publicity-requirements/{item_id}", response_model=PublicityRequirementRead)
def patch_publicity_requirement(item_id: str, payload: PublicityRequirementUpdate, db: Session = Depends(get_db),
                                actor_name: str | None = Header(default=None, alias="X-Actor-Name")) -> PublicityRequirement:
    item = db.get(PublicityRequirement, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="宣传需求不存在")
    values = payload.model_dump(exclude_unset=True)
    try:
        if "activity_id" in values:
            validate_activity(db, item.program_id, values["activity_id"])
        if "budget_item_id" in values:
            validate_budget_item_link(db, item.program_id, values["budget_item_id"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for key, value in values.items(): setattr(item, key, value.strip() if isinstance(value, str) else value)
    add_activity_log(db, program_id=item.program_id, activity_id=item.activity_id, actor_name=actor_name,
                     module="publicity", action="updated", entity_type="publicity_requirement", entity_id=item.id,
                     summary=f"更新宣传需求：{item.content_type}", changes=values, source="requirement_update")
    db.commit(); db.refresh(item)
    return item


@app.delete("/api/v2/publicity-requirements/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_publicity_requirement(item_id: str, db: Session = Depends(get_db),
                                 actor_name: str | None = Header(default=None, alias="X-Actor-Name")) -> None:
    item = db.get(PublicityRequirement, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="宣传需求不存在")
    add_activity_log(db, program_id=item.program_id, activity_id=item.activity_id, actor_name=actor_name,
                     module="publicity", action="deleted", entity_type="publicity_requirement", entity_id=item.id,
                     summary=f"删除宣传需求：{item.content_type}", source="requirement_update")
    db.delete(item); db.commit()


@app.get("/api/v2/programs/{program_id}/requirements/summary", response_model=RequirementsSummary)
def get_requirements_summary(program_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return requirements_counts(db, program_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v2/requirements/summary", response_model=list[RequirementsSummary])
def get_global_requirements_summary(db: Session = Depends(get_db)) -> list[dict]:
    programs = db.scalars(select(Program).where(Program.status != "archived")).all()
    return [requirements_counts(db, item.id) for item in programs]


# Phase 3: operational overview, dashboards and annual map.
@app.get("/api/v2/dashboard/programs")
def list_program_dashboards(db: Session = Depends(get_db)) -> list[dict]:
    programs = db.scalars(select(Program).where(Program.status != "archived").order_by(Program.start_date.desc())).all()
    return [dashboard(db, item.id) for item in programs]


@app.get("/api/v2/programs/{program_id}/dashboard")
def get_program_dashboard(program_id: str, db: Session = Depends(get_db)) -> dict:
    result = dashboard(db, program_id)
    if result is None: raise HTTPException(status_code=404, detail="培养项目不存在")
    return result


@app.get("/api/v2/cohorts/{cohort_id}/summary")
def get_cohort_summary(cohort_id: str, db: Session = Depends(get_db)) -> dict:
    cohort = db.scalar(select(Cohort).options(selectinload(Cohort.activities).selectinload(Project.tasks)).where(Cohort.id == cohort_id))
    if cohort is None: raise HTTPException(status_code=404, detail="届别不存在")
    activities = list(cohort.activities)
    values = [a.progress_override if a.progress_override is not None else (round(sum(t.effective_progress_percent for t in a.tasks if t.status != "cancelled") / len([t for t in a.tasks if t.status != "cancelled"])) if any(t.status != "cancelled" for t in a.tasks) else 0) for a in activities]
    upcoming = next((a for a in sorted(activities, key=lambda x: x.start_date) if a.start_date >= date.today()), None)
    return {"id": cohort.id, "name": cohort.name, "business_unit": cohort.business_unit, "participant_count": cohort.participant_count, "start_date": cohort.start_date, "end_date": cohort.end_date, "status": cohort.status, "graduated": cohort.graduated, "progress": cohort.progress_override if cohort.progress_override is not None else (round(sum(values)/len(values)) if values else 0), "activity_count": len(activities), "completed_activity_count": sum(a.status in {"done", "completed"} for a in activities), "next_activity": {"id": upcoming.id, "name": upcoming.name, "start_date": upcoming.start_date} if upcoming else None}


@app.get("/api/v2/training-map")
def get_training_map(year: int = Query(default_factory=lambda: date.today().year, ge=2000, le=2100), group_by: str = Query("program"), db: Session = Depends(get_db)) -> dict:
    activities = db.scalars(select(Project).options(selectinload(Project.program), selectinload(Project.cohort)).where(Project.start_date <= date(year, 12, 31), func.coalesce(Project.end_date, Project.start_date) >= date(year, 1, 1), Project.status != "archived").order_by(Project.start_date)).all()
    rows=[]
    for item in activities:
        group = item.program.name if item.program else "未归属培养项目"
        activity_type = item.activity_type or item.type
        # 线下培训的 start_date 可能包含数月准备周期；年度地图按实际培训日呈现。
        map_start = item.event_date if activity_type == "offline_training" and item.event_date else item.start_date
        map_end = map_start if activity_type == "offline_training" and item.event_date else (item.end_date or map_start)
        if map_start.year != year and map_end.year != year and not (map_start.year < year < map_end.year):
            continue
        rows.append({"id": item.id, "program_id": item.program_id, "program_name": item.program.name if item.program else None, "group": group, "name": item.name, "activity_type": activity_type, "start_date": map_start, "end_date": map_end, "month": 1 if map_start.year < year else map_start.month, "status": item.status})
    return {"year": year, "group_by": group_by, "items": rows}


@app.get("/api/v2/calendar/todos")
def get_calendar_todos(start: date, end: date, db: Session = Depends(get_db)) -> list[dict]:
    tasks = db.scalars(select(ProjectTask).options(selectinload(ProjectTask.project)).where(ProjectTask.deadline.between(start, end), ProjectTask.status.notin_(["done", "cancelled"]))).all()
    return [{"id": t.id, "type": "task", "title": t.title, "date": t.deadline, "status": t.status, "required": bool(t.required), "activity_id": t.project_id, "activity_name": t.project.name} for t in tasks]


# Phase 4: deterministic alerts and focus.
@app.post("/api/v2/programs/{program_id}/alerts/evaluate")
def post_evaluate_alerts(program_id: str, db: Session = Depends(get_db)) -> list[dict]:
    try: alerts = evaluate_alerts(db, program_id)
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [alert_dict(x) for x in alerts]


def alert_dict(item: Alert) -> dict:
    return {"id": item.id, "program_id": item.program_id, "activity_id": item.activity_id, "rule_code": item.rule_code, "alert_type": item.alert_type, "severity": item.severity, "status": item.status, "title": item.title, "reason": item.reason, "current_data_json": item.current_data_json, "recommended_action": item.recommended_action, "source_entity_type": item.source_entity_type, "source_entity_id": item.source_entity_id, "first_detected_at": item.first_detected_at, "last_detected_at": item.last_detected_at, "resolved_at": item.resolved_at}


@app.get("/api/v2/programs/{program_id}/alerts")
def list_alerts(program_id: str, include_closed: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    query = select(Alert).where(Alert.program_id == program_id)
    if not include_closed: query = query.where(Alert.status.in_(["open", "acknowledged"]))
    return [alert_dict(x) for x in db.scalars(query.order_by(Alert.severity.desc(), Alert.last_detected_at.desc())).all()]


@app.post("/api/v2/alerts/{alert_id}/{action}")
def update_alert_state(alert_id: str, action: str, db: Session = Depends(get_db)) -> dict:
    if action not in {"acknowledge", "resolve", "dismiss"}: raise HTTPException(status_code=404, detail="不支持的预警操作")
    item = db.get(Alert, alert_id)
    if item is None: raise HTTPException(status_code=404, detail="预警不存在")
    item.status = {"acknowledge": "acknowledged", "resolve": "resolved", "dismiss": "dismissed"}[action]
    item.resolved_at = datetime.now(UTC) if action in {"resolve", "dismiss"} else None
    db.commit(); db.refresh(item); return alert_dict(item)


@app.get("/api/v2/programs/{program_id}/focus")
def get_program_focus(program_id: str, days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db)) -> list[dict]:
    program = load_program(db, program_id)
    if not program: raise HTTPException(status_code=404, detail="培养项目不存在")
    return focus_items(program, date.today(), days)


# Phase 5: resources, exports and retrospective.
@app.get("/api/v2/resources")
def list_resources(include_inactive: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    query = select(Resource)
    if not include_inactive: query = query.where(Resource.is_active.is_(True))
    return [resource_dict(x) for x in db.scalars(query.order_by(Resource.updated_at.desc())).all()]


def resource_dict(item: Resource) -> dict:
    return {"id": item.id, "title": item.title, "resource_type": item.resource_type, "url": item.url, "file_name": item.file_name, "mime_type": item.mime_type, "is_upload": item.file_content is not None, "linked_task_count": len(item.task_links), "description": item.description, "owner_name": item.owner_name, "is_active": item.is_active, "created_at": item.created_at, "updated_at": item.updated_at}


@app.post("/api/v2/resources", status_code=201)
def post_resource(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    title, url = str(payload.get("title", "")).strip(), str(payload.get("url", "")).strip()
    if not title or not url: raise HTTPException(status_code=422, detail="资料名称和链接必填")
    item = Resource(id=str(uuid4()), title=title, url=url, resource_type=payload.get("resource_type", "link"), description=payload.get("description"), owner_name=payload.get("owner_name"))
    db.add(item); db.commit(); db.refresh(item); return resource_dict(item)


@app.post("/api/v2/resources/upload", status_code=201)
async def upload_resource(
    file: UploadFile = File(...),
    title: str = Form(""),
    resource_type: str = Form("file"),
    owner_name: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
) -> dict:
    content = await file.read(10 * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=422, detail="请选择非空文件")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="单个文件不能超过 10MB")
    safe_name = Path(file.filename or "上传文件").name[:300]
    item = Resource(
        id=str(uuid4()), title=title.strip() or safe_name, resource_type=resource_type,
        url="", file_name=safe_name, mime_type=(file.content_type or "application/octet-stream")[:200],
        file_content=content, owner_name=owner_name.strip() or None, description=description.strip() or None,
    )
    db.add(item); db.commit(); db.refresh(item)
    item.url = f"/api/v2/resources/{item.id}/file"
    db.commit(); db.refresh(item)
    return resource_dict(item)


@app.get("/api/v2/resources/{resource_id}/file")
def download_resource(resource_id: str, db: Session = Depends(get_db)) -> Response:
    item = db.get(Resource, resource_id)
    if item is None or item.file_content is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    ascii_name = "resource" + Path(item.file_name or "").suffix
    return Response(
        item.file_content,
        media_type=item.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{ascii_name}"'},
    )


@app.get("/api/v2/tasks/{task_id}/resources")
def list_task_resources(task_id: str, db: Session = Depends(get_db)) -> list[dict]:
    links = db.scalars(select(TaskResourceLink).options(selectinload(TaskResourceLink.resource)).where(TaskResourceLink.task_id == task_id)).all()
    return [{**resource_dict(x.resource), "relation_type": x.relation_type} for x in links]


@app.get("/api/v2/resources/{resource_id}/tasks")
def list_resource_tasks(resource_id: str, db: Session = Depends(get_db)) -> list[dict]:
    links = db.scalars(
        select(TaskResourceLink).options(
            selectinload(TaskResourceLink.task).selectinload(ProjectTask.project),
            selectinload(TaskResourceLink.task).selectinload(ProjectTask.project_milestone),
        ).where(TaskResourceLink.resource_id == resource_id)
    ).all()
    return [{"task_id": x.task.id, "task_title": x.task.title, "activity_id": x.task.project_id,
             "program_id": x.task.project.program_id,
             "activity_name": x.task.project.name, "milestone_name": x.task.project_milestone.name if x.task.project_milestone else None,
             "relation_type": x.relation_type} for x in links]


@app.get("/api/v2/publicity-calendar")
def publicity_calendar(year: int = Query(default_factory=lambda: date.today().year, ge=2000, le=2100), db: Session = Depends(get_db)) -> list[dict]:
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    items = db.scalars(select(PublicityRequirement).options(selectinload(PublicityRequirement.program), selectinload(PublicityRequirement.activity)).where(
        PublicityRequirement.expected_completion_date.between(year_start, year_end) |
        PublicityRequirement.publish_date.between(year_start, year_end) |
        PublicityRequirement.start_date.between(year_start, year_end)
    )).all()
    rows = []
    for item in items:
        base = {"id": item.id, "program_id": item.program_id, "program_name": item.program.name,
                "activity_name": item.activity.name if item.activity else None, "title": item.content_type, "status": item.status,
                "start_date": item.start_date, "end_date": item.publish_date or item.expected_completion_date or item.start_date,
                "production_deadline": item.expected_completion_date, "publish_date": item.publish_date}
        if item.start_date and not item.expected_completion_date and not item.publish_date:
            rows.append({**base, "date": item.start_date, "date_type": "开始制作"})
        if item.expected_completion_date:
            rows.append({**base, "date": item.expected_completion_date, "date_type": "制作DDL"})
        if item.publish_date:
            rows.append({**base, "date": item.publish_date, "date_type": "预计发布日期"})
    return rows


@app.post("/api/v2/tasks/{task_id}/resources", status_code=201)
def link_task_resource(task_id: str, payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    if db.get(ProjectTask, task_id) is None: raise HTTPException(status_code=404, detail="任务不存在")
    resource = db.get(Resource, payload.get("resource_id"))
    if resource is None: raise HTTPException(status_code=404, detail="资料不存在")
    link = db.get(TaskResourceLink, (task_id, resource.id))
    if link is None:
        link = TaskResourceLink(task_id=task_id, resource_id=resource.id, relation_type=payload.get("relation_type", "reference")); db.add(link); db.commit()
    return {**resource_dict(resource), "relation_type": link.relation_type}


@app.get("/api/v2/tasks/{task_id}/calendar.ics")
def task_calendar(task_id: str, db: Session = Depends(get_db)) -> Response:
    task = db.scalar(select(ProjectTask).options(selectinload(ProjectTask.project).selectinload(Project.program)).where(ProjectTask.id == task_id))
    if not task: raise HTTPException(status_code=404, detail="任务不存在")
    content = build_calendar([{"uid": f"task-{task.id}", "start": task.start_date, "end": task.deadline, "summary": task.title, "description": f"培养项目：{task.project.program.name if task.project.program else ''}；活动：{task.project.name}；负责人：{task.owner or '未填写'}；状态：{task.status}"}])
    return Response(content, media_type="text/calendar; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="task-{task.id}.ics"'})


@app.get("/api/v2/milestones/{milestone_id}/calendar.ics")
def milestone_calendar(milestone_id: str, db: Session = Depends(get_db)) -> Response:
    item = db.scalar(select(ProjectMilestone).options(selectinload(ProjectMilestone.project)).where(ProjectMilestone.id == milestone_id))
    if not item: raise HTTPException(status_code=404, detail="节点不存在")
    content = build_calendar([{"uid": f"milestone-{item.id}", "start": item.start_date, "end": item.deadline, "summary": item.name, "description": f"活动：{item.project.name}；{'关键节点' if item.required else '普通节点'}"}])
    return Response(content, media_type="text/calendar; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="milestone-{item.id}.ics"'})


@app.get("/api/v2/programs/{program_id}/calendar.ics")
def program_calendar(program_id: str, db: Session = Depends(get_db)) -> Response:
    program = load_program(db, program_id)
    if not program: raise HTTPException(status_code=404, detail="培养项目不存在")
    events=[]
    for activity in program.activities:
        for m in activity.milestones:
            if m.required and m.status == "active": events.append({"uid": f"milestone-{m.id}", "start": m.start_date, "end": m.deadline, "summary": f"{activity.name}｜{m.name}", "description": f"培养项目：{program.name}；关键节点"})
        for t in activity.tasks:
            if t.required and t.status not in {"done", "cancelled"}: events.append({"uid": f"task-{t.id}", "start": t.start_date, "end": t.deadline, "summary": f"{activity.name}｜{t.title}", "description": f"培养项目：{program.name}；负责人：{t.owner or '未填写'}"})
    return Response(build_calendar(events), media_type="text/calendar; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="program-{program.id}.ics"'})


@app.get("/api/v2/calendar/all.ics")
def all_programs_calendar(db: Session = Depends(get_db)) -> Response:
    program_ids = db.scalars(select(Program.id).where(Program.status != "archived")).all()
    events = []
    for program_id in program_ids:
        program = load_program(db, program_id)
        if not program:
            continue
        for activity in program.activities:
            if activity.status == "archived":
                continue
            for milestone in activity.milestones:
                if milestone.required and milestone.status == "active":
                    events.append({"uid": f"milestone-{milestone.id}", "start": milestone.start_date, "end": milestone.deadline, "summary": f"{program.name}｜{activity.name}｜{milestone.name}", "description": "培训中心关键节点"})
    return Response(build_calendar(events), media_type="text/calendar; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="training-center-all-programs.ics"'})


@app.get("/api/v2/programs/{program_id}/exports/operations.xlsx")
def export_operations(program_id: str, db: Session = Depends(get_db)) -> Response:
    program = load_program(db, program_id)
    if not program: raise HTTPException(status_code=404, detail="培养项目不存在")
    from app.services.export_excel import build_operations_workbook
    content = build_operations_workbook(db, program)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="training-copilot-{program.id}.xlsx"'})


@app.get("/api/v2/programs/{program_id}/retrospective")
def get_retrospective(program_id: str, db: Session = Depends(get_db)) -> dict:
    result = dashboard(db, program_id)
    program = load_program(db, program_id)
    if not result or not program: raise HTTPException(status_code=404, detail="培养项目不存在")
    tasks=[t for a in program.activities for t in a.tasks if t.status != "cancelled"]
    scored=[t.quality_score for t in tasks if t.quality_score is not None]
    return {"program": {"id": program.id, "name": program.name, "start_date": program.start_date, "end_date": program.end_date}, "progress": result["progress"], "health": result["health"], "activity_count": len(program.activities), "participant_count": result["outcomes"]["participant_count"], "task_count": len(tasks), "completed_task_count": sum(t.status == "done" for t in tasks), "overdue_task_count": sum(t.deadline < date.today() and t.status not in {"done", "cancelled"} for t in tasks), "average_quality_score": round(sum(scored)/len(scored), 2) if scored else None, "retrospective_notes": [{"task_id": t.id, "task_title": t.title, "quality_score": t.quality_score, "note": t.retrospective_note} for t in tasks if t.retrospective_note or t.quality_score], "specialty": result["specialty"], "alerts": result["health"]}
