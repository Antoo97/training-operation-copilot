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
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    # A failed/concurrent production deployment may have committed an early
    # DDL statement while leaving the Alembic revision at the v0.1 baseline.
    # Every schema step is therefore safe to resume.
    if "programs" not in tables:
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
    program_indexes = {item["name"] for item in sa.inspect(connection).get_indexes("programs")}
    if "ix_programs_program_type" not in program_indexes:
        op.create_index("ix_programs_program_type", "programs", ["program_type"])
    if "ix_programs_status" not in program_indexes:
        op.create_index("ix_programs_status", "programs", ["status"])

    if "cohorts" not in set(sa.inspect(connection).get_table_names()):
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
    cohort_indexes = {item["name"] for item in sa.inspect(connection).get_indexes("cohorts")}
    if "ix_cohorts_program_id" not in cohort_indexes:
        op.create_index("ix_cohorts_program_id", "cohorts", ["program_id"])
    if "ix_cohorts_status" not in cohort_indexes:
        op.create_index("ix_cohorts_status", "cohorts", ["status"])

    project_columns = {item["name"]: item for item in sa.inspect(connection).get_columns("projects")}
    additions = {
        "program_id": sa.Column("program_id", sa.String(36), nullable=True),
        "cohort_id": sa.Column("cohort_id", sa.String(36), nullable=True),
        "activity_type": sa.Column("activity_type", sa.String(64), nullable=True),
        "end_date": sa.Column("end_date", sa.Date(), nullable=True),
        "owner_name": sa.Column("owner_name", sa.String(500), nullable=True),
        "location": sa.Column("location", sa.String(300), nullable=True),
        "business_unit": sa.Column("business_unit", sa.String(200), nullable=True),
        "participant_count": sa.Column("participant_count", sa.Integer(), nullable=True),
        "progress_override": sa.Column("progress_override", sa.Integer(), nullable=True),
        "current_phase": sa.Column("current_phase", sa.String(100), nullable=True),
        "updated_at": sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        "archived_at": sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    }
    foreign_keys = {item.get("name") for item in sa.inspect(connection).get_foreign_keys("projects")}
    with op.batch_alter_table("projects") as batch:
        for name, column in additions.items():
            if name not in project_columns:
                batch.add_column(column)
        if "fk_projects_program_id" not in foreign_keys:
            batch.create_foreign_key("fk_projects_program_id", "programs", ["program_id"], ["id"])
        if "fk_projects_cohort_id" not in foreign_keys:
            batch.create_foreign_key("fk_projects_cohort_id", "cohorts", ["cohort_id"], ["id"])
        if not project_columns["template_id"]["nullable"]:
            batch.alter_column("template_id", existing_type=sa.String(64), nullable=True)
        if not project_columns["event_date"]["nullable"]:
            batch.alter_column("event_date", existing_type=sa.Date(), nullable=True)
    project_indexes = {item["name"] for item in sa.inspect(connection).get_indexes("projects")}
    for name, column in [
        ("ix_projects_program_id", "program_id"),
        ("ix_projects_cohort_id", "cohort_id"),
        ("ix_projects_activity_type", "activity_type"),
    ]:
        if name not in project_indexes:
            op.create_index(name, "projects", [column])

    projects = connection.execute(sa.text(
        "SELECT id, name, type, start_date, event_date, status, created_at, program_id FROM projects"
    )).mappings().all()
    now = datetime.now(UTC)
    for project in projects:
        if project["program_id"] is not None:
            continue
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
