"""add Phase 1C task workbench, subtasks and activity logs"""

from alembic import op
import sqlalchemy as sa


revision = "0003_phase1c_task_workbench"
down_revision = "0002_phase1a_program_activity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_tasks") as batch:
        batch.add_column(sa.Column("start_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("progress_mode", sa.String(16), nullable=False, server_default="manual"))
        batch.add_column(sa.Column("progress_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("completion_criteria", sa.Text(), nullable=True))
        batch.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("quality_score", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("retrospective_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE project_tasks
        SET start_date=deadline,
            progress_percent=CASE WHEN status='done' THEN 100 ELSE 0 END,
            last_progress_at=COALESCE(completed_at, CURRENT_TIMESTAMP),
            updated_at=COALESCE(completed_at, CURRENT_TIMESTAMP)
    """))
    with op.batch_alter_table("project_tasks") as batch:
        batch.alter_column("start_date", existing_type=sa.Date(), nullable=False)
        batch.alter_column("last_progress_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    op.create_table(
        "subtasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("project_tasks.id"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("owner", sa.String(500), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="todo"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subtasks_task_id", "subtasks", ["task_id"])
    op.create_table(
        "project_activity_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("cohort_id", sa.String(36), sa.ForeignKey("cohorts.id"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_name", sa.String(100), nullable=False, server_default="系统用户"),
        sa.Column("module", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("changes_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="system"),
        sa.Column("is_manual_entry", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_project_activity_logs_program_id", "project_activity_logs", ["program_id"])
    op.create_index("ix_project_activity_logs_activity_id", "project_activity_logs", ["activity_id"])
    op.create_index("ix_project_activity_logs_occurred_at", "project_activity_logs", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("project_activity_logs")
    op.drop_table("subtasks")
    with op.batch_alter_table("project_tasks") as batch:
        for name in [
            "updated_at", "last_progress_at", "sort_order", "retrospective_note",
            "quality_score", "notes", "completion_criteria", "progress_note",
            "progress_mode", "progress_percent", "start_date",
        ]:
            batch.drop_column(name)
