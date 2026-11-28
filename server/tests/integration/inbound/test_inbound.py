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
        r_grn_after = client.get(
            f"/api/v1/grns/{grn_id}",
            headers={"Authorization": f"Bearer {nhan_token}"},
        )
        assert r_grn_after.status_code == 200
        latest_ver = r_grn_after.json()["data"]["version_no"]

        r_comp = client.post(
            f"/api/v1/grns/{grn_id}/complete",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={"version_no": latest_ver},
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

        r_grn_after = client.get(
            f"/api/v1/grns/{grn_id}", headers={"Authorization": f"Bearer {nhan_token}"}
        )
        assert r_grn_after.status_code == 200
        latest_ver = r_grn_after.json()["data"]["version_no"]
        r_comp = client.post(
            f"/api/v1/grns/{grn_id}/complete",
            headers={"Authorization": f"Bearer {nhan_token}"},
            json={"version_no": latest_ver},
        )
        assert r_comp.status_code == 200

        exec_status = db.execute(
            text("SELECT execution_status::text FROM approval_requests WHERE approval_id = :aid;"),
            {"aid": uuid.UUID(approval_id)},
        ).scalar()
        assert exec_status == "EXECUTED_INVENTORY"
    finally:
        db.close()


def test_suggest_locations_priority_same_sku_then_empty_then_other_sku() -> None:
    """Thứ tự gợi ý vị trí cất hàng: ô cùng SKU -> ô trống -> ô có SKU khác."""
    from server.app.modules.inbound.repositories import InboundRepository

    db = SessionLocal()
    zone_id = uuid.uuid4()
    loc_same_id = uuid.uuid4()
    loc_empty_id = uuid.uuid4()
    loc_other_id = uuid.uuid4()
    other_sku_id = uuid.uuid4()
    tag = uuid.uuid4().hex[:6].upper()

    try:
        zone_code = f"Z-TST-{tag}"
        code_same = f"A-{tag}-01-SAME"
        code_empty = f"A-{tag}-02-EMPTY"
        code_other = f"A-{tag}-03-OTHER"

        db.execute(
            text(
                """
                INSERT INTO zones (
                    zone_id, warehouse_id, zone_code, zone_name, zone_type, is_active
                )
                VALUES (:zid, :wh, :zcode, :zname, 'STORAGE', TRUE);
                """
            ),
            {
                "zid": zone_id,
                "wh": WAREHOUSE_ID,
                "zcode": zone_code,
                "zname": f"Zone Test {tag}",
            },
        )
        for lid, lcode, lstatus in [
            (loc_same_id, code_same, "PARTIAL"),
            (loc_empty_id, code_empty, "EMPTY"),
            (loc_other_id, code_other, "PARTIAL"),
        ]:
            db.execute(
                text(
                    """
                    INSERT INTO locations (
                        location_id, warehouse_id, zone_id, location_code,
                        barcode, status, is_active
                    )
                    VALUES (
                        :lid, :wh, :zid, :lcode, :bcode,
                        CAST(:st AS location_status_type), TRUE
                    );
                    """
                ),
                {
                    "lid": lid,
                    "wh": WAREHOUSE_ID,
                    "zid": zone_id,
                    "lcode": lcode,
                    "bcode": f"BC-{lcode}",
                    "st": lstatus,
                },
            )
        db.execute(
            text(
                """
                INSERT INTO skus (sku_id, sku_code, sku_name, base_uom, is_active)
                VALUES (:sid, :scode, :sname, 'PCS', TRUE);
                """
            ),
            {
                "sid": other_sku_id,
                "scode": f"SKU-OTHER-{tag}",
                "sname": f"Other SKU {tag}",
            },
        )
        for bal_id, loc_id, sid in [
            (uuid.uuid4(), loc_same_id, SKU_ID),
            (uuid.uuid4(), loc_other_id, other_sku_id),
        ]:
            db.execute(
                text(
                    """
                    INSERT INTO inventory_balances (
                        balance_id, warehouse_id, location_id, sku_id, qty_available
                    )
                    VALUES (:bid, :wh, :lid, :sid, 5);
                    """
                ),
                {"bid": bal_id, "wh": WAREHOUSE_ID, "lid": loc_id, "sid": sid},
            )
        db.commit()

        suggestions = InboundRepository.suggest_locations_for_pallet(
            db=db,
            warehouse_id=WAREHOUSE_ID,
            exclude_location_id=None,
            zone_type="STORAGE",
            sku_ids=[SKU_ID],
        )
        by_id = {uuid.UUID(s["location_id"]): s for s in suggestions}
        assert loc_same_id in by_id
        assert by_id[loc_same_id]["same_sku_consolidation"] is True

        order = [uuid.UUID(s["location_id"]) for s in suggestions]
        if loc_empty_id in by_id:
            assert by_id[loc_empty_id]["same_sku_consolidation"] is False
            assert by_id[loc_empty_id]["status"] == "EMPTY"
            assert order.index(loc_same_id) < order.index(loc_empty_id)
        if loc_other_id in by_id:
            assert by_id[loc_other_id]["same_sku_consolidation"] is False
            assert order.index(loc_same_id) < order.index(loc_other_id)
            if loc_empty_id in by_id:
                assert order.index(loc_empty_id) < order.index(loc_other_id)
    finally:
        db.rollback()
        db.execute(
            text("DELETE FROM inventory_balances WHERE location_id IN (:a, :b, :c);"),
            {"a": loc_same_id, "b": loc_empty_id, "c": loc_other_id},
        )
        db.execute(
            text("DELETE FROM locations WHERE location_id IN (:a, :b, :c);"),
            {"a": loc_same_id, "b": loc_empty_id, "c": loc_other_id},
        )
        db.execute(text("DELETE FROM zones WHERE zone_id = :zid;"), {"zid": zone_id})
        db.execute(text("DELETE FROM skus WHERE sku_id = :sid;"), {"sid": other_sku_id})
        db.commit()
        db.close()


def test_damaged_pallet_cleanup_and_reuse_across_recounts() -> None:
    """Pallet DMG bị dọn sang EMPTY khi hết hư vẫn tái sử dụng được khi đếm lại lần 2 có hàng hư."""
    from server.app.modules.inbound.repositories import InboundRepository

    db = SessionLocal()
    grn_id = uuid.uuid4()
    line_id = uuid.uuid4()
    pallet_id = uuid.uuid4()
    tag = uuid.uuid4().hex[:6].upper()
    grn_number = f"GRN-DMG-{tag}"
    dmg_code = f"{grn_number}-DMG"

    try:
        wh_id = db.execute(
            text("SELECT warehouse_id FROM locations WHERE warehouse_id = :wh LIMIT 1;"),
            {"wh": WAREHOUSE_ID},
        ).scalar_one()
        user_id = db.execute(
            text("SELECT user_id FROM users WHERE username = 'nv_nhan' LIMIT 1;")
        ).scalar_one()

        db.execute(
            text(
                """
                INSERT INTO grns (grn_id, grn_number, warehouse_id, received_by, status, version_no)
                VALUES (:gid, :gnum, :wh, :uid, 'PENDING_D1', 1);
                """
            ),
            {"gid": grn_id, "gnum": grn_number, "wh": wh_id, "uid": user_id},
        )
        pallet_id = InboundRepository.create_pallet(
            db=db,
            pallet_code=dmg_code,
            warehouse_id=wh_id,
            location_id=None,
            source_grn_id=grn_id,
            status="DAMAGED_HOLD",
            created_by=user_id,
        )
        db.execute(
            text(
                """
                INSERT INTO grn_lines (
                    grn_line_id, grn_id, sku_id, damaged_pallet_id, uom_code,
                    qty_expected, qty_actual, qty_damaged
                )
                VALUES (:lid, :gid, :sku, :pid, 'PCS', 10, 8, 0);
                """
            ),
            {"lid": line_id, "gid": grn_id, "sku": SKU_ID, "pid": pallet_id},
        )
        db.commit()

        # Lần 1: không còn hàng hư -> dọn pallet DMG sang EMPTY
        InboundRepository.cleanup_empty_damaged_pallets(db, grn_id)
        db.commit()
        status_after_cleanup = db.execute(
            text("SELECT status::text FROM pallets WHERE pallet_id = :pid;"),
            {"pid": pallet_id},
        ).scalar_one()
        assert status_after_cleanup == "EMPTY"

        # Lần 2: lại có hàng hư -> tìm thấy pallet cũ và tái sử dụng thành công
        found_id = InboundRepository.get_pallet_by_code(db, dmg_code)
        assert found_id == pallet_id
        reused_id = InboundRepository.reactivate_pallet_for_grn(
            db=db,
            pallet_id=found_id,
            location_id=None,
            source_grn_id=grn_id,
            status="DAMAGED_HOLD",
        )
        db.commit()
        assert reused_id == pallet_id
        row = db.execute(
            text("SELECT status::text, source_grn_id FROM pallets WHERE pallet_id = :pid;"),
            {"pid": pallet_id},
        ).one()
        assert row[0] == "DAMAGED_HOLD"
        assert row[1] == grn_id
    finally:
        db.rollback()
        db.execute(text("DELETE FROM grn_lines WHERE grn_line_id = :lid;"), {"lid": line_id})
        db.execute(text("DELETE FROM pallets WHERE pallet_id = :pid;"), {"pid": pallet_id})
        db.execute(text("DELETE FROM grns WHERE grn_id = :gid;"), {"gid": grn_id})
        db.commit()
        db.close()


def test_list_grns_can_recount_false_then_true_after_request_recount() -> None:
    """GET /api/v1/grns trả can_recount=False ban đầu và True sau khi yêu cầu đếm lại."""
    nhan_token = _login("nv_nhan")
    thukho_token = _login("thukho")
    nhan_hdr = {"Authorization": f"Bearer {nhan_token}"}
    thukho_hdr = {"Authorization": f"Bearer {thukho_token}"}

    db = SessionLocal()
    try:
        supplier_id = db.execute(text("SELECT supplier_id FROM suppliers LIMIT 1;")).scalar_one()
        sku_id = SKU_ID
        reason_code = db.execute(
            text("SELECT reason_code FROM reason_codes WHERE is_active = TRUE LIMIT 1;")
        ).scalar_one()
    finally:
        db.close()

    po_id = uuid.uuid4()
    po_line_id = uuid.uuid4()
    erp_po = f"PO-RCNT-{uuid.uuid4().hex[:8].upper()}"
    grn_id: uuid.UUID | None = None
    approval_id: uuid.UUID | None = None

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
            {"pid": po_id, "erp": erp_po, "wh": WAREHOUSE_ID, "sup": supplier_id},
        )
        db.execute(
            text(
                """
                INSERT INTO po_lines (po_line_id, po_id, line_number, sku_id, uom_code, qty_ordered)
                VALUES (:lid, :pid, 1, :sku, 'PCS', 10.000);
                """
            ),
            {"lid": po_line_id, "pid": po_id, "sku": sku_id},
        )
        db.commit()

        r_create = client.post("/api/v1/grns", headers=nhan_hdr, json={"po_id": str(po_id)})
        assert r_create.status_code == 201, r_create.text
        grn_data = r_create.json()["data"]
        grn_id = uuid.UUID(grn_data["grn_id"])

        r_list_before = client.get(f"/api/v1/grns?po_id={po_id}", headers=nhan_hdr)
        assert r_list_before.status_code == 200, r_list_before.text
        items_before = r_list_before.json()["data"]
        target_before = next(x for x in items_before if x["grn_id"] == str(grn_id))
        assert target_before["can_recount"] is False

        r_line = client.post(
            f"/api/v1/grns/{grn_id}/lines",
            headers=nhan_hdr,
            json={
                "sku_id": str(sku_id),
                "uom_code": "PCS",
                "qty_actual": "7",
                "qty_damaged": "0",
                "reason_code": reason_code,
                "version_no": grn_data["version_no"],
            },
        )
        assert r_line.status_code == 201, r_line.text

        grn_after_line = client.get(f"/api/v1/grns/{grn_id}", headers=nhan_hdr).json()["data"]
        r_submit = client.post(
            f"/api/v1/grns/{grn_id}/submit",
            headers=nhan_hdr,
            json={"version_no": grn_after_line["version_no"]},
        )
        assert r_submit.status_code == 200, r_submit.text
        submit_data = r_submit.json()["data"]
        approval_id = uuid.UUID(submit_data["approval_id"])

        r_app_get = client.get(f"/api/v1/approvals/{approval_id}", headers=thukho_hdr)
        assert r_app_get.status_code == 200, r_app_get.text
        app_ver = int(r_app_get.json()["data"].get("version_no", 1))

        r_recount_req = client.post(
            f"/api/v1/approvals/{approval_id}/request-info",
            headers=thukho_hdr,
            json={
                "info_required_note": "Đếm lại số lượng thực tế",
                "request_recount": True,
                "version_no": app_ver,
            },
        )
        assert r_recount_req.status_code == 200, r_recount_req.text

        r_list_after = client.get(f"/api/v1/grns?po_id={po_id}", headers=nhan_hdr)
        assert r_list_after.status_code == 200, r_list_after.text
        items_after = r_list_after.json()["data"]
        target_after = next(x for x in items_after if x["grn_id"] == str(grn_id))
        assert target_after["can_recount"] is True
    finally:
        db.rollback()
        if approval_id is not None:
            db.execute(
                text("DELETE FROM approval_histories WHERE approval_id = :aid;"),
                {"aid": approval_id},
            )
            db.execute(
                text("DELETE FROM approval_requests WHERE approval_id = :aid;"),
                {"aid": approval_id},
            )
        if grn_id is not None:
            db.execute(
                text(
                    "DELETE FROM grn_count_attempts "
                    "WHERE grn_line_id IN (SELECT grn_line_id FROM grn_lines WHERE grn_id = :gid);"
                ),
                {"gid": grn_id},
            )
            db.execute(text("DELETE FROM grn_lines WHERE grn_id = :gid;"), {"gid": grn_id})
            db.execute(text("DELETE FROM pallets WHERE source_grn_id = :gid;"), {"gid": grn_id})
            db.execute(text("DELETE FROM grns WHERE grn_id = :gid;"), {"gid": grn_id})
        db.execute(text("DELETE FROM po_lines WHERE po_line_id = :lid;"), {"lid": po_line_id})
        db.execute(text("DELETE FROM purchase_orders WHERE po_id = :pid;"), {"pid": po_id})
        db.commit()
        db.close()


