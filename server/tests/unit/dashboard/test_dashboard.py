"""Unit tests cho DashboardService: số liệu task, tồn kho, đơn hàng, cảnh báo và phạm vi kho.

Mỗi test đo số liệu trước, chèn dữ liệu mẫu trong cùng phiên, đo lại và so phần chênh, rồi
rollback nên không để lại dữ liệu.
"""

import uuid
from collections.abc import Generator, Sequence
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext
from server.app.modules.dashboard import DashboardService

NOW = datetime.now(timezone.utc)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _scalar(db: Session, sql: str, **params: object) -> uuid.UUID:
    value = db.execute(text(sql), params).scalar_one()
    assert isinstance(value, uuid.UUID)
    return value


def _warehouse(db: Session) -> uuid.UUID:
    return _scalar(db, "SELECT warehouse_id FROM warehouses WHERE erp_warehouse_code = 'WH01'")


def _quanly(warehouse_id: uuid.UUID | None) -> UserContext:
    return UserContext(
        user_id=uuid.UUID("c0000000-0000-0000-0000-000000000007"),
        username="quanly",
        role_code="quanly",
        warehouse_id=warehouse_id,
        permissions={"QL-8.1": "V"},
    )


def _alert_codes(alerts: Sequence[object]) -> set[str]:
    return {a.code for a in alerts}  # type: ignore[attr-defined]


