"""Test Web Client cho giao diện Nhập kho (B1, B2) và Kiểm kê (B3)."""

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from client.app.core.api_client import ApiClient
from client.app.main import app as client_app
from scripts.load_demo import DEMO_USERS, _copy_user, add_second_receiver
from server.app.core.database import SessionLocal
from server.app.main import app as backend_app

ORIGIN = {"Origin": "http://localhost:3000"}
WAREHOUSE_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def in_memory_backend() -> Generator[None, None, None]:
    original = ApiClient.backend_app
    ApiClient.backend_app = backend_app
    db = SessionLocal()
    try:
        add_second_receiver(db)
        _copy_user(db, *DEMO_USERS[1])
        db.commit()
    finally:
        db.close()
    yield
    ApiClient.backend_app = original


@pytest.fixture
def web() -> TestClient:
    return TestClient(client_app, base_url="http://localhost:3000")


@pytest.fixture
def api() -> TestClient:
    return TestClient(backend_app)


def _web_login(web: TestClient, username: str) -> str:
    web.cookies.clear()
    resp = web.post(
        "/login",
        data={"username": username, "password": "Demo@123456"},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return resp.cookies.get("abest_session") or ""


def _api_headers(api: TestClient, username: str) -> dict[str, str]:
    resp = api.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo@123456"},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _cleanup_po_grn(po_id: uuid.UUID | None, grn_id: uuid.UUID | None) -> None:
    db = SessionLocal()
    try:
        if grn_id:
            db.execute(
                text(
                    "DELETE FROM tasks WHERE ref_doc_id IN "
                    "(SELECT pallet_id FROM pallets WHERE source_grn_id = :gid)"
                ),
                {"gid": grn_id},
            )
            db.execute(
                text(
                    "DELETE FROM inventory_balances WHERE pallet_id IN "
                    "(SELECT pallet_id FROM pallets WHERE source_grn_id = :gid)"
                ),
                {"gid": grn_id},
            )
            db.execute(text("DELETE FROM grn_lines WHERE grn_id = :gid"), {"gid": grn_id})
            db.execute(
                text(
                    "DELETE FROM pallets WHERE source_grn_id = :gid "
                    "AND pallet_id NOT IN ("
                    "SELECT pallet_id FROM inventory_transactions WHERE pallet_id IS NOT NULL)"
                ),
                {"gid": grn_id},
            )
            db.execute(
                text("DELETE FROM integration_sync_logs WHERE doc_id = :gid"),
                {"gid": grn_id},
            )
            db.execute(
                text("DELETE FROM approval_requests WHERE object_id = :gid"),
                {"gid": grn_id},
            )
            db.execute(
                text("UPDATE pallets SET source_grn_id = NULL WHERE source_grn_id = :gid"),
                {"gid": grn_id},
            )
            db.execute(text("DELETE FROM grns WHERE grn_id = :gid"), {"gid": grn_id})
        if po_id:
            db.execute(
                text("DELETE FROM integration_sync_logs WHERE doc_id = :pid"),
                {"pid": po_id},
            )
            db.execute(text("DELETE FROM po_lines WHERE po_id = :pid"), {"pid": po_id})
            db.execute(text("DELETE FROM purchase_orders WHERE po_id = :pid"), {"pid": po_id})
        db.commit()
    finally:
        db.close()


def test_b1_grn_recount_ui_flow(web: TestClient, api: TestClient) -> None:
    """nv_nhan đếm lệch -> thukho request-info -> nv_nhan2 mở form đếm lại và gửi thành công."""
    admin_h = _api_headers(api, "admin")
    thukho_h = _api_headers(api, "thukho")
    nhan_h = _api_headers(api, "nv_nhan")
    nhan2_cookie = _web_login(web, "nv_nhan2")

    db = SessionLocal()
    try:
        sku_id = db.execute(
            text("SELECT sku_id FROM skus WHERE sku_code = 'SKU-GEN-008' LIMIT 1;")
        ).scalar_one()
        supplier_code = db.execute(
            text("SELECT erp_supplier_code FROM suppliers ORDER BY 1 LIMIT 1;")
        ).scalar_one()
        reason_code = db.execute(
            text("SELECT reason_code FROM reason_codes WHERE is_active ORDER BY 1 LIMIT 1;")
        ).scalar_one()
    finally:
        db.close()

    po_id = None
    grn_id = None
    try:
        r_po = api.post(
            "/api/v1/integrations/erp/purchase-orders",
            headers=admin_h,
            json={
                "erp_po_number": f"PO-UI-{uuid.uuid4().hex[:6].upper()}",
                "warehouse_code": "WH01",
                "supplier_code": supplier_code,
                "lines": [
                    {
                        "line_number": 1,
                        "sku_code": "SKU-GEN-008",
                        "uom_code": "SET",
                        "qty_ordered": 10,
                    }
                ],
            },
        )
        assert r_po.status_code == 201, r_po.text
        po_id = uuid.UUID(r_po.json()["data"]["doc_id"])

        r_grn = api.post("/api/v1/grns", headers=nhan_h, json={"po_id": str(po_id)})
        assert r_grn.status_code == 201, r_grn.text
        grn_data = r_grn.json()["data"]
        grn_id = uuid.UUID(grn_data["grn_id"])

        r_line = api.post(
            f"/api/v1/grns/{grn_id}/lines",
            headers=nhan_h,
            json={
                "sku_id": str(sku_id),
                "uom_code": "SET",
                "qty_actual": "8",
                "qty_damaged": "1",
                "reason_code": reason_code,
                "version_no": grn_data["version_no"],
            },
        )
        assert r_line.status_code == 201, r_line.text
        grn_cur = api.get(f"/api/v1/grns/{grn_id}", headers=nhan_h).json()["data"]
        grn_line_id = grn_cur["lines"][0]["grn_line_id"]
        v_after_line = grn_cur["version_no"]

        r_sub = api.post(
            f"/api/v1/grns/{grn_id}/submit",
            headers=nhan_h,
            json={"version_no": v_after_line},
        )
        assert r_sub.status_code == 200, r_sub.text
        sub_data = r_sub.json()["data"]
        assert sub_data["status"] == "PENDING_D1"
        approval_id = sub_data["approval_id"]

        app_ver = api.get(f"/api/v1/approvals/{approval_id}", headers=thukho_h).json()["data"][
            "version_no"
        ]
        r_req = api.post(
            f"/api/v1/approvals/{approval_id}/request-info",
            headers=thukho_h,
            json={
                "info_required_note": "Đếm lại giúp anh",
                "request_recount": True,
                "version_no": app_ver,
            },
        )
        assert r_req.status_code == 200, r_req.text

        # nv_nhan2 mở giao diện thấy form đếm lại
        page = web.get(
            f"/inbound?grn_id={grn_id}",
            cookies={"abest_session": nhan2_cookie},
        )
        assert page.status_code == 200
        grn_state = api.get(f"/api/v1/grns/{grn_id}", headers=nhan_h).json()["data"]["status"]
        assert "Xác nhận đếm lại" in page.text, f"status={grn_state}"
        assert f"/inbound/grns/{grn_id}/recount" in page.text

        # Gửi form đếm lại qua client
        v_recount = api.get(f"/api/v1/grns/{grn_id}", headers=nhan_h).json()["data"]["version_no"]
        post_recount = web.post(
            f"/inbound/grns/{grn_id}/recount",
            cookies={"abest_session": nhan2_cookie},
            headers=ORIGIN,
            data={
                "version_no": str(v_recount),
                "grn_line_id": [str(grn_line_id)],
                "qty_actual": ["10"],
                "qty_damaged": ["0"],
            },
            follow_redirects=False,
        )
        assert post_recount.status_code == 303

        grn_after = api.get(f"/api/v1/grns/{grn_id}", headers=nhan_h).json()["data"]
        assert grn_after["recount_count"] == 1
    finally:
        _cleanup_po_grn(po_id, grn_id)


def test_b2_putaway_top5_suggestions_ui(web: TestClient, api: TestClient) -> None:
    """nv_cat mở pallet STAGED tại /inbound?pallet_id=... thấy tối đa 5 gợi ý vị trí cất hàng."""
    admin_h = _api_headers(api, "admin")
    nhan_h = _api_headers(api, "nv_nhan")
    cat_cookie = _web_login(web, "nv_cat")

    db = SessionLocal()
    try:
        sku_id = db.execute(
            text("SELECT sku_id FROM skus WHERE sku_code = 'SKU-GEN-008' LIMIT 1;")
        ).scalar_one()
        supplier_code = db.execute(
            text("SELECT erp_supplier_code FROM suppliers ORDER BY 1 LIMIT 1;")
        ).scalar_one()
    finally:
        db.close()

    po_id = None
    grn_id = None
    try:
        r_po = api.post(
            "/api/v1/integrations/erp/purchase-orders",
            headers=admin_h,
            json={
                "erp_po_number": f"PO-PUT-{uuid.uuid4().hex[:6].upper()}",
                "warehouse_code": "WH01",
                "supplier_code": supplier_code,
                "lines": [
                    {
                        "line_number": 1,
                        "sku_code": "SKU-GEN-008",
                        "uom_code": "SET",
                        "qty_ordered": 10,
                    }
                ],
            },
        )
        assert r_po.status_code == 201, r_po.text
        po_id = uuid.UUID(r_po.json()["data"]["doc_id"])

        r_grn = api.post("/api/v1/grns", headers=nhan_h, json={"po_id": str(po_id)})
        assert r_grn.status_code == 201, r_grn.text
        grn_data = r_grn.json()["data"]
        grn_id = uuid.UUID(grn_data["grn_id"])

        r_line = api.post(
            f"/api/v1/grns/{grn_id}/lines",
            headers=nhan_h,
            json={
                "sku_id": str(sku_id),
                "uom_code": "SET",
                "qty_actual": "10",
                "qty_damaged": "0",
                "version_no": grn_data["version_no"],
            },
        )
        assert r_line.status_code == 201, r_line.text

        v_b2 = api.get(f"/api/v1/grns/{grn_id}", headers=nhan_h).json()["data"]["version_no"]
        r_sub = api.post(
            f"/api/v1/grns/{grn_id}/submit",
            headers=nhan_h,
            json={"version_no": v_b2},
        )
        assert r_sub.status_code == 200, r_sub.text

        r_done = api.post(
            f"/api/v1/grns/{grn_id}/complete",
            headers=nhan_h,
            json={"version_no": r_sub.json()["data"]["version_no"]},
        )
        assert r_done.status_code == 200, r_done.text
        pallet_id = r_done.json()["data"]["pallets"][0]["pallet_id"]

        page = web.get(
            f"/inbound?pallet_id={pallet_id}",
            cookies={"abest_session": cat_cookie},
        )
        assert page.status_code == 200
        assert "vị trí gợi ý" in page.text
        assert "Quét & Xác nhận cất" in page.text
    finally:
        _cleanup_po_grn(po_id, grn_id)


def test_b3_cycle_count_recount_ui_flow(web: TestClient, api: TestClient) -> None:
    """nv_kiemke đếm lệch -> nv_kiemke2 mở /cycle-count?sheet_id=... thấy form đếm lại."""
    thukho_h = _api_headers(api, "thukho")
    kk1_h = _api_headers(api, "nv_kiemke")
    kk2_cookie = _web_login(web, "nv_kiemke2")

    db = SessionLocal()
    try:
        loc_id = db.execute(
            text(
                "SELECT location_id FROM locations "
                "WHERE warehouse_id = :wh AND status = 'EMPTY' AND is_active = TRUE LIMIT 1;"
            ),
            {"wh": WAREHOUSE_ID},
        ).scalar_one()
    finally:
        db.close()

    sheet_id = None
    try:
        r_create = api.post(
            "/api/v1/cycle-counts",
            headers=thukho_h,
            json={
                "count_type": "PERIODIC",
                "due_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                "location_ids": [str(loc_id)],
            },
        )
        assert r_create.status_code == 201, r_create.text
        sheet_data = r_create.json()["data"]
        sheet_id = uuid.UUID(sheet_data["count_sheet_id"])
        line_id = sheet_data["lines"][0]["count_line_id"]

        # Đếm lệch (tồn sổ sách = 0, đếm thực tế = 5)
        r_cnt = api.post(
            f"/api/v1/cycle-counts/{sheet_id}/lines/{line_id}/count",
            headers=kk1_h,
            json={"blind_counted_qty": "5"},
        )
        assert r_cnt.status_code == 200, r_cnt.text

        # nv_kiemke2 mở giao diện thấy form đếm lại
        page = web.get(
            f"/cycle-count?sheet_id={sheet_id}",
            cookies={"abest_session": kk2_cookie},
        )
        assert page.status_code == 200
        assert "Ghi nhận đếm lại" in page.text
        assert f"/cycle-count/{sheet_id}/lines/{line_id}/recount" in page.text
    finally:
        db = SessionLocal()
        try:
            if sheet_id:
                db.execute(
                    text("DELETE FROM approval_requests WHERE object_id = :sid"),
                    {"sid": sheet_id},
                )
                db.execute(
                    text("DELETE FROM cycle_count_lines WHERE count_sheet_id = :sid"),
                    {"sid": sheet_id},
                )
                db.execute(
                    text("DELETE FROM cycle_count_sheets WHERE count_sheet_id = :sid"),
                    {"sid": sheet_id},
                )
            db.execute(
                text(
                    "UPDATE locations SET status = 'EMPTY', lock_reason = NULL, "
                    "locked_by = NULL, locked_at = NULL WHERE location_id = :lid"
                ),
                {"lid": loc_id},
            )
            db.commit()
        finally:
            db.close()
