"""resource and calendar ux

Revision ID: 0008_resource_calendar_ux
Revises: 0007_workspace_refresh
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_resource_calendar_ux"
down_revision = "0007_workspace_refresh"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publicity_requirements", sa.Column("publish_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("publicity_requirements", "publish_date")
