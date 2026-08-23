from datetime import UTC, date, datetime

from app.models import ProjectTask


def test_task_completion_fields() -> None:
    task = ProjectTask(
        id="task-test",
        project_id="project-test",
        template_task_id="tt_m01_01",
        milestone_id="ms_offline_m01",
        title="明确培训目标",
        status="todo",
        deadline=date(2026, 9, 1),
        required=True,
    )

    task.status = "done"
    task.completed_at = datetime.now(UTC)
    assert task.status == "done"
    assert task.completed_at is not None

    task.status = "todo"
    task.completed_at = None
    assert task.completed_at is None

    task.owner = "张三"
    assert task.owner == "张三"
