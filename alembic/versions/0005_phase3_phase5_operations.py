"""phase 3-5 operations, alerts and resources

Revision ID: 0005_phase3_phase5
Revises: 0004_phase2_requirements
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_phase3_phase5"
down_revision = "0004_phase2_requirements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("rule_code", sa.String(64), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("current_data_json", sa.JSON(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("source_entity_type", sa.String(32), nullable=False),
        sa.Column("source_entity_id", sa.String(36), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("program_id", "rule_code", "source_entity_type", "source_entity_id", name="uq_open_alert_source"),
    )
    for column in ("program_id", "activity_id", "rule_code", "alert_type", "severity", "status"):
        op.create_index(f"ix_alerts_{column}", "alerts", [column])
    op.create_table(
        "resources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False, server_default="link"),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_name", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_resources_is_active", "resources", ["is_active"])
    op.create_table(
        "task_resource_links",
        sa.Column("task_id", sa.String(36), sa.ForeignKey("project_tasks.id"), primary_key=True),
        sa.Column("resource_id", sa.String(36), sa.ForeignKey("resources.id"), primary_key=True),
        sa.Column("relation_type", sa.String(32), nullable=False, server_default="reference"),
        sa.UniqueConstraint("task_id", "resource_id"),
    )


def downgrade() -> None:
    op.drop_table("task_resource_links")
    op.drop_index("ix_resources_is_active", table_name="resources")
    op.drop_table("resources")
    for column in ("status", "severity", "alert_type", "rule_code", "activity_id", "program_id"):
        op.drop_index(f"ix_alerts_{column}", table_name="alerts")
    op.drop_table("alerts")
