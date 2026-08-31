"""resource file uploads

Revision ID: 0006_resource_file_uploads
Revises: 0005_phase3_phase5
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_resource_file_uploads"
down_revision: str | None = "0005_phase3_phase5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resources", sa.Column("file_name", sa.String(300), nullable=True))
    op.add_column("resources", sa.Column("mime_type", sa.String(200), nullable=True))
    op.add_column("resources", sa.Column("file_content", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("resources", "file_content")
    op.drop_column("resources", "mime_type")
    op.drop_column("resources", "file_name")
