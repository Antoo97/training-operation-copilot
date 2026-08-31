from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import Milestone, ProjectTemplate, ReferencePrice, RiskRule, TemplateTask


DEFAULT_SEED_DIR = Path(__file__).resolve().parents[2] / "initialization" / "offline_training_v1_0"
REFERENCE_PRICE_SEED_DIR = Path(__file__).resolve().parents[2] / "initialization" / "reference_prices_v1"


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_offline_training_seed(db: Session, seed_dir: Path = DEFAULT_SEED_DIR) -> None:
    template_data = _read_json(seed_dir / "template.json")
    milestones_data = _read_json(seed_dir / "milestones.json")
    tasks_data = _read_json(seed_dir / "template_tasks.json")
    rules_data = _read_json(seed_dir / "risk_rules.json")

    db.merge(ProjectTemplate(**template_data))
    db.flush()

    for item in milestones_data:
        db.merge(Milestone(**item))
    db.flush()

    for item in tasks_data:
        db.merge(TemplateTask(**item))
    db.flush()

    for item in rules_data:
        db.merge(RiskRule(**item))

    db.commit()


def load_reference_price_seed(db: Session, seed_dir: Path = REFERENCE_PRICE_SEED_DIR) -> None:
    for item in _read_json(seed_dir / "reference_prices.json"):
        if db.get(ReferencePrice, item["id"]) is None:
            db.add(ReferencePrice(**item))
    db.commit()
