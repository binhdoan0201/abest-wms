"""Integration tests luồng Kiểm kê B-09 (tự dọn dữ liệu)."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text

from server.app.core.database import SessionLocal
from server.app.main import app

client = TestClient(app)
WAREHOUSE_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")


def _login(username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo@123456"},
    )
    assert resp.status_code == 200
    return str(resp.json()["data"]["access_token"])


def test_cycle_count_blind_count_and_close() -> None:
    """Tạo phiếu kiểm kê -> khóa vị trí -> nv_kiemke đếm mù -> đóng phiếu mở khóa vị trí."""
    thukho_token = _login("thukho")
    kiemke_token = _login("nv_kiemke")

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
        # 1. Thủ kho tạo phiếu kiểm kê
        r_create = client.post(
            "/api/v1/cycle-counts",
            headers={"Authorization": f"Bearer {thukho_token}"},
            json={
                "count_type": "PERIODIC",
                "due_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                "location_ids": [str(loc_id)],
            },
        )
        assert r_create.status_code == 201
        sheet = r_create.json()["data"]
        sheet_id = sheet["count_sheet_id"]
        line_id = sheet["lines"][0]["count_line_id"]

        # 2. nv_kiemke xem chi tiết -> phải ẩn tồn sổ sách
        r_get = client.get(
            f"/api/v1/cycle-counts/{sheet_id}",
            headers={"Authorization": f"Bearer {kiemke_token}"},
        )
        assert r_get.status_code == 200
        assert r_get.json()["data"]["lines"][0]["system_qty_snapshot"] is None

        # 3. nv_kiemke ghi kết quả đếm mù = 0 -> khớp tồn -> AUTO_APPROVED_Z
        r_cnt = client.post(
            f"/api/v1/cycle-counts/{sheet_id}/lines/{line_id}/count",
            headers={"Authorization": f"Bearer {kiemke_token}"},
            json={"blind_counted_qty": "0"},
        )
        assert r_cnt.status_code == 200
        assert r_cnt.json()["data"]["status"] == "AUTO_APPROVED_Z"

        # 4. Đóng phiếu kiểm kê -> mở khóa vị trí
        r_close = client.post(
            f"/api/v1/cycle-counts/{sheet_id}/close",
            headers={"Authorization": f"Bearer {thukho_token}"},
        )
        assert r_close.status_code == 200
        assert r_close.json()["data"]["status"] == "CLOSED"
    finally:
        db = SessionLocal()
        try:
            db.execute(
                text(
                    "UPDATE locations SET status = 'EMPTY', lock_reason = NULL, locked_by = NULL, locked_at = NULL WHERE location_id = :loc;"  # noqa: E501
                ),
                {"loc": loc_id},
            )
            if sheet_id:
                db.execute(
                    text(
                        "DELETE FROM tasks WHERE ref_doc_type = 'CYCLE_COUNT' AND ref_doc_id = :sid;"  # noqa: E501
                    ),
                    {"sid": uuid.UUID(sheet_id)},
                )
                db.execute(
                    text("DELETE FROM cycle_count_sheets WHERE count_sheet_id = :sid;"),
                    {"sid": uuid.UUID(sheet_id)},
                )
            db.commit()
        finally:
            db.close()


def test_cycle_count_diff_approval_marks_executed_on_close() -> None:
    """Tạo phiếu -> đếm lệch (10 -> 7) -> duyệt -> đóng -> EXECUTED_INVENTORY."""
    from decimal import Decimal

    from server.app.modules.inventory.services import apply_movement

    thukho_token = _login("thukho")
    kiemke_token = _login("nv_kiemke")

    db = SessionLocal()
    loc_id = None
    sku_id = None
    sheet_id = None
    approval_id = None
    seed_ref_id = uuid.uuid4()
    try:
        loc_id = db.execute(
            text(
                "SELECT location_id FROM locations "
                "WHERE warehouse_id = :wh AND status = 'EMPTY' "
                "AND lock_reason IS NULL AND is_active = TRUE LIMIT 1;"
            ),
            {"wh": WAREHOUSE_ID},
        ).scalar_one()
        sku_id = db.execute(
            text("SELECT sku_id FROM skus WHERE is_active = TRUE LIMIT 1;")
        ).scalar_one()
        actor_id = db.execute(
            text("SELECT user_id FROM users WHERE username = 'thukho' LIMIT 1;")
        ).scalar_one()

        # Nạp sẵn tồn = 10 tại vị trí kiểm kê
        apply_movement(
            db=db,
            warehouse_id=WAREHOUSE_ID,
            location_id=loc_id,
            sku_id=sku_id,
            lot_id=None,
            pallet_id=None,
            serial_number=None,
            tx_type="CYCLE_COUNT",
            delta_available=Decimal("10"),
            ref_doc_type="CYCLE_COUNT",
            ref_doc_id=seed_ref_id,
            performed_by=actor_id,
        )
        db.commit()

        # 1. Tạo phiếu kiểm kê
        r_create = client.post(
            "/api/v1/cycle-counts",
            headers={"Authorization": f"Bearer {thukho_token}"},
            json={
                "count_type": "PERIODIC",
                "due_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
                "location_ids": [str(loc_id)],
            },
        )
        assert r_create.status_code == 201
        sheet = r_create.json()["data"]
        sheet_id = sheet["count_sheet_id"]
        line_id = sheet["lines"][0]["count_line_id"]

        # 2. Đếm mù = 7 (chênh lệch -3) -> phát sinh approval_requests (CYCLE_COUNT_DIFF)
        r_cnt = client.post(
            f"/api/v1/cycle-counts/{sheet_id}/lines/{line_id}/count",
            headers={"Authorization": f"Bearer {kiemke_token}"},
            json={"blind_counted_qty": "7"},
        )
        assert r_cnt.status_code == 200
        assert r_cnt.json()["data"]["status"].startswith("PENDING")

        approval_id = db.execute(
            text(
                "SELECT approval_id::text FROM approval_requests "
                "WHERE warehouse_id = :wh AND object_type = 'CYCLE_COUNT_DIFF' "
                "AND object_id = :oid;"
            ),
            {"wh": WAREHOUSE_ID, "oid": uuid.UUID(line_id)},
        ).scalar_one()

        # 3. Thủ kho (D1) duyệt hồ sơ sai lệch kiểm kê
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
                "recommendation_or_reason": "Xác nhận chênh lệch kiểm kê 10 -> 7",
                "version_no": app_ver,
            },
        )
        assert r_approve.status_code == 200
        assert r_approve.json()["data"]["execution_status"] == "WAITING_EXECUTION"

        # 4. Đóng phiếu kiểm kê -> ghi tồn & cập nhật execution_status = EXECUTED_INVENTORY
        r_close = client.post(
            f"/api/v1/cycle-counts/{sheet_id}/close",
            headers={"Authorization": f"Bearer {thukho_token}"},
        )
        assert r_close.status_code == 200
        assert r_close.json()["data"]["status"] == "CLOSED"

        exec_status = db.execute(
            text("SELECT execution_status::text FROM approval_requests WHERE approval_id = :aid;"),
            {"aid": uuid.UUID(approval_id)},
        ).scalar_one()
        assert exec_status == "EXECUTED_INVENTORY"
    finally:
        db.rollback()
        if sheet_id:
            db.execute(
                text(
                    "DELETE FROM tasks " "WHERE ref_doc_type = 'CYCLE_COUNT' AND ref_doc_id = :sid;"
                ),
                {"sid": uuid.UUID(sheet_id)},
            )
            db.execute(
                text("DELETE FROM cycle_count_sheets WHERE count_sheet_id = :sid;"),
                {"sid": uuid.UUID(sheet_id)},
            )
        if approval_id:
            db.execute(
                text("DELETE FROM approval_requests WHERE approval_id = :aid;"),
                {"aid": uuid.UUID(approval_id)},
            )
        if loc_id is not None:
            db.execute(
                text("DELETE FROM inventory_balances WHERE location_id = :loc;"),
                {"loc": loc_id},
            )
            db.execute(
                text(
                    "UPDATE locations SET status = 'EMPTY', lock_reason = NULL, "
                    "locked_by = NULL, locked_at = NULL WHERE location_id = :loc;"
                ),
                {"loc": loc_id},
            )
        db.commit()
        db.close()
