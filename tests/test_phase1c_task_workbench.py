from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.main import (
    bulk_update_tasks,
    list_activity_logs,
    patch_subtask,
    patch_task_v2,
    post_manual_activity_log,
    post_subtask,
)
from app.schemas import (
    ActivityLogCreate,
    ProgramCreate,
    ProjectCreate,
    SubtaskCreate,
    SubtaskUpdate,
    TaskBulkUpdate,
    TaskV2Update,
)
from app.services.activity_logs import clean_actor_name
from app.services.projects import create_program, create_project
from app.services.seed import load_offline_training_seed


def test_task_subtask_progress_bulk_and_activity_logs() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        load_offline_training_seed(db)
        project = create_project(
            db,
            ProjectCreate(
                name="Phase 1C测试项目",
                template_id="tpl_offline_training_v1_0",
                start_date=date(2026, 6, 1),
                event_date=date(2026, 7, 1),
            ),
        )
        task = project.tasks[0]
        template_start = task.project_milestone.start_date
        first = post_subtask(
            task.id,
            SubtaskCreate(
                title="准备初稿",
                owner="张三、李四",
                start_date=task.start_date,
                deadline=task.deadline,
            ),
            db,
            "王五",
        )
        second = post_subtask(
            task.id,
            SubtaskCreate(
                title="完成确认",
                start_date=task.start_date,
                deadline=task.deadline,
            ),
            db,
            "王五",
        )
        latest_deadline = task.deadline + timedelta(days=5)
        patch_subtask(second.id, SubtaskUpdate(deadline=latest_deadline), db, "王五")
        rolled_up = patch_task_v2(task.id, TaskV2Update(), db, "王五")
        assert rolled_up.deadline == latest_deadline
        db.refresh(rolled_up.project_milestone)
        assert rolled_up.project_milestone.start_date == template_start
        assert rolled_up.project_milestone.deadline == max(
            item.deadline for item in project.tasks if item.project_milestone_id == rolled_up.project_milestone_id
        )
        updated_first = patch_subtask(
            first.id, SubtaskUpdate(status="done"), db, "王五"
        )
        assert updated_first.progress_percent == 100
        auto_task = patch_task_v2(task.id, TaskV2Update(), db, "王五")
        assert auto_task.progress_mode == "auto"
        assert auto_task.auto_progress_percent == 50
        assert auto_task.effective_progress_percent == 50

        manual_task = patch_task_v2(
            task.id,
            TaskV2Update(
                progress_mode="manual",
                progress_percent=60,
                progress_note="等待最终确认",
                completion_criteria="业务负责人确认",
                notes="普通备注",
            ),
            db,
            "王五",
        )
        assert manual_task.effective_progress_percent == 60
        patch_subtask(second.id, SubtaskUpdate(status="done"), db, "王五")
        manual_task = patch_task_v2(task.id, TaskV2Update(), db, "王五")
        assert manual_task.auto_progress_percent == 100
        assert manual_task.effective_progress_percent == 60

        restored = patch_task_v2(
            task.id, TaskV2Update(progress_mode="auto"), db, "王五"
        )
        assert restored.effective_progress_percent == 100

        for index in range(3):
            post_subtask(
                task.id,
                SubtaskCreate(
                    title=f"补充小任务{index + 1}",
                    start_date=task.start_date,
                    deadline=task.deadline,
                ),
                db,
                "王五",
            )
        five_subtasks = patch_task_v2(task.id, TaskV2Update(), db, "王五")
        assert len(five_subtasks.subtasks) == 5
        assert five_subtasks.auto_progress_percent == 40  # 2/5 done; each subtask has 20% weight.

        other_ids = [item.id for item in project.tasks[1:3]]
        completed = bulk_update_tasks(
            TaskBulkUpdate(task_ids=other_ids, action="complete"), db, "王五"
        )
        assert all(item.status == "done" and item.progress_percent == 100 for item in completed)
        scored = patch_task_v2(
            other_ids[0],
            TaskV2Update(quality_score=5, retrospective_note="下次提前确认"),
            db,
            "王五",
        )
        assert scored.quality_score == 5

        manual_log = post_manual_activity_log(
            project.program_id,
            ActivityLogCreate(summary="项目组完成阶段沟通"),
            db,
            "王五",
        )
        assert manual_log.actor_name == "王五"
        logs = list_activity_logs(project.program_id, db)
        assert len(logs) >= 8
        assert any(item.is_manual_entry for item in logs)


def test_lightweight_program_can_exist_without_activity_template() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        program = create_program(
            db,
            ProgramCreate(
                name="无模板培养项目",
                program_type="annual_continuous",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
            ),
        )
        assert program.name == "无模板培养项目"


def test_actor_name_accepts_browser_safe_percent_encoding() -> None:
    assert clean_actor_name("%E7%8E%8B%E4%BA%94") == "王五"
    assert clean_actor_name(None) == "系统用户"
