"""add Phase 2 budgets, reference prices, materials and publicity"""

from alembic import op
import sqlalchemy as sa


revision = "0004_phase2_requirements"
down_revision = "0003_phase1c_task_workbench"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reference_prices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expense_name", sa.String(200), nullable=False),
        sa.Column("price_type", sa.String(16), nullable=False, server_default="unit"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("min_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reference_prices_expense_name", "reference_prices", ["expense_name"])
    op.create_index("ix_reference_prices_is_active", "reference_prices", ["is_active"])
    op.create_table(
        "budget_sheets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("owner_name", sa.String(500), nullable=True),
        sa.Column("planned_apply_date", sa.Date(), nullable=True),
        sa.Column("actual_apply_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_confirmation"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_budget_sheets_program_id", "budget_sheets", ["program_id"])
    op.create_index("ix_budget_sheets_activity_id", "budget_sheets", ["activity_id"])
    op.create_index("ix_budget_sheets_status", "budget_sheets", ["status"])
    op.create_table(
        "budget_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("budget_sheet_id", sa.String(36), sa.ForeignKey("budget_sheets.id"), nullable=False),
        sa.Column("expense_name", sa.String(200), nullable=False),
        sa.Column("is_involved", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("reference_price_id", sa.String(36), sa.ForeignKey("reference_prices.id"), nullable=True),
        sa.Column("reference_unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("reference_min_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("reference_max_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("amount_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_budget_items_budget_sheet_id", "budget_items", ["budget_sheet_id"])
    op.create_table(
        "material_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("budget_item_id", sa.String(36), sa.ForeignKey("budget_items.id"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("specification", sa.String(500), nullable=True),
        sa.Column("owner_name", sa.String(500), nullable=True),
        sa.Column("content_due_date", sa.Date(), nullable=True),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_confirmation"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("include_in_budget", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ["program_id", "activity_id", "owner_name", "status"]:
        op.create_index(f"ix_material_requirements_{name}", "material_requirements", [name])
    op.create_table(
        "publicity_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("program_id", sa.String(36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("budget_item_id", sa.String(36), sa.ForeignKey("budget_items.id"), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("format", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("owner_name", sa.String(500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("expected_completion_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="requirement_confirmation"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ["program_id", "activity_id", "owner_name", "status"]:
        op.create_index(f"ix_publicity_requirements_{name}", "publicity_requirements", [name])


def downgrade() -> None:
    op.drop_table("publicity_requirements")
    op.drop_table("material_requirements")
    op.drop_table("budget_items")
    op.drop_table("budget_sheets")
    op.drop_table("reference_prices")
