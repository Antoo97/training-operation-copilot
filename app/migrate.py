from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models  # noqa: F401


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
            if is_postgres:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})


if __name__ == "__main__":
    migrate()
