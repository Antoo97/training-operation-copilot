"""v0.1 schema baseline for existing installations.

Existing v0.1 databases must be stamped at this revision before upgrading.
Fresh databases continue to be initialized by SQLAlchemy metadata before the
Phase 1 migration until the pre-Alembic bootstrap is retired.
"""

revision = "0001_v01_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
