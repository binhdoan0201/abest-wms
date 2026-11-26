"""E2E theo kịch bản demo (A-09): ERP → nhập kho → duyệt lệch → cất → ERP → xuất kho → ERP.

Chạy trọn qua HTTP, mỗi bước bằng đúng vai trò làm việc đó ngoài đời:

    ERP đẩy PO
    → nv_nhan mở GRN, đếm mù có lệch (thiếu, hư) → nộp → chờ thủ kho duyệt (D1)
    → thukho yêu cầu đếm lại → nv_nhan2 (người khác) đếm lại đủ → nộp → (duyệt nếu cần)
    → nv_nhan hoàn tất GRN → pallet STAGED, task PUTAWAY, GRN vào hàng đợi ERP
    → nv_cat cất pallet → STORED, task PUTAWAY xong
    → ERP đẩy SO → thukho cấp phát, tạo phiên soạn giao nv_soan → nv_soan soạn
    → nv_dongoi đóng gói, lập GI (TMS cấp vận đơn), xác nhận có chữ ký tài xế → SHIPPED
    → quanly chạy hàng đợi → GRN, GI gửi ERP thành công → bgd xem dashboard.

Dùng SKU riêng `SKU-GEN-008`, nhập 10 rồi xuất đủ 10 nên không để lại tồn; dọn nhật ký đồng bộ
của các chứng từ đã tạo. Tài khoản `nv_nhan2` tạo bằng `scripts.load_demo` nếu chưa có.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from scripts.load_demo import add_second_receiver
from server.app.core.database import SessionLocal
from server.app.integrations.erp_mock import get_erp_gateway
from server.app.integrations.tms_mock import get_tms_gateway
from server.app.main import app

client = TestClient(app)
PASSWORD = "Demo@123456"
SKU_CODE = "SKU-GEN-008"
QTY = 10
_marker = uuid.uuid4().hex[:6].upper()
_created_docs: list[uuid.UUID] = []


def _sql(sql: str, **params: Any) -> Any:
    db = SessionLocal()
    try:
        return db.execute(text(sql), params).scalar()
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def _prepare_and_cleanup() -> Iterator[None]:
    db = SessionLocal()
    try:
        add_second_receiver(db)
        db.commit()
    finally:
        db.close()
    get_erp_gateway().configure_failures("NONE", 0)
    get_tms_gateway().configure_failures("NONE", 0)
    yield
    db = SessionLocal()
    try:
        if _created_docs:
            db.execute(
                text("DELETE FROM integration_sync_logs WHERE doc_id = ANY(:ids)"),
                {"ids": _created_docs},
            )
            # Dòng cấp phát (đã xuất xong, còn 0) giữ khóa ngoại tới inventory_balances; test khác
            # dọn tồn theo vị trí sẽ vướng nếu vị trí cất hàng của kịch bản trùng vị trí của chúng.
            alloc_scope = (
                "SELECT ia.allocation_id FROM inventory_allocations ia "
                "JOIN outbound_order_lines ol ON ol.order_line_id = ia.order_line_id "
                "WHERE ol.order_id = ANY(:ids)"
            )
            db.execute(
                text(
                    f"UPDATE pick_lines SET allocation_id = NULL "
                    f"WHERE allocation_id IN ({alloc_scope})"
                ),
                {"ids": _created_docs},
            )
            db.execute(
                text(f"DELETE FROM inventory_allocations WHERE allocation_id IN ({alloc_scope})"),
                {"ids": _created_docs},
            )
            db.commit()
    finally:
        db.close()


def _headers(username: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200, (username, resp.text)
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


def _ok(resp: Any, status: int = 200) -> Any:
    assert resp.status_code == status, resp.text
    return resp.json()["data"]


def _grn(gid: str, who: dict[str, str]) -> Any:
    return _ok(client.get(f"/api/v1/grns/{gid}", headers=who))


def _approve(aid: str, who: dict[str, str]) -> None:
    version = _ok(client.get(f"/api/v1/approvals/{aid}", headers=who))["version_no"]
    _ok(
        client.post(
            f"/api/v1/approvals/{aid}/approve",
            headers=who,
            json={"version_no": version, "reauth_method": "PASSWORD", "reauth_password": PASSWORD},
        )
    )


def test_demo_flow_erp_inbound_approval_putaway_outbound_erp() -> None:
    admin, nhan, nhan2 = _headers("admin"), _headers("nv_nhan"), _headers("nv_nhan2")
    thukho, quanly, cat = _headers("thukho"), _headers("quanly"), _headers("nv_cat")
    soan, dongoi, bgd = _headers("nv_soan"), _headers("nv_dongoi"), _headers("bgd")
    sku_id = _sql("SELECT sku_id FROM skus WHERE sku_code = :c", c=SKU_CODE)
    supplier = _sql("SELECT erp_supplier_code FROM suppliers ORDER BY 1 LIMIT 1")
    customer = _sql("SELECT erp_customer_code FROM customers ORDER BY 1 LIMIT 1")
    reason = _sql("SELECT reason_code FROM reason_codes WHERE is_active ORDER BY 1 LIMIT 1")
    tasks_before = _ok(client.get("/api/v1/dashboard/tasks", headers=bgd))["completed_today"]

    # 1. ERP đẩy PO
    po = _ok(
        client.post(
            "/api/v1/integrations/erp/purchase-orders",
            headers=admin,
            json={
                "erp_po_number": f"E2E-PO-{_marker}",
                "warehouse_code": "WH01",
                "supplier_code": supplier,
                "lines": [
                    {"line_number": 1, "sku_code": SKU_CODE, "uom_code": "SET", "qty_ordered": QTY}
                ],
            },
        ),
        201,
    )
    po_id = po["doc_id"]
    _created_docs.append(uuid.UUID(po_id))

    # 2. nv_nhan mở GRN, đếm mù có lệch: 8 đếm được, 1 hư
    grn = _ok(client.post("/api/v1/grns", headers=nhan, json={"po_id": po_id}), 201)
    gid = grn["grn_id"]
    _created_docs.append(uuid.UUID(gid))
    _ok(
        client.post(
            f"/api/v1/grns/{gid}/lines",
            headers=nhan,
            json={
                "sku_id": str(sku_id),
                "uom_code": "SET",
                "qty_actual": "8",
                "qty_damaged": "1",
                "reason_code": reason,
                "version_no": grn["version_no"],
            },
        ),
        201,
    )
    blind = _grn(gid, nhan)
    assert all(line.get("qty_expected") is None for line in blind["lines"]), "đếm mù"

    submitted = _ok(
        client.post(
            f"/api/v1/grns/{gid}/submit",
            headers=nhan,
            json={"version_no": _grn(gid, nhan)["version_no"]},
        )
    )
    assert submitted["outcome"] == "PENDING_APPROVAL" and submitted["status"] == "PENDING_D1"
    first_approval = submitted["approval_id"]
    assert (
        client.post(
            f"/api/v1/grns/{gid}/complete",
            headers=nhan,
            json={"version_no": _grn(gid, nhan)["version_no"]},
        ).status_code
        == 409
    ), "chưa duyệt thì chưa nhập tồn"

    # 3. thukho yêu cầu đếm lại → nv_nhan2 đếm lại đủ 10
    version = _ok(client.get(f"/api/v1/approvals/{first_approval}", headers=thukho))["version_no"]
    _ok(
        client.post(
            f"/api/v1/approvals/{first_approval}/request-info",
            headers=thukho,
            json={
                "info_required_note": "Đếm lại cả pallet",
                "request_recount": True,
                "version_no": version,
            },
        )
    )
    line_id = _grn(gid, thukho)["lines"][0]["grn_line_id"]
    same = client.post(
        f"/api/v1/grns/{gid}/recount",
        headers=nhan,
        json={
            "version_no": _grn(gid, thukho)["version_no"],
            "lines": [{"grn_line_id": line_id, "qty_actual": str(QTY), "qty_damaged": "0"}],
        },
    )
    assert same.status_code == 409, "đếm lại phải là người khác"
    recount = _ok(
        client.post(
            f"/api/v1/grns/{gid}/recount",
            headers=nhan2,
            json={
                "version_no": _grn(gid, thukho)["version_no"],
                "lines": [{"grn_line_id": line_id, "qty_actual": str(QTY), "qty_damaged": "0"}],
            },
        )
    )
    if recount.get("outcome") == "PENDING_APPROVAL":
        _approve(recount["approval_id"], thukho)
    assert _grn(gid, thukho)["status"] == "APPROVED"

    # 4. Hoàn tất GRN
    done = _ok(
        client.post(
            f"/api/v1/grns/{gid}/complete",
            headers=nhan,
            json={"version_no": _grn(gid, nhan)["version_no"]},
        )
    )
    assert done["status"] == "CLOSED"
    pallet = done["pallets"][0]
    assert pallet["status"] == "STAGED"
    assert (
        _sql("SELECT status::text FROM purchase_orders WHERE po_id = :p", p=uuid.UUID(po_id))
        == "FULLY_RECEIVED"
    )

    # 5. nv_cat cất pallet
    suggestion = _ok(
        client.post("/api/v1/putaway/suggest", headers=cat, json={"pallet_id": pallet["pallet_id"]})
    )["suggestions"][0]
    _ok(
        client.post(
            f"/api/v1/pallets/{pallet['pallet_id']}/putaway",
            headers=cat,
            json={
                "location_id": suggestion["location_id"],
                "scanned_location_barcode": suggestion["barcode"],
                "version_no": pallet["version_no"],
            },
        )
    )
    assert (
        _sql(
            "SELECT status::text FROM pallets WHERE pallet_id = :p",
            p=uuid.UUID(pallet["pallet_id"]),
        )
        == "STORED"
    )
    assert (
        _sql(
            "SELECT status::text FROM tasks WHERE task_type = 'PUTAWAY' AND ref_doc_id = :p",
            p=uuid.UUID(pallet["pallet_id"]),
        )
        == "COMPLETED"
    )

    # 6. ERP đẩy SO
    so = _ok(
        client.post(
            "/api/v1/integrations/erp/outbound-orders",
            headers=admin,
            json={
                "erp_order_number": f"E2E-SO-{_marker}",
                "order_type": "SO",
                "warehouse_code": "WH01",
                "customer_code": customer,
                "cutoff_time": "2099-12-31T17:00:00+07:00",
                "lines": [{"line_number": 1, "sku_code": SKU_CODE, "qty_ordered": QTY}],
            },
        ),
        201,
    )
    order_id = so["doc_id"]
    _created_docs.append(uuid.UUID(order_id))

    # 7. thukho cấp phát, tạo phiên soạn giao nv_soan
    order = _ok(client.get(f"/api/v1/outbound-orders/{order_id}", headers=thukho))
    allocated = _ok(
        client.post(
            f"/api/v1/outbound-orders/{order_id}/allocate",
            headers=thukho,
            json={"version_no": order["version_no"]},
        )
    )
    assert allocated["has_shortage"] is False
    soan_id = _sql("SELECT user_id FROM users WHERE username = 'nv_soan'")
    session = _ok(
        client.post(
            "/api/v1/pick-sessions",
            headers=thukho,
            json={"order_ids": [order_id], "picker_user_id": str(soan_id)},
        ),
        201,
    )

    # 8. nv_soan soạn đủ từng dòng
    for line in session["lines"]:
        _ok(
            client.post(
                f"/api/v1/pick-sessions/{session['pick_session_id']}/lines/{line['pick_line_id']}/confirm",
                headers=soan,
                json={"qty_picked": line["qty_to_pick"]},
            )
        )
    assert (
        _ok(client.get(f"/api/v1/outbound-orders/{order_id}", headers=thukho))["status"] == "PICKED"
    )

    # 9. nv_dongoi đóng gói, lập GI (TMS cấp vận đơn), xác nhận có chữ ký tài xế
    _ok(client.post(f"/api/v1/outbound-orders/{order_id}/packages", headers=dongoi, json={}), 201)
    gi = _ok(client.post("/api/v1/goods-issues", headers=dongoi, json={"order_id": order_id}), 201)
    _created_docs.append(uuid.UUID(gi["gi_id"]))
    assert gi["tms_waybill_code"]
    shipped = _ok(
        client.post(
            f"/api/v1/goods-issues/{gi['gi_id']}/confirm",
            headers=dongoi,
            json={"driver_signature_data": "chu-ky-tai-xe-demo"},
        )
    )
    assert shipped["order_status"] == "SHIPPED"
    on_hand = _sql(
        "SELECT COALESCE(SUM(qty_available + qty_allocated), 0) FROM inventory_balances "
        "WHERE sku_id = :s",
        s=sku_id,
    )
    assert on_hand == 0, "nhập 10, xuất 10"

    # 10. quanly đẩy GRN, GI sang ERP (thử lại đúng dòng của kịch bản)
    for doc_type, doc_id in (("GRN", gid), ("GI", gi["gi_id"])):
        sync_id = _sql(
            "SELECT sync_id FROM integration_sync_logs WHERE doc_type = :t AND doc_id = :d "
            "AND direction = 'OUTBOUND'",
            t=doc_type,
            d=uuid.UUID(doc_id),
        )
        assert sync_id, f"{doc_type} phải vào hàng đợi gửi ERP"
        log = _ok(client.post(f"/api/v1/integrations/sync-logs/{sync_id}/retry", headers=quanly))
        assert log["status"] == "SUCCESS", doc_type

    # 11. bgd xem dashboard
    tasks = _ok(client.get("/api/v1/dashboard/tasks", headers=bgd))
    assert tasks["completed_today"] >= tasks_before + 2, "PUTAWAY và PICKING đã xong"
    orders = _ok(client.get("/api/v1/dashboard/orders", headers=bgd))
    assert orders["outbound"]["gi_confirmed_today"] >= 1
    assert orders["inbound"]["grns_closed_today"] >= 1
