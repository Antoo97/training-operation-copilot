"""add immutable template-derived milestone start date

Revision ID: 0010_milestone_start_date
Revises: 0009_deadline_rollup_backfill
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_milestone_start_date"
down_revision = "0009_deadline_rollup_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_milestones") as batch:
        batch.add_column(sa.Column("start_date", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE project_milestones
        SET start_date = COALESCE(
            (
                SELECT date(projects.event_date, printf('%+d days', milestones.offset_days))
                FROM projects
                JOIN milestones ON milestones.id = project_milestones.template_milestone_id
                WHERE projects.id = project_milestones.project_id
            ),
            project_milestones.deadline
        )
        """
    )
    with op.batch_alter_table("project_milestones") as batch:
        batch.alter_column("start_date", existing_type=sa.Date(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("project_milestones") as batch:
        batch.drop_column("start_date")
