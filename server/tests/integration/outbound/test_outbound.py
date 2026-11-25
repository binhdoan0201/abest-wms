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
        db.execute(
            text(
                (
                    "UPDATE tasks SET status = 'COMPLETED' WHERE assigned_to = (SELECT "
                    "user_id FROM users WHERE username = 'nv_soan') AND status IN "
                    "('ASSIGNED', 'IN_PROGRESS');"
                )
            )
        )
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
    # 3. Nhân viên soạn xác nhận soạn toàn bộ các dòng hàng trong phiên
    cur_ver = ps_data["version_no"]
    confirm_pick_resp = None
    for idx, pl in enumerate(ps_data["lines"]):
        confirm_pick_resp = client.post(
            f"/api/v1/pick-sessions/{pick_session_id}/lines/{pl['pick_line_id']}/confirm",
            headers={"Authorization": f"Bearer {soan_token}"},
            json={
                "qty_picked": str(pl["qty_to_pick"]),
                "target_tote_barcode": f"TOTE-{idx + 1:03d}",
                "version_no": cur_ver,
            },
        )
        assert confirm_pick_resp.status_code == 200
        cur_ver = confirm_pick_resp.json()["data"]["session_version_no"]
    assert confirm_pick_resp is not None
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
    db = SessionLocal()
    try:
        db.execute(
            text(
                (
                    "UPDATE tasks SET status = 'COMPLETED' WHERE assigned_to = (SELECT "
                    "user_id FROM users WHERE username = 'nv_soan') AND status IN "
                    "('ASSIGNED', 'IN_PROGRESS');"
                )
            )
        )
        db.commit()
    finally:
        db.close()
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


def test_outbound_exception_releases_allocation_and_blocks_partial_confirm() -> None:
    """Kiểm thử: (1) confirm thiếu trả về 409; (2) exception_reason sai trả về 422;
    (3) exception hợp lệ giải phóng phân bổ RELEASED và ghi DEALLOCATE."""
    order_id, _line_id, _loc_id = _seed_stock_and_order()
    thukho_token = _login("thukho")
    soan_token = _login("nv_soan")

    # Cấp phát FEFO
    alloc_resp = client.post(
        f"/api/v1/outbound-orders/{order_id}/allocate",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"strategy": "FEFO"},
    )
    assert alloc_resp.status_code == 200

    # Tạo phiên soạn giao cho nv_soan
    soan_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {soan_token}"}
    ).json()["data"]
    ps_resp = client.post(
        "/api/v1/pick-sessions",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"order_ids": [str(order_id)], "picker_user_id": soan_me["user_id"]},
    )
    assert ps_resp.status_code == 201
    ps_data = ps_resp.json()["data"]
    ps_id = ps_data["pick_session_id"]
    line_id = ps_data["lines"][0]["pick_line_id"]

    # 1. Cố tình confirm thiếu hàng -> phải bị chặn 409 OUTBOUND_PARTIAL_PICK_REQUIRES_EXCEPTION
    bad_confirm = client.post(
        f"/api/v1/pick-sessions/{ps_id}/lines/{line_id}/confirm",
        headers={"Authorization": f"Bearer {soan_token}"},
        json={"qty_picked": "1"},
    )
    assert bad_confirm.status_code == 409
    assert bad_confirm.json()["error"]["code"] == "OUTBOUND_PARTIAL_PICK_REQUIRES_EXCEPTION"

    # 2. Báo ngoại lệ với reason code không tồn tại -> phải trả về 422 OUTBOUND_INVALID_REASON_CODE
    bad_exc = client.post(
        f"/api/v1/pick-sessions/{ps_id}/lines/{line_id}/exception",
        headers={"Authorization": f"Bearer {soan_token}"},
        json={
            "exception_type": "EXCEPTION_SHORT",
            "exception_reason": "NON_EXISTENT_CODE_XYZ",
            "qty_actual": "1",
        },
    )
    assert bad_exc.status_code == 422
    assert bad_exc.json()["error"]["code"] == "OUTBOUND_INVALID_REASON_CODE"

    # 3. Lấy một reason_code hợp lệ trong DB và báo ngoại lệ thiếu hàng
    db = SessionLocal()
    try:
        reason_code = db.execute(
            text("SELECT reason_code FROM reason_codes WHERE is_active = TRUE LIMIT 1;")
        ).scalar_one()
    finally:
        db.close()

    ok_exc = client.post(
        f"/api/v1/pick-sessions/{ps_id}/lines/{line_id}/exception",
        headers={"Authorization": f"Bearer {soan_token}"},
        json={
            "exception_type": "EXCEPTION_SHORT",
            "exception_reason": reason_code,
            "qty_actual": "1",
        },
    )
    assert ok_exc.status_code == 200
    assert ok_exc.json()["data"]["status"] == "EXCEPTION_SHORT"

    # Kiểm tra DB: allocation chuyển sang RELEASED và sổ cái có DEALLOCATE
    db = SessionLocal()
    try:
        alloc_status = db.execute(
            text(
                (
                    "SELECT ia.status FROM inventory_allocations ia JOIN outbound_order_lines "
                    "l ON l.order_line_id = ia.order_line_id WHERE l.order_id = :oid LIMIT 1;"
                )
            ),
            {"oid": order_id},
        ).scalar_one()
        assert alloc_status == "RELEASED"
        dealloc_cnt = db.execute(
            text(
                (
                    "SELECT COUNT(*) FROM inventory_transactions WHERE ref_doc_id = :psid AND "
                    "tx_type = 'DEALLOCATE';"
                )
            ),
            {"psid": uuid.UUID(ps_id)},
        ).scalar_one()
        assert int(dealloc_cnt) >= 1
        st = db.execute(
            text("SELECT status FROM outbound_orders WHERE order_id = :oid;"), {"oid": order_id}
        ).scalar_one()
        assert st == "ON_HOLD"
    finally:
        db.close()


