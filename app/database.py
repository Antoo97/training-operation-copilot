from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("TRAINING_COPILOT_DATABASE_URL", "sqlite:///./training_copilot.db")
# Some providers still expose the legacy postgres:// prefix. SQLAlchemy expects
# an explicit modern driver name.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def ensure_schema_compatibility() -> None:
    """Apply the only pre-Alembic compatibility change used by the local MVP."""
    inspector = inspect(engine)
    if "project_tasks" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("project_tasks")}
    if "completed_at" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE project_tasks ADD COLUMN completed_at TIMESTAMP"))
    inspector = inspect(engine)
    task_columns = {column["name"]: column for column in inspector.get_columns("project_tasks")}
    requires_milestone_upgrade = (
        "project_milestone_id" not in task_columns
        or not task_columns["template_task_id"]["nullable"]
        or not task_columns["milestone_id"]["nullable"]
    )
    if requires_milestone_upgrade:
        if engine.dialect.name == "sqlite":
            with engine.begin() as connection:
                connection.execute(text("""
                    CREATE TABLE project_tasks_v3 (
                        id VARCHAR(36) NOT NULL PRIMARY KEY,
                        project_id VARCHAR(36) NOT NULL REFERENCES projects(id),
                        template_task_id VARCHAR(64) REFERENCES template_tasks(id),
                        milestone_id VARCHAR(64) REFERENCES milestones(id),
                        project_milestone_id VARCHAR(36) REFERENCES project_milestones(id),
                        title VARCHAR(300) NOT NULL,
                        owner VARCHAR(200),
                        status VARCHAR(32) NOT NULL,
                        deadline DATE NOT NULL,
                        required BOOLEAN,
                        completed_at TIMESTAMP,
                        UNIQUE (project_id, template_task_id)
                    )
                """))
                project_milestone_value = (
                    "project_milestone_id" if "project_milestone_id" in task_columns else "NULL"
                )
                connection.execute(text("""
                    INSERT INTO project_tasks_v3
                    (id, project_id, template_task_id, milestone_id, project_milestone_id, title, owner, status, deadline, required, completed_at)
                    SELECT id, project_id, template_task_id, milestone_id, :project_milestone_id, title, owner, status, deadline, required, completed_at
                    FROM project_tasks
                """).bindparams(project_milestone_id=None))
                connection.execute(text("DROP TABLE project_tasks"))
                connection.execute(text("ALTER TABLE project_tasks_v3 RENAME TO project_tasks"))
                connection.execute(text("CREATE INDEX ix_project_tasks_project_id ON project_tasks (project_id)"))
                connection.execute(text("CREATE INDEX ix_project_tasks_project_milestone_id ON project_tasks (project_milestone_id)"))
        else:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE project_tasks ALTER COLUMN template_task_id DROP NOT NULL"))
                connection.execute(text("ALTER TABLE project_tasks ALTER COLUMN milestone_id DROP NOT NULL"))
                if "project_milestone_id" not in task_columns:
                    connection.execute(text(
                        "ALTER TABLE project_tasks ADD COLUMN project_milestone_id VARCHAR(36) REFERENCES project_milestones(id)"
                    ))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
