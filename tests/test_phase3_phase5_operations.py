import asyncio
from datetime import date, timedelta
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from fastapi import UploadFile

from app.main import download_resource, get_training_map, post_resource, link_task_resource, get_retrospective, upload_resource
from app.models import Alert, Resource, RiskRule
from app.schemas import ProjectCreate
from app.services.alerts import THRESHOLDS, evaluate
from app.services.dashboard import dashboard, focus_items, load_program
from app.services.export_excel import build_operations_workbook
from app.services.export_ics import calendar
from app.services.projects import create_project
from app.services.seed import load_offline_training_seed


def setup_activity(db: Session):
    load_offline_training_seed(db)
    today = date.today()
    return create_project(db, ProjectCreate(name="Phase 3-5 验收", template_id="tpl_offline_training_v1_0", start_date=today - timedelta(days=30), event_date=today + timedelta(days=7)))


def test_dashboard_map_alerts_focus_and_existing_rules() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        activity = setup_activity(db)
        task = activity.tasks[0]
        task.deadline = date.today() - timedelta(days=1)
        task.required = True
        db.commit()
        result = dashboard(db, activity.program_id)
        assert result["outcomes"]["task_count"] == 64
        assert result["outcomes"]["activity_count"] == 1
        alerts = evaluate(db, activity.program_id)
        assert any(x.alert_type == "overdue" and x.source_entity_id == task.id for x in alerts)
        assert any(x.rule_code.startswith("R00") for x in alerts)
        evaluate(db, activity.program_id)
        assert db.query(Alert).filter(Alert.program_id == activity.program_id, Alert.rule_code == "GEN_OVERDUE", Alert.source_entity_id == task.id).count() == 1
        assert THRESHOLDS == {"due_soon_days": 3, "stale_days": 7, "schedule_lag_points": 20, "specialty_lag_points": 25}
        assert db.query(RiskRule).count() == 9
        assert isinstance(focus_items(load_program(db, activity.program_id), date.today()), list)
        training_map = get_training_map(date.today().year, "cohort", db)
        map_item = next(x for x in training_map["items"] if x["id"] == activity.id)
        assert map_item["start_date"] == activity.event_date
        assert map_item["month"] == activity.event_date.month


def test_resources_retrospective_excel_and_ics() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        activity = setup_activity(db)
        resource = post_resource({"title": "线下培训执行 SOP", "resource_type": "sop", "url": "https://example.com/sop"}, db)
        linked = link_task_resource(activity.tasks[0].id, {"resource_id": resource["id"], "relation_type": "reference"}, db)
        assert linked["title"] == "线下培训执行 SOP"
        assert db.query(Resource).count() == 1
        uploaded = asyncio.run(upload_resource(
            UploadFile(filename="培训手册.pdf", file=BytesIO(b"sample-pdf"), headers={"content-type": "application/pdf"}),
            "培训手册", "file", "王五", "测试上传", db,
        ))
        response = download_resource(uploaded["id"], db)
        assert response.body == b"sample-pdf"
        assert uploaded["is_upload"] is True
        retro = get_retrospective(activity.program_id, db)
        assert retro["task_count"] == 64
        content = build_operations_workbook(db, load_program(db, activity.program_id))
        workbook = load_workbook(BytesIO(content))
        assert workbook.sheetnames == ["运营总览", "节点任务明细", "预算", "物料", "宣传", "项目动态"]
        detail = workbook["节点任务明细"]
        assert detail.freeze_panes == "A2"
        assert [detail.cell(1, column).value for column in range(1, 11)] == [
            "活动", "模板T日期", "节点代码", "节点名称", "节点开始", "节点截止", "层级", "任务代码", "主任务", "分支任务",
        ]
        assert detail.max_row == 65
        assert workbook["运营总览"]["A1"].value.endswith("项目运营总览")
        ics = calendar([{"uid": "task-1", "start": date(2026, 9, 1), "end": date(2026, 9, 1), "summary": "中文任务"}])
        assert "DTSTART;VALUE=DATE:20260901" in ics
        assert "DTEND;VALUE=DATE:20260902" in ics
        assert "SUMMARY:中文任务" in ics