def test_outbound_invalid_picker_and_quanly_gi_403() -> None:
    """Kiểm thử giao pick-session sai vai trò trả về 422 và quanly xác nhận GI bị 403."""
    order_id, _line_id, _loc_id = _seed_stock_and_order()
    thukho_token = _login("thukho")
    dongoi_token = _login("nv_dongoi")
    quanly_token = _login("quanly")

    assert (
        client.post(
            f"/api/v1/outbound-orders/{order_id}/allocate",
            headers={"Authorization": f"Bearer {thukho_token}"},
            json={"strategy": "FEFO"},
        ).status_code
        == 200
    )

    dongoi_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {dongoi_token}"}
    ).json()["data"]
    ps_resp = client.post(
        "/api/v1/pick-sessions",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"order_ids": [str(order_id)], "picker_user_id": dongoi_me["user_id"]},
    )
    assert ps_resp.status_code == 422
    assert ps_resp.json()["error"]["code"] == "OUTBOUND_INVALID_PICKER"

    gi_resp = client.post(
        f"/api/v1/goods-issues/{uuid.uuid4()}/confirm",
        headers={"Authorization": f"Bearer {quanly_token}"},
        json={"carrier_name": "GHN", "vehicle_plate": "43C-12345", "driver_signed": True},
    )
    assert gi_resp.status_code == 403
    assert gi_resp.json()["error"]["code"] == "FORBIDDEN"


