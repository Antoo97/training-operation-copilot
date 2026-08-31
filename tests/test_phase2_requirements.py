from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.main import (
    delete_material_requirement, delete_publicity_requirement,
    get_requirements_summary, patch_budget_item, patch_budget_sheet, patch_reference_price, remove_reference_price,
    patch_material_requirement, patch_publicity_requirement, publicity_calendar,
    post_budget_item, post_budget_sheet, post_material_requirement, remove_budget_sheet,
    post_publicity_requirement,
)
from app.models import ProjectActivityLog, ReferencePrice
from app.schemas import (
    BudgetItemCreate, BudgetItemUpdate, BudgetSheetCreate, BudgetSheetUpdate,
    MaterialRequirementCreate, MaterialRequirementUpdate, ProjectCreate, PublicityRequirementCreate, PublicityRequirementUpdate,
    ReferencePriceUpdate,
)
from app.services.projects import create_project
from app.services.seed import load_offline_training_seed, load_reference_price_seed


def test_phase2_budget_snapshot_summary_and_requirements() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        load_offline_training_seed(db)
        load_reference_price_seed(db)
        activity = create_project(
            db,
            ProjectCreate(
                name="Phase 2测试活动",
                template_id="tpl_offline_training_v1_0",
                start_date=date(2026, 9, 1),
                event_date=date(2026, 10, 1),
            ),
        )
        reference = db.get(ReferencePrice, "rp_refreshments")
        reference.unit_price = Decimal("38.50")
        db.commit()

        sheet = post_budget_sheet(
            BudgetSheetCreate(program_id=activity.program_id, activity_id=activity.id, owner_name="王五"),
            db,
            "王五",
        )
        sheet = patch_budget_sheet(
            sheet.id,
            BudgetSheetUpdate(status="in_review", actual_apply_date=date(2026, 9, 10)),
            db,
            "王五",
        )
        assert sheet.status == "in_review"
        item = post_budget_item(
            sheet.id,
            BudgetItemCreate(
                expense_name="茶歇",
                quantity=Decimal("30"),
                reference_price_id=reference.id,
            ),
            db,
            "王五",
        )
        assert item.reference_unit_price == Decimal("38.50")
        assert item.estimated_amount == Decimal("1155.00")

        patch_reference_price(reference.id, ReferencePriceUpdate(unit_price=Decimal("45.00")), db)
        db.refresh(item)
        assert item.reference_unit_price == Decimal("38.50")
        assert item.estimated_amount == Decimal("1155.00")

        item = patch_budget_item(
            item.id,
            BudgetItemUpdate(quantity=Decimal("32"), status="approved"),
            db,
            "赵六",
        )
        assert item.estimated_amount == Decimal("1232.00")
        assert item.status == "approved"

        remove_reference_price(reference.id, db)
        db.refresh(reference)
        assert reference.is_active is False
        db.refresh(item)
        assert item.reference_unit_price == Decimal("38.50")

        material = post_material_requirement(
            MaterialRequirementCreate(
                program_id=activity.program_id,
                activity_id=activity.id,
                budget_item_id=item.id,
                name="学员手册",
                quantity=Decimal("32"),
                specification="A4装订",
                owner_name="赵六",
                include_in_budget=True,
            ),
            db,
            "赵六",
        )
        publicity = post_publicity_requirement(
            PublicityRequirementCreate(
                program_id=activity.program_id,
                activity_id=activity.id,
                content_type="图文/新闻稿",
                quantity=1,
                owner_name="钱七",
            ),
            db,
            "钱七",
        )
        assert material.budget_item_id == item.id
        assert publicity.status == "pending"
        patch_material_requirement(material.id, MaterialRequirementUpdate(status="in_progress"), db, "赵六")
        patch_publicity_requirement(publicity.id, PublicityRequirementUpdate(start_date=date(2026, 9, 12), expected_completion_date=date(2026, 9, 18), publish_date=date(2026, 9, 20)), db, "钱七")
        calendar_rows = publicity_calendar(2026, db)
        assert {row["date_type"] for row in calendar_rows} == {"制作DDL", "预计发布日期"}

        summary = get_requirements_summary(activity.program_id, db)
        assert summary["budget_total"] == Decimal("1232.00")
        assert summary["budget_sheet_count"] == 1
        assert summary["material_total"] == 1
        assert summary["publicity_total"] == 1
        assert db.query(ProjectActivityLog).filter(
            ProjectActivityLog.module.in_(["budget", "material", "publicity"])
        ).count() >= 5

        remove_budget_sheet(sheet.id, db, "王五")
        assert get_requirements_summary(activity.program_id, db)["budget_sheet_count"] == 0
        db.refresh(material)
        assert material.budget_item_id is None
        delete_material_requirement(material.id, db, "赵六")
        delete_publicity_requirement(publicity.id, db, "钱七")
        assert get_requirements_summary(activity.program_id, db)["material_total"] == 0
        assert get_requirements_summary(activity.program_id, db)["publicity_total"] == 0


def test_reference_seed_has_names_without_invented_prices() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        load_reference_price_seed(db)
        prices = db.query(ReferencePrice).all()
        assert len(prices) == 8
        assert all(item.unit_price is None and item.min_price is None and item.max_price is None for item in prices)
