"""add immutable template-derived milestone start date

Revision ID: 0010_milestone_start_date
Revises: 0009_deadline_rollup_backfill
"""

from datetime import date, timedelta

from alembic import op
import sqlalchemy as sa


revision = "0010_milestone_start_date"
down_revision = "0009_deadline_rollup_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_milestones") as batch:
        batch.add_column(sa.Column("start_date", sa.Date(), nullable=True))
    # Calculate in Python instead of using SQLite-specific date()/printf().
    # The production database is PostgreSQL while local development uses
    # SQLite, so the migration must remain dialect independent.
    connection = op.get_bind()
    rows = connection.execute(sa.text("""
        SELECT pm.id, pm.deadline, p.event_date, m.offset_days
        FROM project_milestones AS pm
        LEFT JOIN projects AS p ON p.id = pm.project_id
        LEFT JOIN milestones AS m ON m.id = pm.template_milestone_id
    """)).mappings().all()
    for row in rows:
        start_date = row["deadline"]
        if row["event_date"] is not None and row["offset_days"] is not None:
            event_date = row["event_date"]
            if isinstance(event_date, str):
                event_date = date.fromisoformat(event_date)
            start_date = event_date + timedelta(days=row["offset_days"])
        connection.execute(
            sa.text("UPDATE project_milestones SET start_date=:start_date WHERE id=:id"),
            {"start_date": start_date, "id": row["id"]},
        )
    with op.batch_alter_table("project_milestones") as batch:
        batch.alter_column("start_date", existing_type=sa.Date(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("project_milestones") as batch:
        batch.drop_column("start_date")
