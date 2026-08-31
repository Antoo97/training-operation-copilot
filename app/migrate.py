from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import Base, engine
from app import models  # noqa: F401


def migrate() -> None:
    config = Config("alembic.ini")
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables:
        if "projects" in tables:
            # Existing pre-Alembic v0.1 database: its schema is the baseline.
            command.stamp(config, "0001_v01_baseline")
        else:
            # Fresh installation: create the current schema directly and mark
            # it current. Migrations remain responsible for existing data.
            Base.metadata.create_all(bind=engine)
            command.stamp(config, "head")
            return
    command.upgrade(config, "head")


if __name__ == "__main__":
    migrate()
