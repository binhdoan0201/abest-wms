"""Integration tests cho luồng nghiệp vụ khép kín của module Outbound."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import text

from server.app.core.database import SessionLocal
from server.app.core.exceptions import BusinessError
from server.app.main import app
from server.app.modules.inventory import apply_movement

client = TestClient(app)

WAREHOUSE_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
CUSTOMER_ID = uuid.UUID("a5000000-0000-0000-0000-000000000001")
SKU_ID = uuid.UUID("a3000000-0000-0000-0000-000000000003")
BOX_TYPE_ID = uuid.UUID("a4000000-0000-0000-0000-000000000001")


def _login(username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo@123456"},
    )
    assert resp.status_code == 200
    return str(resp.json()["data"]["access_token"])


def _seed_stock_and_order() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Tạo tồn kho khả dụng tại LOC-A01-01 và một đơn xuất kho NEW để kiểm thử E2E."""
    db = SessionLocal()
    try:
        loc_id = db.execute(
            text(
                "SELECT location_id FROM locations "
                "WHERE warehouse_id = :wh AND location_code = 'LOC-A01-01';"
            ),
            {"wh": WAREHOUSE_ID},
        ).scalar_one()

        actor_id = db.execute(
            text("SELECT user_id FROM users WHERE username = 'thukho' LIMIT 1;")
        ).scalar_one()

        apply_movement(
            db=db,
            warehouse_id=WAREHOUSE_ID,
            location_id=loc_id,
            sku_id=SKU_ID,
            lot_id=None,
            pallet_id=None,
            serial_number=None,
            tx_type="ADJUSTMENT",
            delta_available=Decimal("20.000"),
            ref_doc_type="TEST_SEED",
            ref_doc_id=uuid.uuid4(),
            performed_by=actor_id,
        )

        order_id = uuid.uuid4()
        order_line_id = uuid.uuid4()
        erp_no = f"SO-TEST-{uuid.uuid4().hex[:8].upper()}"
        cutoff = datetime.now(timezone.utc) + timedelta(hours=6)

        db.execute(
            text(
                """
                INSERT INTO outbound_orders (
                    order_id, erp_order_number, order_type, warehouse_id,
                    customer_id, status, cutoff_time
                ) VALUES (
                    :order_id, :erp_no, 'SO', :wh, :cust, 'NEW', :cutoff
                );
                """
            ),
            {
                "order_id": order_id,
                "erp_no": erp_no,
                "wh": WAREHOUSE_ID,
                "cust": CUSTOMER_ID,
                "cutoff": cutoff,
            },
        )
        db.execute(
            text(
                """
                INSERT INTO outbound_order_lines (
                    order_line_id, order_id, sku_id, qty_ordered
                ) VALUES (
                    :line_id, :order_id, :sku_id, 5.000
                );
                """
            ),
            {"line_id": order_line_id, "order_id": order_id, "sku_id": SKU_ID},
        )
        db.commit()
        return order_id, order_line_id, loc_id
    finally:
        db.close()