def test_list_grns_can_recount_false_when_need_info_without_request_recount() -> None:
    """Hồ sơ NEED_INFO nhưng không có REQUEST_RECOUNT thì can_recount vẫn là False."""
    nhan_token = _login("nv_nhan")
    thukho_token = _login("thukho")
    nhan_hdr = {"Authorization": f"Bearer {nhan_token}"}
    thukho_hdr = {"Authorization": f"Bearer {thukho_token}"}

    db = SessionLocal()
    try:
        supplier_id = db.execute(text("SELECT supplier_id FROM suppliers LIMIT 1;")).scalar_one()
        sku_id = SKU_ID
        reason_code = db.execute(
            text("SELECT reason_code FROM reason_codes WHERE is_active = TRUE LIMIT 1;")
        ).scalar_one()
    finally:
        db.close()

    po_id = uuid.uuid4()
    po_line_id = uuid.uuid4()
    erp_po = f"PO-NI-{uuid.uuid4().hex[:8].upper()}"
    grn_id: uuid.UUID | None = None
    approval_id: uuid.UUID | None = None

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
            {"pid": po_id, "erp": erp_po, "wh": WAREHOUSE_ID, "sup": supplier_id},
        )
        db.execute(
            text(
                """
                INSERT INTO po_lines (po_line_id, po_id, line_number, sku_id, uom_code, qty_ordered)
                VALUES (:lid, :pid, 1, :sku, 'PCS', 10.000);
                """
            ),
            {"lid": po_line_id, "pid": po_id, "sku": sku_id},
        )
        db.commit()

        r_create = client.post("/api/v1/grns", headers=nhan_hdr, json={"po_id": str(po_id)})
        assert r_create.status_code == 201, r_create.text
        grn_data = r_create.json()["data"]
        grn_id = uuid.UUID(grn_data["grn_id"])

        r_line = client.post(
            f"/api/v1/grns/{grn_id}/lines",
            headers=nhan_hdr,
            json={
                "sku_id": str(sku_id),
                "uom_code": "PCS",
                "qty_actual": "7",
                "qty_damaged": "0",
                "reason_code": reason_code,
                "version_no": grn_data["version_no"],
            },
        )
        assert r_line.status_code == 201, r_line.text

        grn_after_line = client.get(f"/api/v1/grns/{grn_id}", headers=nhan_hdr).json()["data"]
        r_submit = client.post(
            f"/api/v1/grns/{grn_id}/submit",
            headers=nhan_hdr,
            json={"version_no": grn_after_line["version_no"]},
        )
        assert r_submit.status_code == 200, r_submit.text
        approval_id = uuid.UUID(r_submit.json()["data"]["approval_id"])

        r_app_get = client.get(f"/api/v1/approvals/{approval_id}", headers=thukho_hdr)
        assert r_app_get.status_code == 200, r_app_get.text
        app_ver = int(r_app_get.json()["data"].get("version_no", 1))

        r_info = client.post(
            f"/api/v1/approvals/{approval_id}/request-info",
            headers=thukho_hdr,
            json={
                "info_required_note": "Bổ sung biên bản giao nhận",
                "request_recount": False,
                "version_no": app_ver,
            },
        )
        assert r_info.status_code == 200, r_info.text

        r_list = client.get(f"/api/v1/grns?po_id={po_id}", headers=nhan_hdr)
        assert r_list.status_code == 200, r_list.text
        items = r_list.json()["data"]
        target = next(x for x in items if x["grn_id"] == str(grn_id))
        assert target["can_recount"] is False
    finally:
        db.rollback()
        if approval_id is not None:
            db.execute(
                text("DELETE FROM approval_histories WHERE approval_id = :aid;"),
                {"aid": approval_id},
            )
            db.execute(
                text("DELETE FROM approval_requests WHERE approval_id = :aid;"),
                {"aid": approval_id},
            )
        if grn_id is not None:
            db.execute(
                text(
                    "DELETE FROM grn_count_attempts "
                    "WHERE grn_line_id IN (SELECT grn_line_id FROM grn_lines WHERE grn_id = :gid);"
                ),
                {"gid": grn_id},
            )
            db.execute(text("DELETE FROM grn_lines WHERE grn_id = :gid;"), {"gid": grn_id})
            db.execute(text("DELETE FROM pallets WHERE source_grn_id = :gid;"), {"gid": grn_id})
            db.execute(text("DELETE FROM grns WHERE grn_id = :gid;"), {"gid": grn_id})
        db.execute(text("DELETE FROM po_lines WHERE po_line_id = :lid;"), {"lid": po_line_id})
        db.execute(text("DELETE FROM purchase_orders WHERE po_id = :pid;"), {"pid": po_id})
        db.commit()
        db.close()
