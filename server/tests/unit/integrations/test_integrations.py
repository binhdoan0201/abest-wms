"""Unit tests cho hàm công khai của integrations: enqueue_to_erp, request_waybill, get_waybill.

Test không giả định hàng đợi trống: module khác có thể để lại dòng chờ. Vì vậy chỉ thử lại đúng
dòng của mình (`retry_log`), hoặc cấu hình đủ lỗi giả lập và bỏ giới hạn số dòng khi cần chạy
`process_pending`. Mọi thay đổi rollback cuối test.
"""

import uuid

from sqlalchemy import text

from server.app.core.database import SessionLocal
from server.app.core.rbac import UserContext
from server.app.integrations.erp_mock import get_erp_gateway
from server.app.integrations.tms_mock import get_tms_gateway
from server.app.modules.integrations import (
    IntegrationService,
    enqueue_to_erp,
    get_waybill,
    request_waybill,
)
from server.app.modules.integrations.services import MAX_RETRIES

# Đủ lớn để không bị dòng chờ của module khác dùng hết lỗi giả lập hoặc chiếm chỗ trong lô.
PLENTY = 100_000


def _warehouse_id(db: object) -> uuid.UUID:
    value = db.execute(  # type: ignore[attr-defined]
        text("SELECT warehouse_id FROM warehouses WHERE erp_warehouse_code = 'WH01'")
    ).scalar_one()
    assert isinstance(value, uuid.UUID)
    return value


def _quanly(warehouse_id: uuid.UUID) -> UserContext:
    return UserContext(
        user_id=uuid.UUID("c0000000-0000-0000-0000-000000000007"),
        username="quanly",
        role_code="quanly",
        warehouse_id=warehouse_id,
        permissions={"QL-2.1": "V"},
    )


def test_waybill_success_and_retry_after_tms_failure() -> None:
    db = SessionLocal()
    try:
        warehouse_id = _warehouse_id(db)
        get_tms_gateway().configure_failures("NONE", 0)
        gi_ok = uuid.uuid4()
        waybill = request_waybill(db, warehouse_id, gi_ok, {"gi_id": str(gi_ok)})
        assert waybill is not None and waybill.startswith("TMS")
        assert get_waybill(db, gi_ok) == waybill

        gi_wait = uuid.uuid4()
        get_tms_gateway().configure_failures("TECHNICAL_ERROR", 1)
        assert request_waybill(db, warehouse_id, gi_wait, {"gi_id": str(gi_wait)}) is None
        assert get_waybill(db, gi_wait) is None

        waybill_log = db.execute(
            text(
                "SELECT sync_id FROM integration_sync_logs "
                "WHERE external_system = 'TMS' AND doc_id = :g"
            ),
            {"g": gi_wait},
        ).scalar_one()
        IntegrationService.retry_log(db, _quanly(warehouse_id), str(waybill_log))
        assert get_waybill(db, gi_wait) is not None
    finally:
        db.rollback()
        db.close()


def test_enqueue_to_erp_stops_retrying_after_max() -> None:
    db = SessionLocal()
    try:
        warehouse_id = _warehouse_id(db)
        user = _quanly(warehouse_id)
        get_erp_gateway().configure_failures("TECHNICAL_ERROR", PLENTY)
        sync_id = enqueue_to_erp(db, warehouse_id, "GRN", uuid.uuid4(), {"grn": "test"})

        # process_pending phải tự dừng thử lại dòng này khi đủ MAX_RETRIES lần.
        for _ in range(MAX_RETRIES + 2):
            IntegrationService.process_pending(db, user, limit=PLENTY)
        retry_count, status = db.execute(
            text("SELECT retry_count, status FROM integration_sync_logs WHERE sync_id = :s"),
            {"s": sync_id},
        ).one()
        assert status == "FAILED_TECHNICAL"
        assert retry_count == MAX_RETRIES

        get_erp_gateway().configure_failures("BUSINESS_ERROR", 1)
        other = enqueue_to_erp(db, warehouse_id, "GI", uuid.uuid4(), {"gi": "test"})
        IntegrationService.retry_log(db, user, str(other))
        status = db.execute(
            text("SELECT status FROM integration_sync_logs WHERE sync_id = :s"), {"s": other}
        ).scalar_one()
        assert status == "FAILED_BUSINESS"
    finally:
        get_erp_gateway().configure_failures("NONE", 0)
        db.rollback()
        db.close()
