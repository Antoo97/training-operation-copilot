from contextlib import asynccontextmanager
from datetime import UTC, datetime
import base64
import os
import secrets
from uuid import uuid4
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import Base, SessionLocal, engine, ensure_schema_compatibility, get_db
from app.models import Project, ProjectMilestone, ProjectTask, ProjectTemplate
from app.schemas import (
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectMilestoneCreate,
    ProjectMilestoneRead,
    ProjectMilestoneUpdate,
    ProjectTaskCreate,
    ProjectTaskRead,
    TaskOwnerUpdate,
    TaskRequiredUpdate,
    TaskStatusUpdate,
)
from app.services.projects import TemplateNotFoundError, backfill_project_milestones, create_project
from app.services.seed import load_offline_training_seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    with SessionLocal() as db:
        load_offline_training_seed(db)
        backfill_project_milestones(db)
    yield


app = FastAPI(title="Training Operation Copilot", version="0.1.0", lifespan=lifespan)
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
        )
        .where(Project.id == project_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@app.patch("/tasks/{task_id}/status", response_model=ProjectTaskRead)
def patch_task_status(task_id: str, payload: TaskStatusUpdate, db: Session = Depends(get_db)) -> ProjectTask:
    task = db.get(ProjectTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    task.status = payload.status
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
        deadline=milestone.deadline,
        required=payload.required,
    )
    db.add(task)
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
