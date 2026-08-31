"""workspace interaction refresh

Revision ID: 0007_workspace_refresh
Revises: 0006_resource_file_uploads
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_workspace_refresh"
down_revision = "0006_resource_file_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_classes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("business_unit", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("program_id", "name"),
    )
    op.create_index("ix_training_classes_program_id", "training_classes", ["program_id"])
    op.add_column("budget_items", sa.Column("status", sa.String(32), nullable=False, server_default="pending_submission"))
    op.create_index("ix_budget_items_status", "budget_items", ["status"])

    op.execute("UPDATE budget_sheets SET status='pending_submission' WHERE status='pending_confirmation'")
    op.execute("UPDATE budget_sheets SET status='in_review' WHERE status='submitted'")
    op.execute("UPDATE material_requirements SET status='pending' WHERE status IN ('pending_confirmation','blocked','cancelled')")
    op.execute("UPDATE material_requirements SET status='done' WHERE status='done'")
    op.execute("UPDATE publicity_requirements SET status='pending' WHERE status IN ('requirement_confirmation','pending_confirmation')")
    op.execute("UPDATE publicity_requirements SET status='in_progress' WHERE status IN ('material_preparation','in_production')")
    op.execute("UPDATE publicity_requirements SET status='done' WHERE status IN ('done','published')")


def downgrade() -> None:
    op.drop_index("ix_budget_items_status", table_name="budget_items")
    op.drop_column("budget_items", "status")
    op.drop_index("ix_training_classes_program_id", table_name="training_classes")
    op.drop_table("training_classes")