def _insert_task(
    db: Session,
    warehouse_id: uuid.UUID,
    status: str,
    priority: str = "NORMAL",
    sla_due_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    db.execute(
        text(
            "INSERT INTO tasks (warehouse_id, task_type, stage, ref_doc_type, ref_doc_id, "
            "priority, status, sla_due_at, completed_at) VALUES (:wh, 'PICKING', 'SOAN_HANG', "
            "'SO', :ref, :priority, :status, :sla, :done)"
        ),
        {
            "wh": warehouse_id,
            "ref": uuid.uuid4(),
            "priority": priority,
            "status": status,
            "sla": sla_due_at,
            "done": completed_at,
        },
    )


def test_tasks_counts_overdue_and_alerts(db: Session) -> None:
    wh = _warehouse(db)
    user = _quanly(wh)
    before = DashboardService.get_tasks(db, user)

    _insert_task(db, wh, "UNASSIGNED", "URGENT", sla_due_at=NOW - timedelta(minutes=30))
    _insert_task(db, wh, "IN_PROGRESS", sla_due_at=NOW + timedelta(hours=1))
    _insert_task(db, wh, "COMPLETED", sla_due_at=NOW + timedelta(hours=1), completed_at=NOW)
    _insert_task(db, wh, "COMPLETED", sla_due_at=NOW - timedelta(hours=2), completed_at=NOW)
    after = DashboardService.get_tasks(db, user)

    assert after.total_tasks - before.total_tasks == 4
    assert after.open_tasks - before.open_tasks == 2
    assert after.unassigned_tasks - before.unassigned_tasks == 1
    assert after.in_progress_tasks - before.in_progress_tasks == 1
    assert after.overdue_tasks - before.overdue_tasks == 1
    assert after.urgent_open_tasks - before.urgent_open_tasks == 1
    assert after.completed_today - before.completed_today == 2
    assert after.on_time_rate_today is not None
    assert after.open_by_stage.get("SOAN_HANG", 0) - before.open_by_stage.get("SOAN_HANG", 0) == 2
    overdue = [t for t in after.overdue_list if t.priority == "URGENT"]
    assert overdue and overdue[0].minutes_overdue >= 29
    assert {"TASK_OVERDUE", "TASK_URGENT_OPEN", "TASK_UNASSIGNED"} <= _alert_codes(after.alerts)
    assert after.alerts[0].level == "CRITICAL"


def test_inventory_expiry_occupancy_and_min_stock(db: Session) -> None:
    wh = _warehouse(db)
    user = _quanly(wh)
    before = DashboardService.get_inventory(db, user, near_expiry_days=30)
    narrow_before = DashboardService.get_inventory(db, user, near_expiry_days=3)

    sku_id, min_level = db.execute(
        text("SELECT sku_id, min_stock_level FROM skus WHERE sku_code = 'SKU-FOOD-001'")
    ).one()
    # Chọn hai vị trí đang trống: test module khác có thể để lại hàng ở các vị trí cố định.
    empty_locations = [
        row[0]
        for row in db.execute(
            text(
                "SELECT location_id FROM locations WHERE warehouse_id = :wh AND is_active "
                "AND status = 'EMPTY' ORDER BY location_code LIMIT 2"
            ),
            {"wh": wh},
        ).all()
    ]
    assert len(empty_locations) == 2, "Cần ít nhất 2 vị trí trống trong kho WH01"
    loc_a, loc_b = empty_locations
    today = before.scope.business_date  # ngày theo giờ Việt Nam, không theo máy chạy test
    lots = {}
    for suffix, expiry in (("NEAR", today + timedelta(days=5)), ("OLD", today - timedelta(days=1))):
        lots[suffix] = _scalar(
            db,
            "INSERT INTO lots (sku_id, lot_number, expiry_date) VALUES (:sku, :lot, :exp) "
            "RETURNING lot_id",
            sku=sku_id,
            lot=f"DASH-{suffix}-{uuid.uuid4().hex[:6]}",
            exp=expiry,
        )
    qty = min_level + 5  # đủ vượt mức tối thiểu cho SKU này
    for loc, lot, available, damaged in (
        (loc_a, lots["NEAR"], qty, 0),
        (loc_b, lots["OLD"], 2, 1),
    ):
        db.execute(
            text(
                "INSERT INTO inventory_balances (warehouse_id, location_id, sku_id, lot_id, "
                "qty_available, qty_damaged) VALUES (:wh, :loc, :sku, :lot, :a, :d)"
            ),
            {"wh": wh, "loc": loc, "sku": sku_id, "lot": lot, "a": available, "d": damaged},
        )
    db.execute(
        text("UPDATE locations SET status = 'PARTIAL' WHERE location_id IN (:a, :b)"),
        {"a": loc_a, "b": loc_b},
    )
    after = DashboardService.get_inventory(db, user, near_expiry_days=30)

    assert after.near_expiry_lots - before.near_expiry_lots == 1
    assert after.expired_lots - before.expired_lots == 1
    assert {"LOT_EXPIRED_IN_STOCK", "LOT_NEAR_EXPIRY"} <= _alert_codes(after.alerts)
    assert any(lot.days_left == 5 for lot in after.expiring_list)
    assert float(after.quantities.damaged) - float(before.quantities.damaged) == 1
    assert after.locations.occupied - before.locations.occupied == 2
    assert after.locations.occupancy_rate is not None and after.locations.occupancy_rate > 0
    assert "SKU-FOOD-001" not in {s.sku_code for s in after.below_min_stock_list}

    # Ngưỡng 3 ngày thì lô còn 5 ngày không còn tính là sắp hết hạn.
    narrow = DashboardService.get_inventory(db, user, near_expiry_days=3)
    assert narrow.near_expiry_lots == narrow_before.near_expiry_lots


def test_orders_late_on_hold_fulfillment_and_alerts(db: Session) -> None:
    wh = _warehouse(db)
    user = _quanly(wh)
    customer = _scalar(db, "SELECT customer_id FROM customers LIMIT 1")
    before = DashboardService.get_orders(db, user)

    for status, cutoff, urgent in (
        ("NEW", NOW - timedelta(hours=1), True),
        ("ON_HOLD", NOW + timedelta(minutes=5), False),
        ("SHIPPED", NOW + timedelta(minutes=5), False),
    ):
        db.execute(
            text(
                "INSERT INTO outbound_orders (erp_order_number, order_type, warehouse_id, "
                "customer_id, status, is_urgent, cutoff_time) VALUES (:no, 'SO', :wh, :cus, "
                ":st, :urg, :cut)"
            ),
            {
                "no": f"DASH-{uuid.uuid4().hex[:10]}",
                "wh": wh,
                "cus": customer,
                "st": status,
                "urg": urgent,
                "cut": cutoff,
            },
        )
    after = DashboardService.get_orders(db, user)

    assert after.outbound.open_orders - before.outbound.open_orders == 2
    assert after.outbound.late - before.outbound.late == 1
    assert after.outbound.urgent_open - before.outbound.urgent_open == 1
    assert after.outbound.on_hold - before.outbound.on_hold == 1
    assert after.outbound.due_today_shipped - before.outbound.due_today_shipped == 1
    assert after.outbound.fulfillment_rate_today is not None
    assert any(o.is_urgent and o.minutes_late >= 59 for o in after.late_orders)
    assert {"ORDER_LATE", "ORDER_ON_HOLD"} <= _alert_codes(after.alerts)


def test_warehouse_scope(db: Session) -> None:
    wh = _warehouse(db)
    with pytest.raises(BusinessError) as exc:
        DashboardService.get_tasks(db, _quanly(wh), uuid.uuid4())
    assert exc.value.http_status == 404

    # Người dùng gắn kho, hỏi đúng kho của mình: hợp lệ.
    assert DashboardService.get_tasks(db, _quanly(wh), wh).scope.warehouse_id == wh
    # Người dùng không gắn kho, không chọn kho: gộp mọi kho.
    assert DashboardService.get_orders(db, _quanly(None)).scope.warehouse_id is None