def test_outbound_access_control_integration() -> None:
    """Xác nhận người dùng không có quyền (nv-kiemke) bị chặn 403 khi truy cập đơn xuất."""
    token = _login("nv_kiemke")
    resp = client.get(
        "/api/v1/outbound-orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_outbound_full_flow_allocate_pick_pack_ship() -> None:
    """Kiểm thử toàn trình: Cấp phát -> Soạn hàng -> Đóng gói -> Xác nhận GI."""
    order_id, order_line_id, _loc_id = _seed_stock_and_order()
    thukho_token = _login("thukho")
    soan_token = _login("nv_soan")
    dongoi_token = _login("nv_dongoi")

    # 1. Thủ kho cấp phát tồn kho (Allocate)
    alloc_resp = client.post(
        f"/api/v1/outbound-orders/{order_id}/allocate",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"strategy": "FIFO", "version_no": 1},
    )
    assert alloc_resp.status_code == 200
    assert len(alloc_resp.json()["data"]["allocations"]) >= 1

    # Kiểm tra xung đột phiên bản (version_no cũ phải trả 409 VERSION_CONFLICT)
    conflict_resp = client.post(
        f"/api/v1/outbound-orders/{order_id}/allocate",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"strategy": "FIFO", "version_no": 1},
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["error"]["code"] == "VERSION_CONFLICT"

    # 2. Thủ kho tạo phiên soạn hàng
    ps_resp = client.post(
        "/api/v1/pick-sessions",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"order_ids": [str(order_id)], "pick_mode": "SINGLE_ORDER"},
    )
    assert ps_resp.status_code == 201
    ps_data = ps_resp.json()["data"]
    pick_session_id = ps_data["pick_session_id"]
    pick_line_id = ps_data["lines"][0]["pick_line_id"]

    # 3. Nhân viên soạn xác nhận soạn dòng hàng
    confirm_pick_resp = client.post(
        f"/api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/confirm",
        headers={"Authorization": f"Bearer {soan_token}"},
        json={"qty_picked": "5.000", "target_tote_barcode": "TOTE-001"},
    )
    assert confirm_pick_resp.status_code == 200
    assert confirm_pick_resp.json()["data"]["session_status"] == "COMPLETED"

    # 4. Nhân viên đóng gói tạo kiện hàng
    pkg_resp = client.post(
        f"/api/v1/outbound-orders/{order_id}/packages",
        headers={"Authorization": f"Bearer {dongoi_token}"},
        json={
            "box_type_id": str(BOX_TYPE_ID),
            "weight_kg": "2.500",
            "items": [
                {
                    "order_line_id": str(order_line_id),
                    "sku_id": str(SKU_ID),
                    "qty": "5.000",
                }
            ],
        },
    )
    assert pkg_resp.status_code == 201
    assert pkg_resp.json()["data"]["order_status"] == "READY_TO_SHIP"

    # 5. Nhân viên đóng gói lập phiếu xuất kho GI
    gi_resp = client.post(
        "/api/v1/goods-issues",
        headers={"Authorization": f"Bearer {dongoi_token}"},
        json={"order_id": str(order_id), "tms_waybill_code": "WB-2026-001"},
    )
    assert gi_resp.status_code == 201
    gi_id = gi_resp.json()["data"]["gi_id"]
    assert gi_resp.json()["data"]["total_packages"] == 1

    # 6. Test Rollback (Mục 9.4): Ép lỗi trừ tồn -> GI không đổi sang GI_CONFIRMED
    with patch(
        "server.app.modules.outbound.services.apply_movement",
        side_effect=BusinessError(
            code="INVENTORY_INSUFFICIENT_QTY",
            message="Giả lập lỗi trừ tồn kho",
            http_status=409,
        ),
    ):
        fail_confirm = client.post(
            f"/api/v1/goods-issues/{gi_id}/confirm",
            headers={"Authorization": f"Bearer {dongoi_token}"},
            json={"driver_signature_data": "data:image/png;base64,SIGN_OK"},
        )
        assert fail_confirm.status_code == 409

    # Xác nhận trạng thái đơn vẫn chưa SHIPPED sau rollback
    order_check = client.get(
        f"/api/v1/outbound-orders/{order_id}",
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert order_check.json()["data"]["status"] == "READY_TO_SHIP"

    # 7. Xác nhận GI thành công -> đơn chuyển SHIPPED và trừ tồn kho
    confirm_gi_resp = client.post(
        f"/api/v1/goods-issues/{gi_id}/confirm",
        headers={"Authorization": f"Bearer {dongoi_token}"},
        json={"driver_signature_data": "data:image/png;base64,SIGN_OK"},
    )
    assert confirm_gi_resp.status_code == 200
    assert confirm_gi_resp.json()["data"]["status"] == "GI_CONFIRMED"
    assert confirm_gi_resp.json()["data"]["order_status"] == "SHIPPED"


def test_erp_order_change_freeze_and_manager_decide() -> None:
    """Kiểm thử đóng băng đơn khi ERP yêu cầu hủy và Quản lý chốt ACCEPT."""
    order_id, _line_id, _loc_id = _seed_stock_and_order()
    thukho_token = _login("thukho")
    quanly_token = _login("quanly")

    # Cấp phát và đưa đơn sang PICKING
    client.post(
        f"/api/v1/outbound-orders/{order_id}/allocate",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"strategy": "FIFO"},
    )
    client.post(
        "/api/v1/pick-sessions",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"order_ids": [str(order_id)]},
    )

    # Giả lập ERP gửi yêu cầu hủy đơn qua hàm DB fn_receive_erp_order_change
    db = SessionLocal()
    try:
        admin_id = db.execute(
            text("SELECT user_id FROM users WHERE username = 'admin' LIMIT 1;")
        ).scalar_one()
        req_id = db.execute(
            text(
                "SELECT fn_receive_erp_order_change("
                ":order_id, 'CANCEL_ORDER', '{}'::jsonb, :actor);"
            ),
            {"order_id": order_id, "actor": admin_id},
        ).scalar_one()
        db.commit()
    finally:
        db.close()

    # Quản lý chốt ACCEPT hủy đơn
    decide_resp = client.post(
        f"/api/v1/order-changes/{req_id}/decide",
        headers={"Authorization": f"Bearer {quanly_token}"},
        json={"decision": "ACCEPT", "reject_note": "Đồng ý hủy theo yêu cầu ERP"},
    )
    assert decide_resp.status_code == 200
    assert decide_resp.json()["data"]["order_status"] == "CANCELLED"
    assert decide_resp.json()["data"]["erp_change_pending"] is False
