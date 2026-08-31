from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models  # noqa: F401


PARTIAL_V2_TABLES = [
    "task_resource_links",
    "resources",
    "alerts",
    "publicity_requirements",
    "material_requirements",
    "budget_items",
    "budget_sheets",
    "reference_prices",
    "project_activity_logs",
    "subtasks",
    "training_classes",
    "cohorts",
    "programs",
]


def recover_interrupted_v2_bootstrap(connection) -> None:
    """Remove only empty v2 artifacts left by the 2026-08 concurrent deploy.

    Legacy projects/tasks remain untouched. Reference prices are deterministic
    seed data and are recreated during application startup.
    """
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if not {"projects", "alembic_version"}.issubset(tables):
        return
    revision = connection.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if revision != "0001_v01_baseline" or "program_id" in project_columns:
        return
    existing = [name for name in PARTIAL_V2_TABLES if name in tables]
    for name in existing:
        count = connection.scalar(text(f'SELECT COUNT(*) FROM "{name}"'))
        if count and name != "reference_prices":
            raise RuntimeError(
                f"Interrupted v2 table {name} contains data; automatic recovery stopped"
            )
    for name in existing:
        connection.execute(text(f'DROP TABLE IF EXISTS "{name}"'))


def migrate() -> None:
    config = Config("alembic.ini")
    with engine.begin() as connection:
        is_postgres = connection.dialect.name == "postgresql"
        lock_key = 814_726_195_001
        if is_postgres:
            # Render can start an Auto-Deploy and a Blueprint deploy together.
            # A session advisory lock serializes all schema inspection, stamp,
            # and upgrade work against the shared Supabase database.
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
        try:
            config.attributes["connection"] = connection
            recover_interrupted_v2_bootstrap(connection)
            tables = set(inspect(connection).get_table_names())
            if "alembic_version" not in tables:
                if "projects" in tables:
                    # Existing pre-Alembic v0.1 database: its schema is the baseline.
                    command.stamp(config, "0001_v01_baseline")
                else:
                    # Fresh installation: create the current schema directly and mark
                    # it current. Migrations remain responsible for existing data.
                    Base.metadata.create_all(bind=connection)
                    command.stamp(config, "head")
                    return
            command.upgrade(config, "head")
        finally:
            # Session advisory locks are released automatically when the
            # connection closes, including after a failed transaction.
            pass


if __name__ == "__main__":
    migrate()
