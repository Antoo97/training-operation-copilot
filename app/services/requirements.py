from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    BudgetItem, BudgetSheet, MaterialRequirement, Program, Project,
    PublicityRequirement, ReferencePrice,
)
from app.schemas import BudgetItemCreate, BudgetItemUpdate, BudgetSheetCreate


MONEY = Decimal("0.01")


def money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def require_program(db: Session, program_id: str) -> Program:
    program = db.get(Program, program_id)
    if program is None:
        raise ValueError("培训项目不存在")
    return program


def validate_activity(db: Session, program_id: str, activity_id: str | None) -> Project | None:
    if activity_id is None:
        return None
    activity = db.get(Project, activity_id)
    if activity is None or activity.program_id != program_id:
        raise ValueError("培养活动不属于所选培训项目")
    return activity


def validate_budget_item_link(db: Session, program_id: str, budget_item_id: str | None) -> BudgetItem | None:
    if budget_item_id is None:
        return None
    item = db.scalar(
        select(BudgetItem).join(BudgetSheet).where(
            BudgetItem.id == budget_item_id,
            BudgetSheet.program_id == program_id,
        )
    )
    if item is None:
        raise ValueError("预算项不属于所选培训项目")
    return item


def create_budget_sheet(db: Session, payload: BudgetSheetCreate) -> BudgetSheet:
    require_program(db, payload.program_id)
    validate_activity(db, payload.program_id, payload.activity_id)
    if payload.activity_id:
        existing = db.scalar(select(BudgetSheet).where(BudgetSheet.activity_id == payload.activity_id))
        if existing:
            raise ValueError("该培养活动已经有预算表")
    else:
        existing = db.scalar(select(BudgetSheet).where(
            BudgetSheet.program_id == payload.program_id,
            BudgetSheet.activity_id.is_(None),
        ))
        if existing:
            raise ValueError("该培训项目已经有项目级预算表")
    sheet = BudgetSheet(id=str(uuid4()), **payload.model_dump())
    db.add(sheet)
    db.commit()
    return get_budget_sheet(db, sheet.id)


def get_budget_sheet(db: Session, sheet_id: str) -> BudgetSheet:
    sheet = db.scalar(
        select(BudgetSheet).options(selectinload(BudgetSheet.items)).where(BudgetSheet.id == sheet_id)
    )
    if sheet is None:
        raise ValueError("预算表不存在")
    return sheet


def apply_reference_snapshot(item: BudgetItem, reference: ReferencePrice | None) -> None:
    item.reference_price_id = reference.id if reference else None
    item.reference_unit_price = reference.unit_price if reference else None
    item.reference_min_price = reference.min_price if reference else None
    item.reference_max_price = reference.max_price if reference else None
    if reference:
        item.unit = item.unit or reference.unit
        if item.estimated_unit_price is None:
            item.estimated_unit_price = reference.unit_price or reference.min_price


def recalculate_budget_item(item: BudgetItem, *, explicit_amount: Decimal | None = None) -> None:
    if explicit_amount is not None:
        item.estimated_amount = money(explicit_amount)
        item.amount_overridden = True
    else:
        item.estimated_amount = money(Decimal(item.quantity) * Decimal(item.estimated_unit_price or 0))
        item.amount_overridden = False


def create_budget_item(db: Session, sheet_id: str, payload: BudgetItemCreate) -> BudgetItem:
    sheet = get_budget_sheet(db, sheet_id)
    values = payload.model_dump(exclude={"estimated_amount"})
    reference_id = values.pop("reference_price_id", None)
    item = BudgetItem(id=str(uuid4()), budget_sheet_id=sheet.id, **values)
    reference = db.get(ReferencePrice, reference_id) if reference_id else None
    if reference_id and (reference is None or not reference.is_active):
        raise ValueError("参考价格不存在或已停用")
    apply_reference_snapshot(item, reference)
    recalculate_budget_item(item, explicit_amount=payload.estimated_amount)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_budget_item(db: Session, item: BudgetItem, payload: BudgetItemUpdate) -> BudgetItem:
    values = payload.model_dump(exclude_unset=True)
    explicit_amount = values.pop("estimated_amount", None) if "estimated_amount" in values else None
    reference_changed = "reference_price_id" in values
    reference_id = values.pop("reference_price_id", None) if reference_changed else None
    for key, value in values.items():
        setattr(item, key, value)
    if reference_changed:
        reference = db.get(ReferencePrice, reference_id) if reference_id else None
        if reference_id and (reference is None or not reference.is_active):
            raise ValueError("参考价格不存在或已停用")
        apply_reference_snapshot(item, reference)
    if explicit_amount is not None:
        recalculate_budget_item(item, explicit_amount=explicit_amount)
    elif any(key in values for key in {"quantity", "estimated_unit_price"}) or reference_changed:
        recalculate_budget_item(item)
    db.commit()
    db.refresh(item)
    return item


def program_budget_total(db: Session, program_id: str) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(BudgetItem.estimated_amount), 0))
        .join(BudgetSheet)
        .where(BudgetSheet.program_id == program_id, BudgetItem.is_involved.is_(True))
    )
    return money(value)


def requirements_counts(db: Session, program_id: str) -> dict:
    require_program(db, program_id)
    material_total = db.scalar(select(func.count(MaterialRequirement.id)).where(MaterialRequirement.program_id == program_id)) or 0
    material_open = db.scalar(select(func.count(MaterialRequirement.id)).where(
        MaterialRequirement.program_id == program_id,
        MaterialRequirement.status != "done",
    )) or 0
    material_done = material_total - material_open
    publicity_total = db.scalar(select(func.count(PublicityRequirement.id)).where(PublicityRequirement.program_id == program_id)) or 0
    publicity_open = db.scalar(select(func.count(PublicityRequirement.id)).where(
        PublicityRequirement.program_id == program_id,
        PublicityRequirement.status != "done",
    )) or 0
    publicity_done = publicity_total - publicity_open
    sheet_count = db.scalar(select(func.count(BudgetSheet.id)).where(BudgetSheet.program_id == program_id)) or 0
    return {
        "program_id": program_id,
        "budget_total": program_budget_total(db, program_id),
        "budget_sheet_count": sheet_count,
        "material_total": material_total,
        "material_open": material_open,
        "material_done": material_done,
        "publicity_total": publicity_total,
        "publicity_open": publicity_open,
        "publicity_done": publicity_done,
    }
