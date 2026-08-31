"""backfill branch-task deadline rollups

Revision ID: 0009_deadline_rollup_backfill
Revises: 0008_resource_calendar_ux
"""

from alembic import op


revision = "0009_deadline_rollup_backfill"
down_revision = "0008_resource_calendar_ux"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE project_tasks
        SET deadline = (
            SELECT MAX(subtasks.deadline)
            FROM subtasks
            WHERE subtasks.task_id = project_tasks.id
              AND subtasks.status != 'cancelled'
        )
        WHERE EXISTS (
            SELECT 1 FROM subtasks
            WHERE subtasks.task_id = project_tasks.id
              AND subtasks.status != 'cancelled'
        )
        """
    )
    op.execute(
        """
        UPDATE project_milestones
        SET deadline = (
            SELECT MAX(project_tasks.deadline)
            FROM project_tasks
            WHERE project_tasks.project_milestone_id = project_milestones.id
              AND project_tasks.status != 'cancelled'
        )
        WHERE EXISTS (
            SELECT 1 FROM project_tasks
            WHERE project_tasks.project_milestone_id = project_milestones.id
              AND project_tasks.status != 'cancelled'
        )
        """
    )


def downgrade() -> None:
    # Runtime dates cannot be reconstructed safely after users have edited them.
    pass
