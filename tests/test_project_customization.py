from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.main import (
    patch_project_milestone,
    patch_task_required,
    post_project_milestone,
    post_project_task,
    remove_project_milestone,
    remove_project_task,
)
from app.schemas import (
    ProjectCreate,
    ProjectMilestoneCreate,
    ProjectMilestoneUpdate,
    ProjectTaskCreate,
    TaskRequiredUpdate,
)
from app.services.projects import create_project
from app.services.seed import load_offline_training_seed


def test_add_mark_critical_and_remove_custom_task() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        load_offline_training_seed(db)
        project = create_project(
            db,
            ProjectCreate(
                name="定制培训项目",
                template_id="tpl_offline_training_v1_0",
                start_date=date(2026, 8, 1),
                event_date=date(2026, 9, 30),
            ),
        )

        task = post_project_task(
            project.id,
            ProjectTaskCreate(
                title="定制任务",
                project_milestone_id=next(
                    item.id for item in project.milestones if item.template_milestone_id == "ms_offline_m10"
                ),
                owner="李四",
                required=False,
            ),
            db,
        )
        assert task.template_task_id is None
        assert task.deadline == date(2026, 9, 16)
        assert task.owner == "李四"

        updated = patch_task_required(task.id, TaskRequiredUpdate(required=True), db)
        assert updated.required is True

        remove_project_task(task.id, db)
        db.refresh(task)
        assert task.status == "cancelled"

        milestone = post_project_milestone(
            project.id,
            ProjectMilestoneCreate(name="业务确认", deadline=date(2026, 9, 10), required=True),
            db,
        )
        custom_task = post_project_task(
            project.id,
            ProjectTaskCreate(
                title="确认业务方案",
                project_milestone_id=milestone.id,
                owner=None,
                required=True,
            ),
            db,
        )
        assert custom_task.deadline == date(2026, 9, 10)

        patch_project_milestone(
            milestone.id,
            ProjectMilestoneUpdate(deadline=date(2026, 9, 12)),
            db,
        )
        db.refresh(custom_task)
        assert custom_task.deadline == date(2026, 9, 12)

        remove_project_milestone(milestone.id, db)
        db.refresh(milestone)
        db.refresh(custom_task)
        assert milestone.status == "removed"
        assert custom_task.status == "cancelled"
