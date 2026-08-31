"""add Program/Cohort and Activity compatibility fields"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0002_phase1a_program_activity"
down_revision = "0001_v01_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "programs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("program_type", sa.String(64), nullable=False, server_default="annual_continuous"),
        sa.Column("owner_name", sa.String(500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("current_phase", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("business_unit", sa.String(200), nullable=True),
        sa.Column("participant_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_programs_program_type", "programs", ["program_type"])
    op.create_index("ix_programs_status", "programs", ["status"])
    op.create_table(
        "cohorts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("business_unit", sa.String(200), nullable=True),
        sa.Column("participant_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("graduated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("progress_override", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("program_id", "name"),
    )
    op.create_index("ix_cohorts_program_id", "cohorts", ["program_id"])
    op.create_index("ix_cohorts_status", "cohorts", ["status"])

    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("program_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("cohort_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("activity_type", sa.String(64), nullable=True))
        batch.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("owner_name", sa.String(500), nullable=True))
        batch.add_column(sa.Column("location", sa.String(300), nullable=True))
        batch.add_column(sa.Column("business_unit", sa.String(200), nullable=True))
        batch.add_column(sa.Column("participant_count", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("progress_override", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("current_phase", sa.String(100), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_projects_program_id", "programs", ["program_id"], ["id"])
        batch.create_foreign_key("fk_projects_cohort_id", "cohorts", ["cohort_id"], ["id"])
        batch.alter_column("template_id", existing_type=sa.String(64), nullable=True)
        batch.alter_column("event_date", existing_type=sa.Date(), nullable=True)
    op.create_index("ix_projects_program_id", "projects", ["program_id"])
    op.create_index("ix_projects_cohort_id", "projects", ["cohort_id"])
    op.create_index("ix_projects_activity_type", "projects", ["activity_type"])

    connection = op.get_bind()
    projects = connection.execute(sa.text(
        "SELECT id, name, type, start_date, event_date, status, created_at FROM projects"
    )).mappings().all()
    now = datetime.now(UTC)
    for project in projects:
        program_id = str(uuid4())
        end_date = project["event_date"] or project["start_date"]
        connection.execute(sa.text("""
            INSERT INTO programs
            (id, name, program_type, start_date, end_date, status, created_at, updated_at)
            VALUES (:id, :name, :program_type, :start_date, :end_date, :status, :created_at, :updated_at)
        """), {
            "id": program_id,
            "name": project["name"],
            "program_type": "annual_continuous",
            "start_date": project["start_date"],
            "end_date": end_date,
            "status": project["status"] if project["status"] != "removed" else "archived",
            "created_at": project["created_at"] or now,
            "updated_at": now,
        })
        connection.execute(sa.text("""
            UPDATE projects SET program_id=:program_id, activity_type=type,
                end_date=COALESCE(event_date, start_date), updated_at=:updated_at
            WHERE id=:project_id
        """), {"program_id": program_id, "updated_at": now, "project_id": project["id"]})


def downgrade() -> None:
    op.drop_index("ix_projects_activity_type", table_name="projects")
    op.drop_index("ix_projects_cohort_id", table_name="projects")
    op.drop_index("ix_projects_program_id", table_name="projects")
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_projects_cohort_id", type_="foreignkey")
        batch.drop_constraint("fk_projects_program_id", type_="foreignkey")
        for name in [
            "archived_at", "updated_at", "current_phase", "progress_override",
            "participant_count", "business_unit", "location", "owner_name",
            "end_date", "activity_type", "cohort_id", "program_id",
        ]:
            batch.drop_column(name)
        batch.alter_column("template_id", existing_type=sa.String(64), nullable=False)
        batch.alter_column("event_date", existing_type=sa.Date(), nullable=False)
    op.drop_table("cohorts")
    op.drop_table("programs")
