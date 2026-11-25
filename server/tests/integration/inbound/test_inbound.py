"""Integration tests luồng Inbound từ B-04 đến B-07 (tự dọn dữ liệu)."""

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

from server.app.core.database import SessionLocal
from server.app.main import app

client = TestClient(app)

WAREHOUSE_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
SUPPLIER_ID = uuid.UUID("a2000000-0000-0000-0000-000000000001")
SKU_ID = uuid.UUID("a3000000-0000-0000-0000-000000000003")


def _login(username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo@123456"},
    )
    assert resp.status_code == 200
    return str(resp.json()["data"]["access_token"])


def test_inbound_full_flow_receive_submit_complete_putaway() -> None:
    """Kiểm thử toàn trình: PO -> mở GRN -> đếm mù -> submit auto-approve -> complete -> putaway."""
    global SUPPLIER_ID
    _s = SessionLocal()
    try:
        SUPPLIER_ID = _s.execute(text("SELECT supplier_id FROM suppliers LIMIT 1;")).scalar_one()
    finally:
        _s.close()
    nhan_token = _login("nv_nhan")
    cat_token = _login("nv_cat")

    po_id = uuid.uuid4()
    po_line_id = uuid.uuid4()
    erp_po = f"PO-TEST-{uuid.uuid4().hex[:8].upper()}"
    lot_num = f"LOT-INB-{uuid.uuid4().hex[:6].upper()}"

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO purchase_orders (
                    po_id, erp_po_number, warehouse_id, supplier_id, status, expected_date
                )
                VALUES (:pid, :erp, :wh, :sup, 'PENDING', CURRENT_DATE);
                """
            ),
            {"pid": po_id, "erp": erp_po, "wh": WAREHOUSE_ID, "sup": SUPPLIER_ID},
        )
        db.execute(
            text(
                """
                INSERT INTO po_lines (po_line_id, po_id, line_number, sku_id, uom_code, qty_ordered)
                VALUES (:lid, :pid, 1, :sku, 'PCS', 10.000);
                """
            ),
            {"lid": po_line_id, "pid": po_id, "sku": SKU_ID},
        )
        db.commit()
    finally:
        db.close()

    grn_id = None
    try:
        # 1. Mở GRN (B-04)
        r_grn = client.post(
            "/api/v1/grns",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={"po_id": str(po_id)},
        )
        assert r_grn.status_code == 201
        grn_data = r_grn.json()["data"]
        grn_id = grn_data["grn_id"]
        assert grn_data["status"] == "COUNTING"

        # 2. Ghi dòng đếm khớp 100% số lượng PO (B-04)
        r_line = client.post(
            f"/api/v1/grns/{grn_id}/lines",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={
                "sku_id": str(SKU_ID),
                "lot_number": lot_num,
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                "uom_code": "PCS",
                "qty_actual": "10",
                "qty_damaged": "0",
                "version_no": grn_data["version_no"],
            },
        )
        assert r_line.status_code == 201
        # Đếm mù: nv-nhan không thấy qty_expected
        assert r_line.json()["data"]["qty_expected"] is None
        cur_ver = r_line.json()["data"]["grn_version_no"]

        # 3. Nộp phiếu GRN -> lệch = 0 -> tự động duyệt APPROVED (B-05)
        r_sub = client.post(
            f"/api/v1/grns/{grn_id}/submit",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={"version_no": cur_ver},
        )
        assert r_sub.status_code == 200
        assert r_sub.json()["data"]["status"] == "APPROVED"
        assert r_sub.json()["data"]["outcome"] == "AUTO_APPROVED"
        cur_ver = r_sub.json()["data"]["version_no"]

        # 4. Hoàn tất GRN -> nhập tồn dock, pallet STAGED, task PUTAWAY (B-06)
        r_comp = client.post(
            f"/api/v1/grns/{grn_id}/complete",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={"version_no": cur_ver},
        )
        assert r_comp.status_code == 200
        comp_data = r_comp.json()["data"]
        assert comp_data["status"] == "CLOSED"
        assert len(comp_data["pallets"]) == 1
        pallet = comp_data["pallets"][0]
        pallet_id = pallet["pallet_id"]

        # 5. Gợi ý vị trí cất hàng (B-07)
        r_sug = client.post(
            "/api/v1/putaway/suggest",
            headers={"Authorization": f"Bearer {cat_token}"},
            json={"pallet_id": pallet_id},
        )
        assert r_sug.status_code == 200
        suggestions = r_sug.json()["data"]["suggestions"]
        assert len(suggestions) >= 1
        target_loc = suggestions[0]

        # 6. Xác nhận cất pallet lên kệ (B-07)
        r_put = client.post(
            f"/api/v1/pallets/{pallet_id}/putaway",
            headers={"Authorization": f"Bearer {cat_token}"},
            json={
                "location_id": target_loc["location_id"],
                "scanned_pallet_code": pallet["pallet_code"],
                "scanned_location_barcode": target_loc["barcode"],
                "version_no": pallet["version_no"],
            },
        )
        assert r_put.status_code == 200
        assert r_put.json()["data"]["status"] == "STORED"
        db_chk = SessionLocal()
        try:
            task_status = db_chk.execute(
                text(
                    "SELECT status::text FROM tasks "
                    "WHERE ref_doc_type = 'PALLET' AND ref_doc_id = :pid AND task_type = 'PUTAWAY';"
                ),
                {"pid": uuid.UUID(pallet_id)},
            ).scalar()
            assert task_status == "COMPLETED"
        finally:
            db_chk.close()
    finally:
        # Giải phóng vị trí kệ về EMPTY; giữ nguyên dữ liệu lịch sử bất biến
        db = SessionLocal()
        try:
            if grn_id:
                db.execute(
                    text(
                        "UPDATE locations SET status = 'EMPTY' "
                        "WHERE location_id IN ("
                        "SELECT current_location_id FROM pallets WHERE source_grn_id = :gid);"
                    ),
                    {"gid": uuid.UUID(grn_id)},
                )
                db.commit()
        finally:
            db.close()


def test_grn_discrepancy_approval_marks_executed_on_complete() -> None:
    """GRN lệch -> duyệt -> complete GRN chuyển execution_status = EXECUTED_INVENTORY."""
    nhan_token = _login("nv_nhan")
    thukho_token = _login("thukho")

    po_number = f"PO-EXEC-{uuid.uuid4().hex[:8].upper()}"
    db = SessionLocal()
    grn_id = None
    try:
        wh_id = db.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1;")).scalar()
        sup_id = db.execute(text("SELECT supplier_id FROM suppliers LIMIT 1;")).scalar()
        sku_row = db.execute(
            text("SELECT sku_id, base_uom FROM skus WHERE is_active = TRUE LIMIT 1;")
        ).first()
        assert wh_id and sup_id and sku_row
        sku_id, uom_id = sku_row[0], sku_row[1]

        po_id = uuid.uuid4()
        po_line_id = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO purchase_orders "
                "(po_id, erp_po_number, warehouse_id, supplier_id, status) "
                "VALUES (:po_id, :po_no, :wh_id, :sup_id, 'PENDING');"
            ),
            {"po_id": po_id, "po_no": po_number, "wh_id": wh_id, "sup_id": sup_id},
        )
        db.execute(
            text(
                "INSERT INTO po_lines "
                "(po_line_id, po_id, line_number, sku_id, uom_code, qty_ordered) "
                "VALUES (:lid, :po_id, 1, :sku_id, :uom_code, 10.000);"
            ),
            {"lid": po_line_id, "po_id": po_id, "sku_id": sku_id, "uom_code": uom_id},
        )
        db.commit()

        r_grn = client.post(
            "/api/v1/grns",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={"po_id": str(po_id)},
        )
        assert r_grn.status_code == 201
        grn = r_grn.json()["data"]
        grn_id = grn["grn_id"]

        r_line = client.post(
            f"/api/v1/grns/{grn_id}/lines",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={
                "sku_id": str(sku_id),
                "lot_number": f"LOT-EXEC-{uuid.uuid4().hex[:6].upper()}",
                "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                "uom_code": uom_id,
                "qty_actual": "8",
                "qty_damaged": "0",
                "version_no": grn["version_no"],
            },
        )
        assert r_line.status_code == 201
        line_ver = r_line.json()["data"]["grn_version_no"]

        r_sub = client.post(
            f"/api/v1/grns/{grn_id}/submit",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={"version_no": line_ver},
        )
        assert r_sub.status_code == 200
        sub_data = r_sub.json()["data"]
        assert sub_data["status"] == "PENDING_D1"
        approval_id = sub_data["approval_id"]
        cur_ver = sub_data["version_no"]

        r_app_detail = client.get(
            f"/api/v1/approvals/{approval_id}",
            headers={"Authorization": f"Bearer {thukho_token}"},
        )
        assert r_app_detail.status_code == 200
        app_ver = r_app_detail.json()["data"]["version_no"]

        r_approve = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers={"Authorization": f"Bearer {thukho_token}"},
            json={
                "recommendation_or_reason": "Xác nhận thiếu 2 kiện theo biên bản giao nhận",
                "version_no": app_ver,
            },
        )
        assert r_approve.status_code == 200
        assert r_approve.json()["data"]["execution_status"] == "WAITING_EXECUTION"

        r_comp = client.post(
            f"/api/v1/grns/{grn_id}/complete",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={"version_no": cur_ver},
        )
        assert r_comp.status_code == 200

        exec_status = db.execute(
            text("SELECT execution_status::text FROM approval_requests WHERE approval_id = :aid;"),
            {"aid": uuid.UUID(approval_id)},
        ).scalar()
        assert exec_status == "EXECUTED_INVENTORY"
    finally:
        db.close()