def test_outbound_lot_substitution_and_exception_stock_state() -> None:
    """Kiểm thử thay lô đủ tồn cập nhật đúng tồn kho 2 lô và trạng thái đơn sau exception."""
    db = SessionLocal()
    try:
        db.execute(
            text(
                (
                    "UPDATE tasks SET status = 'COMPLETED' WHERE assigned_to = (SELECT "
                    "user_id FROM users WHERE username = 'nv_soan') AND status IN "
                    "('ASSIGNED', 'IN_PROGRESS');"
                )
            )
        )
        db.execute(
            text(
                (
                    "UPDATE inventory_balances SET qty_available = 0 WHERE warehouse_id = :wh "
                    "AND sku_id = :sku;"
                )
            ),
            {"wh": WAREHOUSE_ID, "sku": SKU_ID},
        )
        loc_id = db.execute(
            text(
                (
                    "SELECT location_id FROM locations WHERE warehouse_id = :wh AND "
                    "location_code = 'LOC-A01-01';"
                )
            ),
            {"wh": WAREHOUSE_ID},
        ).scalar_one()
        actor_id = db.execute(
            text("SELECT user_id FROM users WHERE username = 'thukho' LIMIT 1;")
        ).scalar_one()
        lot1_id, lot2_id = uuid.uuid4(), uuid.uuid4()
        db.execute(
            text(
                (
                    "INSERT INTO lots (lot_id, sku_id, lot_number, expiry_date) VALUES (:l1, "
                    ":sku, :n1, CURRENT_DATE + 10), (:l2, :sku, :n2, CURRENT_DATE + 60);"
                )
            ),
            {
                "l1": lot1_id,
                "l2": lot2_id,
                "sku": SKU_ID,
                "n1": f"LOT-OLD-{lot1_id.hex[:6]}",
                "n2": f"LOT-NEW-{lot2_id.hex[:6]}",
            },
        )
        for lid in (lot1_id, lot2_id):
            apply_movement(
                db=db,
                warehouse_id=WAREHOUSE_ID,
                location_id=loc_id,
                sku_id=SKU_ID,
                lot_id=lid,
                pallet_id=None,
                serial_number=None,
                tx_type="ADJUSTMENT",
                delta_available=Decimal("10.000"),
                ref_doc_type="TEST_LOT_SEED",
                ref_doc_id=uuid.uuid4(),
                performed_by=actor_id,
            )
        order_id, order_line_id = uuid.uuid4(), uuid.uuid4()
        db.execute(
            text(
                (
                    "INSERT INTO outbound_orders (order_id, erp_order_number, order_type, "
                    "warehouse_id, customer_id, status, cutoff_time) VALUES (:oid, :erp, "
                    "'SO', :wh, :cust, 'NEW', NOW() + INTERVAL '6 hours');"
                )
            ),
            {
                "oid": order_id,
                "erp": f"SO-LOT-{order_id.hex[:8].upper()}",
                "wh": WAREHOUSE_ID,
                "cust": CUSTOMER_ID,
            },
        )
        db.execute(
            text(
                (
                    "INSERT INTO outbound_order_lines (order_line_id, order_id, sku_id, "
                    "qty_ordered) VALUES (:lid, :oid, :sku, 4.000);"
                )
            ),
            {"lid": order_line_id, "oid": order_id, "sku": SKU_ID},
        )
        db.commit()
    finally:
        db.close()

    thukho_token, soan_token = _login("thukho"), _login("nv_soan")
    soan_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {soan_token}"}
    ).json()["data"]
    assert (
        client.post(
            f"/api/v1/outbound-orders/{order_id}/allocate",
            headers={"Authorization": f"Bearer {thukho_token}"},
            json={"strategy": "FEFO"},
        ).status_code
        == 200
    )
    ps_data = client.post(
        "/api/v1/pick-sessions",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"order_ids": [str(order_id)], "picker_user_id": soan_me["user_id"]},
    ).json()["data"]
    assert (
        client.post(
            f"/api/v1/pick-sessions/{ps_data['pick_session_id']}/lines/{ps_data['lines'][0]['pick_line_id']}/confirm",
            headers={"Authorization": f"Bearer {soan_token}"},
            json={
                "qty_picked": "4",
                "actual_lot_id": str(lot2_id),
                "version_no": ps_data["version_no"],
            },
        ).status_code
        == 200
    )

    db = SessionLocal()
    try:
        assert Decimal(
            str(
                db.execute(
                    text(
                        (
                            "SELECT qty_available FROM inventory_balances WHERE location_id = :loc "
                            "AND sku_id = :sku AND lot_id = :lot;"
                        )
                    ),
                    {"loc": loc_id, "sku": SKU_ID, "lot": lot1_id},
                ).scalar_one()
            )
        ) == Decimal("10.000")
        assert Decimal(
            str(
                db.execute(
                    text(
                        (
                            "SELECT qty_available FROM inventory_balances WHERE location_id = :loc "
                            "AND sku_id = :sku AND lot_id = :lot;"
                        )
                    ),
                    {"loc": loc_id, "sku": SKU_ID, "lot": lot2_id},
                ).scalar_one()
            )
        ) == Decimal("6.000")
    finally:
        db.close()


def test_outbound_c08_picking_exception_form_end_to_end() -> None:
    from client.app.core.api_client import ApiClient
    from client.app.main import app as client_app

    thukho_token = _login("thukho")
    soan_token = _login("nv_soan")
    order_id, _, _ = _seed_stock_and_order()
    r_alloc = client.post(
        f"/api/v1/outbound-orders/{order_id}/allocate",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"strategy": "FEFO"},
    )
    assert r_alloc.status_code == 200
    soan_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {soan_token}"}
    ).json()["data"]
    r_ps = client.post(
        "/api/v1/pick-sessions",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"order_ids": [str(order_id)], "picker_user_id": soan_me["user_id"]},
    )
    assert r_ps.status_code == 201
    ps_data = r_ps.json()["data"]
    ps_id = ps_data["pick_session_id"]
    line_id = ps_data["lines"][0]["pick_line_id"]
    orig = ApiClient.backend_app
    ApiClient.backend_app = app
    try:
        web = TestClient(client_app)
        page = web.get(
            f"/outbound/picking?session_id={ps_id}",
            cookies={"abest_session": soan_token},
            follow_redirects=False,
        )
        assert page.status_code == 200
        assert "DISCREPANCY_SHORT" in page.text
        assert "SHORTAGE" not in page.text
        submit = web.post(
            f"/outbound/pick-sessions/{ps_id}/lines/{line_id}/exception",
            data={
                "exception_type": "EXCEPTION_SHORT",
                "exception_reason": "DISCREPANCY_SHORT",
                "qty_actual": "0",
                "version_no": str(ps_data["version_no"]),
                "pick_action_url": "/outbound/picking",
            },
            headers={"HX-Request": "true"},
            cookies={"abest_session": soan_token},
        )
        assert submit.status_code == 200
        assert "Đã ghi nhận ngoại lệ dòng soạn hàng!" in submit.text
        assert "ON_HOLD_SHORTAGE" in submit.text
    finally:
        ApiClient.backend_app = orig
