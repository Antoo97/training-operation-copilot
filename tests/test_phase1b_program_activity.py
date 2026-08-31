from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.main import post_activity, post_cohort, post_training_class, remove_project
from app.models import Program, Project, TrainingClass
from app.schemas import ActivityCreate, CohortCreate, ProgramCreate, ProjectCreate, TrainingClassCreate
from app.services.projects import create_program, create_project
from app.services.seed import load_offline_training_seed


def test_program_cohort_and_activity_hierarchy() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        load_offline_training_seed(db)
        program = create_program(
            db,
            ProgramCreate(
                name="2026管培生培养项目",
                program_type="multi_cohort",
                owner_name="张三、李四",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
            ),
        )
        cohort = post_cohort(
            program.id,
            CohortCreate(
                name="2026届",
                participant_count=30,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
            ),
            db,
        )
        training_class = post_training_class(
            program.id,
            TrainingClassCreate(name="一班", participant_count=30, business_unit="销售事业部"),
            db,
        )
        assert training_class.start_date == program.start_date
        assert training_class.end_date == program.end_date
        assert db.query(TrainingClass).count() == 1
        lightweight = post_activity(
            program.id,
            ActivityCreate(
                name="线上学习第一期",
                activity_type="online_training",
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 14),
                cohort_id=cohort.id,
                owner_name="王五、赵六",
            ),
            db,
        )
        assert lightweight.template_id is None
        assert lightweight.event_date is None
        assert lightweight.tasks == []

        offline = post_activity(
            program.id,
            ActivityCreate(
                name="线下培训第一期",
                activity_type="offline_training",
                start_date=date(2026, 2, 1),
                end_date=date(2026, 3, 3),
                event_date=date(2026, 3, 2),
                template_id="tpl_offline_training_v1_0",
                cohort_id=cohort.id,
            ),
            db,
        )
        assert offline.program_id == program.id
        assert len(offline.milestones) == 20
        assert len(offline.tasks) == 64
        assert db.query(Program).count() == 1
        assert db.query(Project).count() == 2


def test_v1_create_project_still_creates_compatible_program() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        load_offline_training_seed(db)
        project = create_project(
            db,
            ProjectCreate(
                name="v1兼容项目",
                template_id="tpl_offline_training_v1_0",
                start_date=date(2026, 4, 1),
                event_date=date(2026, 5, 1),
            ),
        )
        assert project.program_id is not None
        assert project.activity_type == "offline_training"
        assert project.end_date == project.event_date
        assert len(project.tasks) == 64
        remove_project(project.id, db)
        assert db.query(Project).count() == 0
        assert db.query(Program).count() == 0
