from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Milestone, ProjectTask, RiskRule, TemplateTask
from app.schemas import ProjectCreate
from app.services.projects import create_project
from app.services.seed import load_offline_training_seed


def test_seed_and_project_task_instantiation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        load_offline_training_seed(db)

        assert db.query(Milestone).count() == 20
        assert db.query(TemplateTask).count() == 64
        assert db.query(RiskRule).count() == 9

        project = create_project(
            db,
            ProjectCreate(
                name="线下培训测试项目",
                template_id="tpl_offline_training_v1_0",
                start_date=date(2026, 8, 1),
                event_date=date(2026, 9, 30),
            ),
        )

        tasks = db.query(ProjectTask).filter_by(project_id=project.id).all()
        assert len(tasks) == 64
        assert len(project.milestones) == 20

        by_template_id = {task.template_task_id: task for task in tasks}
        assert by_template_id["tt_m03_01"].deadline == date(2026, 9, 9)
        assert by_template_id["tt_m14_01"].deadline == date(2026, 9, 30)
        assert by_template_id["tt_m19_01"].deadline == date(2026, 10, 14)
        assert by_template_id["tt_m20_01"].deadline == date(2026, 10, 21)
        assert by_template_id["tt_m03_01"].required is True
        assert by_template_id["tt_m16_01"].required is False
        assert by_template_id["tt_m12_01"].required is None
        assert by_template_id["tt_m03_01"].completed_at is None
        assert by_template_id["tt_m03_01"].project_milestone_id is not None
