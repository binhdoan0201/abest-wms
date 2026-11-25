"""Integration tests cho module integrations (A-07) qua API, đối chiếu docs/api/integrations.md.

Dùng hàm xử lý giả (đăng ký trong test) thay cho inbound/outbound chưa làm. Nhật ký và đơn
xuất do test tạo được xóa khi kết thúc module để không ảnh hưởng lần chạy sau.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.exceptions import BusinessError
from server.app.integrations.erp_mock import get_erp_gateway
from server.app.integrations.tms_mock import get_tms_gateway
from server.app.main import app
from server.app.modules.integrations import register_erp_handler
from server.app.modules.integrations.services import unregister_erp_handler

client = TestClient(app)
_created_orders: list[str] = []
_marker = f"T{uuid.uuid4().hex[:6].upper()}"


def _h(username: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo@123456"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.fixture(scope="module")
def admin() -> dict[str, str]:
    return _h("admin")


@pytest.fixture(scope="module")
def quanly() -> dict[str, str]:
    return _h("quanly")


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    for doc_type in ("PO", "ASN", "SO"):
        unregister_erp_handler(doc_type)
    get_erp_gateway().configure_failures("NONE", 0)
    get_tms_gateway().configure_failures("NONE", 0)
    yield
    for doc_type in ("PO", "ASN", "SO"):
        unregister_erp_handler(doc_type)


@pytest.fixture(scope="module", autouse=True)
def _cleanup() -> Iterator[None]:
    yield
    db = SessionLocal()
    try:
        db.execute(
            text(
                "DELETE FROM integration_sync_logs "
                "WHERE business_payload::text LIKE :m OR doc_id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"m": f"%{_marker}%", "ids": _created_orders},
        )
        db.execute(
            text("DELETE FROM order_change_requests WHERE order_id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": _created_orders},
        )
        db.execute(
            text("DELETE FROM outbound_orders WHERE order_id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": _created_orders},
        )
        db.commit()
    finally:
        db.close()


def _po(number: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "erp_po_number": f"{_marker}-{number}",
        "warehouse_code": "WH01",
        "supplier_code": "SUPP-001",
        "expected_date": "2026-11-28",
        "lines": [
            {"line_number": 1, "sku_code": "SKU-FOOD-001", "uom_code": "BOX", "qty_ordered": "10"}
        ],
    }
    body.update(overrides)
    return body


def _log(headers: dict[str, str], sync_id: str) -> dict[str, Any]:
    resp = client.get("/api/v1/integrations/sync-logs", headers=headers, params={"page_size": 100})
    assert resp.status_code == 200
    found = [x for x in resp.json()["data"] if x["sync_id"] == sync_id]
    assert found, sync_id
    result: dict[str, Any] = found[0]
    return result


# ----------------------------------------------------------------------------- quyền


def test_rbac() -> None:
    worker = _h("nv_nhan")
    assert client.post("/api/v1/integrations/erp/purchase-orders", json=_po("X")).status_code == 401
    resp = client.post("/api/v1/integrations/erp/purchase-orders", headers=worker, json=_po("X"))
    assert resp.status_code == 403
    assert client.get("/api/v1/integrations/sync-logs", headers=worker).status_code == 403

    thukho = _h("thukho")
    assert client.get("/api/v1/integrations/sync-logs", headers=thukho).status_code == 200
    resp = client.post("/api/v1/integrations/sync-logs/process", headers=thukho)
    assert resp.status_code == 403


# ----------------------------------------------------------------------------- nhận từ ERP


def test_po_without_handler_is_pending_then_processed_after_register(
    admin: dict[str, str], quanly: dict[str, str]
) -> None:
    resp = client.post("/api/v1/integrations/erp/purchase-orders", headers=admin, json=_po("P1"))
    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    assert data["status"] == "PENDING"
    sync_id = data["sync_id"]

    # admin không thấy dữ liệu nghiệp vụ; quản lý thấy dữ liệu đã đổi mã sang ID
    assert _log(admin, sync_id)["business_payload"] is None
    normalized = _log(quanly, sync_id)["business_payload"]["normalized"]
    assert normalized["supplier_id"]
    assert normalized["lines"][0]["sku_id"]
    assert normalized["lines"][0]["qty_ordered"] == "10"

    created: dict[str, Any] = {}

    def handler(db: Session, payload: dict[str, Any], actor_id: uuid.UUID) -> uuid.UUID:
        created["payload"] = payload
        return uuid.uuid4()

    register_erp_handler("PO", handler)
    resp = client.post("/api/v1/integrations/sync-logs/process", headers=quanly)
    assert resp.status_code == 200
    assert resp.json()["data"]["SUCCESS"] >= 1
    log = _log(quanly, sync_id)
    assert log["status"] == "SUCCESS"
    assert log["doc_id"]
    assert created["payload"]["erp_po_number"] == f"{_marker}-P1"


def test_po_with_handler_success_and_business_error(
    admin: dict[str, str], quanly: dict[str, str]
) -> None:
    doc_id = uuid.uuid4()
    register_erp_handler("PO", lambda db, data, actor: doc_id)
    resp = client.post("/api/v1/integrations/erp/purchase-orders", headers=admin, json=_po("P2"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["doc_id"] == str(doc_id)
    assert resp.json()["data"]["status"] == "SUCCESS"

    def reject(db: Session, data: dict[str, Any], actor: uuid.UUID) -> uuid.UUID:
        raise BusinessError(code="INBOUND_PO_DUPLICATE", message="Trùng số PO", http_status=409)

    register_erp_handler("PO", reject)
    resp = client.post("/api/v1/integrations/erp/purchase-orders", headers=admin, json=_po("P3"))
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "INBOUND_PO_DUPLICATE"
    sync_id = error["details"]["sync_id"]
    assert _log(quanly, sync_id)["status"] == "FAILED_BUSINESS"

    # Lỗi nghiệp vụ không tự thử lại; người vận hành thử lại sau khi sửa, hoặc đánh dấu đã xử lý
    register_erp_handler("PO", lambda db, data, actor: doc_id)
    resp = client.post(f"/api/v1/integrations/sync-logs/{sync_id}/retry", headers=quanly)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "SUCCESS"
    resp = client.post(f"/api/v1/integrations/sync-logs/{sync_id}/retry", headers=quanly)
    assert resp.status_code == 409


def test_unknown_codes_are_logged_and_rejected(
    admin: dict[str, str], quanly: dict[str, str]
) -> None:
    body = _po(
        "P4",
        supplier_code="KHONG-CO",
        lines=[
            {"line_number": 1, "sku_code": "SKU-KHONG-CO", "uom_code": "BOX", "qty_ordered": "1"}
        ],
    )
    resp = client.post("/api/v1/integrations/erp/purchase-orders", headers=admin, json=body)
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "INTEGRATION_UNKNOWN_CODE"
    assert {m["field"] for m in error["details"]["missing"]} == {
        "supplier_code",
        "lines[0].sku_code",
    }

    sync_id = error["details"]["sync_id"]
    resp = client.post(f"/api/v1/integrations/sync-logs/{sync_id}/resolve", headers=quanly)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "RESOLVED"
    assert resp.json()["data"]["resolved_by"]


def test_payload_validation(admin: dict[str, str]) -> None:
    dup_lines = _po(
        "P5",
        lines=[
            {"line_number": 1, "sku_code": "SKU-FOOD-001", "uom_code": "BOX", "qty_ordered": "1"},
            {"line_number": 1, "sku_code": "SKU-FOOD-002", "uom_code": "PACK", "qty_ordered": "1"},
        ],
    )
    resp = client.post("/api/v1/integrations/erp/purchase-orders", headers=admin, json=dup_lines)
    assert resp.status_code == 422

    so_without_customer = {
        "erp_order_number": f"{_marker}-SO0",
        "warehouse_code": "WH01",
        "cutoff_time": "2026-11-28T10:00:00Z",
        "lines": [{"line_number": 1, "sku_code": "SKU-FOOD-001", "qty_ordered": "2"}],
    }
    resp = client.post(
        "/api/v1/integrations/erp/outbound-orders", headers=admin, json=so_without_customer
    )
    assert resp.status_code == 422

    so_without_customer["customer_code"] = "CUST-001"
    resp = client.post(
        "/api/v1/integrations/erp/outbound-orders", headers=admin, json=so_without_customer
    )
    assert resp.status_code == 202

    asn = {
        "erp_asn_number": f"{_marker}-ASN1",
        "warehouse_code": "WH01",
        "erp_po_number": f"{_marker}-P1",
        "expected_arrival_at": "2026-11-28T08:00:00Z",
        "dock_location_code": "KHONG-CO-CUA",
    }
    resp = client.post("/api/v1/integrations/erp/asns", headers=admin, json=asn)
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["missing"][0]["field"] == "dock_location_code"


# ----------------------------------------------------------------------------- đổi/hủy đơn


def _create_order() -> str:
    db = SessionLocal()
    try:
        order_id = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO outbound_orders (order_id, erp_order_number, warehouse_id, "
                "customer_id, cutoff_time) "
                "SELECT :id, :num, w.warehouse_id, c.customer_id, now() + interval '1 day' "
                "FROM warehouses w, customers c "
                "WHERE w.erp_warehouse_code = 'WH01' AND c.erp_customer_code = 'CUST-001'"
            ),
            {"id": order_id, "num": f"{_marker}-SO-{order_id[:6]}"},
        )
        db.commit()
    finally:
        db.close()
    _created_orders.append(order_id)
    return order_id


def test_order_change_cancel_accept_then_reject(admin: dict[str, str]) -> None:
    order_id = _create_order()
    url = f"/api/v1/integrations/erp/outbound-orders/{order_id}/changes"

    resp = client.post(
        url, headers=admin, json={"change_type": "CANCEL_ORDER", "reason": "Khách hủy"}
    )
    assert resp.status_code == 200, resp.text
    decision = resp.json()["data"]["decision"]
    assert decision["status"] == "ACCEPTED"
    assert decision["decision_path"] == "AUTO_ACCEPT"

    resp = client.post(url, headers=admin, json={"change_type": "CANCEL_ORDER"})
    assert resp.status_code == 200
    decision = resp.json()["data"]["decision"]
    assert decision["status"] == "REJECTED"
    assert decision["reject_reason_code"] == "CHG_ALREADY_CANCELLED"

    resp = client.post(
        f"/api/v1/integrations/erp/outbound-orders/{uuid.uuid4()}/changes",
        headers=admin,
        json={"change_type": "CANCEL_ORDER", "payload": {"test": _marker}},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["details"]["sync_id"]


# ----------------------------------------------------------------------------- gửi đi, thử lại


def test_outbox_reply_to_erp_retries_technical_error(
    admin: dict[str, str], quanly: dict[str, str]
) -> None:
    """Hủy đơn sinh phản hồi ERP (fn_enqueue_erp_change_reply); ERP lỗi kỹ thuật rồi thử lại."""
    order_id = _create_order()
    client.post(
        f"/api/v1/integrations/erp/outbound-orders/{order_id}/changes",
        headers=admin,
        json={"change_type": "CANCEL_ORDER"},
    )

    def reply_log() -> dict[str, Any]:
        resp = client.get(
            "/api/v1/integrations/sync-logs",
            headers=quanly,
            params={"direction": "OUTBOUND", "doc_type": "SO", "page_size": 100},
        )
        logs = [x for x in resp.json()["data"] if x["doc_id"] == order_id]
        assert logs
        first: dict[str, Any] = logs[0]
        return first

    assert reply_log()["status"] == "PENDING"

    resp = client.post(
        "/api/v1/integrations/mock/failures",
        headers=admin,
        json={"system": "ERP", "error_category": "TECHNICAL_ERROR", "times": 100},
    )
    assert resp.status_code == 200
    client.post("/api/v1/integrations/sync-logs/process", headers=quanly)
    log = reply_log()
    assert log["status"] == "FAILED_TECHNICAL"
    assert log["error_category"] == "TECHNICAL_ERROR"
    assert log["retry_count"] == 1

    get_erp_gateway().configure_failures("NONE", 0)
    client.post("/api/v1/integrations/sync-logs/process", headers=quanly)
    log = reply_log()
    assert log["status"] == "SUCCESS"
    assert log["technical_meta"]["response"]["erp_ref"].startswith("ERP-SO-")
