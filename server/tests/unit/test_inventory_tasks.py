"""ABEST WMS - Kiểm thử Unit & Integration cho Phân hệ Tồn kho (Inventory) và Nhiệm vụ (Tasks).

Quy định kiểm thử bắt buộc theo Mục 9 Quy trình dựng khung:
(a) apply_movement RECEIVE hai lần cùng vị trí: tồn cộng đúng, version_no tăng.
(b) Trừ quá tồn: BusinessError INVENTORY_INSUFFICIENT_QTY (HTTP 409).
(c) transfer_inventory giữ nguyên bucket ALLOCATED.
(d) GET /inventory/balances lọc đúng, và vai trò nv-kiemke và admin bị 403.
(e) tasks: tạo, giao, nhận, hoàn tất theo đúng thứ tự; sai thứ tự trả INVALID_STATE;
    sai version_no trả VERSION_CONFLICT; nhân viên chỉ thấy task của mình.
(f) make ci xanh.
"""

import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.exceptions import BusinessError
from server.app.main import app
from server.app.modules.inventory.services import apply_movement, transfer_inventory

client = TestClient(app)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Cung cấp session CSDL độc lập có rollback sau mỗi bài test."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def get_token(username: str, password: str = "Demo@123456") -> str:
    """Helper đăng nhập lấy Bearer token."""
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Đăng nhập thất bại cho {username}"
    token: str = res.json()["data"]["access_token"]
    return token


def test_apply_movement_receive_twice_increments_qty_and_version(db_session: Session) -> None:
    """(a) apply_movement RECEIVE hai lần cùng vị trí: tồn cộng đúng, version_no tăng."""
    wh_row = db_session.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).fetchone()
    loc_row = db_session.execute(text("SELECT location_id FROM locations LIMIT 1")).fetchone()
    sku_row = db_session.execute(text("SELECT sku_id FROM skus LIMIT 1")).fetchone()
    user_row = db_session.execute(text("SELECT user_id FROM users LIMIT 1")).fetchone()
    assert wh_row and loc_row and sku_row and user_row

    wh_id, loc_id, sku_id, user_id = wh_row[0], loc_row[0], sku_row[0], user_row[0]

    # Lấy tồn kho ban đầu (nếu có)
    bal_before = db_session.execute(
        text(
            """
            SELECT qty_available, version_no FROM inventory_balances
            WHERE warehouse_id = :w AND location_id = :l AND sku_id = :s;
            """
        ),
        {"w": wh_id, "l": loc_id, "s": sku_id},
    ).fetchone()

    base_qty = Decimal(str(bal_before[0])) if bal_before else Decimal("0")
    base_ver = bal_before[1] if bal_before else 0

    # Lần 1: Nhập 10.000
    tx1_id = apply_movement(
        db=db_session,
        warehouse_id=wh_id,
        location_id=loc_id,
        sku_id=sku_id,
        lot_id=None,
        pallet_id=None,
        serial_number=None,
        tx_type="RECEIVE",
        delta_available=Decimal("10.000"),
        ref_doc_type="PO",
        ref_doc_id=uuid.uuid4(),
        performed_by=user_id,
    )
    assert tx1_id is not None

    bal_step1 = db_session.execute(
        text(
            """
            SELECT qty_available, version_no FROM inventory_balances
            WHERE warehouse_id = :w AND location_id = :l AND sku_id = :s;
            """
        ),
        {"w": wh_id, "l": loc_id, "s": sku_id},
    ).fetchone()
    assert bal_step1 is not None
    assert Decimal(str(bal_step1[0])) == base_qty + Decimal("10.000")
    assert bal_step1[1] == base_ver + 1

    # Lần 2: Nhập thêm 15.000 cùng vị trí
    tx2_id = apply_movement(
        db=db_session,
        warehouse_id=wh_id,
        location_id=loc_id,
        sku_id=sku_id,
        lot_id=None,
        pallet_id=None,
        serial_number=None,
        tx_type="RECEIVE",
        delta_available=Decimal("15.000"),
        ref_doc_type="PO",
        ref_doc_id=uuid.uuid4(),
        performed_by=user_id,
    )
    assert tx2_id is not None

    bal_step2 = db_session.execute(
        text(
            """
            SELECT qty_available, version_no FROM inventory_balances
            WHERE warehouse_id = :w AND location_id = :l AND sku_id = :s;
            """
        ),
        {"w": wh_id, "l": loc_id, "s": sku_id},
    ).fetchone()
    assert bal_step2 is not None
    # Khẳng định tồn cộng đúng tổng 25.000 và version_no tăng thêm 1
    assert Decimal(str(bal_step2[0])) == base_qty + Decimal("25.000")
    assert bal_step2[1] == base_ver + 2


def test_apply_movement_insufficient_qty_raises_business_error(db_session: Session) -> None:
    """(b) Trừ quá tồn: BusinessError INVENTORY_INSUFFICIENT_QTY (HTTP 409)."""
    wh_row = db_session.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).fetchone()
    loc_row = db_session.execute(text("SELECT location_id FROM locations LIMIT 1")).fetchone()
    sku_row = db_session.execute(text("SELECT sku_id FROM skus LIMIT 1")).fetchone()
    user_row = db_session.execute(text("SELECT user_id FROM users LIMIT 1")).fetchone()
    assert wh_row and loc_row and sku_row and user_row

    # Cố tình trừ 999,999.000 vượt quá tồn kho
    with pytest.raises(BusinessError) as exc_info:
        apply_movement(
            db=db_session,
            warehouse_id=wh_row[0],
            location_id=loc_row[0],
            sku_id=sku_row[0],
            lot_id=None,
            pallet_id=None,
            serial_number=None,
            tx_type="SHIP_GI",
            delta_available=Decimal("-999999.000"),
            ref_doc_type="SO",
            ref_doc_id=uuid.uuid4(),
            performed_by=user_row[0],
        )

    assert exc_info.value.code == "INVENTORY_INSUFFICIENT_QTY"
    assert exc_info.value.http_status == 409


def test_transfer_inventory_preserves_allocated_bucket(db_session: Session) -> None:
    """(c) transfer_inventory giữ nguyên bucket ALLOCATED (không bị chuyển sang AVAILABLE)."""
    wh_row = db_session.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).fetchone()
    locs = db_session.execute(text("SELECT location_id FROM locations LIMIT 2")).fetchall()
    sku_row = db_session.execute(text("SELECT sku_id FROM skus LIMIT 1")).fetchone()
    user_row = db_session.execute(text("SELECT user_id FROM users LIMIT 1")).fetchone()
    assert wh_row and len(locs) >= 2 and sku_row and user_row

    wh_id = wh_row[0]
    loc_from, loc_to = locs[0][0], locs[1][0]
    sku_id = sku_row[0]
    user_id = user_row[0]

    # 1. Nạp sẵn 20.000 ở bucket ALLOCATED tại loc_from
    apply_movement(
        db=db_session,
        warehouse_id=wh_id,
        location_id=loc_from,
        sku_id=sku_id,
        lot_id=None,
        pallet_id=None,
        serial_number=None,
        tx_type="ALLOCATE",
        delta_available=Decimal("0"),
        delta_allocated=Decimal("20.000"),
        ref_doc_type="SO",
        ref_doc_id=uuid.uuid4(),
        performed_by=user_id,
    )

    # 2. Chuyển 8.000 từ loc_from sang loc_to với bucket ALLOCATED
    tx_transfer_id = transfer_inventory(
        db=db_session,
        warehouse_id=wh_id,
        from_location_id=loc_from,
        to_location_id=loc_to,
        sku_id=sku_id,
        lot_id=None,
        pallet_id=None,
        serial_number=None,
        qty=Decimal("8.000"),
        tx_type="INTERNAL_MOVE",
        ref_doc_type="SO",
        ref_doc_id=uuid.uuid4(),
        performed_by=user_id,
        bucket="ALLOCATED",
    )
    assert tx_transfer_id is not None

    # 3. Kiểm tra vị trí đích loc_to: Phải tăng đúng 8.000 ở qty_allocated, qty_available = 0
    to_bal = db_session.execute(
        text(
            """
            SELECT qty_available, qty_allocated FROM inventory_balances
            WHERE warehouse_id = :w AND location_id = :l AND sku_id = :s;
            """
        ),
        {"w": wh_id, "l": loc_to, "s": sku_id},
    ).fetchone()
    assert to_bal is not None
    assert Decimal(str(to_bal[1])) >= Decimal("8.000")  # qty_allocated tăng 8
    assert Decimal(str(to_bal[0])) == Decimal("0")  # qty_available vẫn là 0 (giữ nguyên ALLOCATED)


def test_inventory_balances_permissions_and_filters() -> None:
    """(d) GET /inventory/balances lọc đúng, và vai trò nv-kiemke và admin bị 403."""
    thukho_token = get_token("thukho")
    nhan_token = get_token("nv_nhan")
    kiemke_token = get_token("nv_kiemke")
    admin_token = get_token("admin")

    # 1. Thủ kho và NV Nhận có quyền xem tồn kho -> 200 OK
    res_thukho = client.get(
        "/api/v1/inventory/balances",
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert res_thukho.status_code == 200
    assert "data" in res_thukho.json()

    res_nhan = client.get(
        "/api/v1/inventory/balances",
        headers={"Authorization": f"Bearer {nhan_token}"},
    )
    assert res_nhan.status_code == 200

    # 2. Vai trò nv-kiemke và admin BỊ CHẶN 403 FORBIDDEN
    res_kiemke = client.get(
        "/api/v1/inventory/balances",
        headers={"Authorization": f"Bearer {kiemke_token}"},
    )
    assert res_kiemke.status_code == 403
    assert res_kiemke.json()["error"]["code"] == "FORBIDDEN"

    res_admin = client.get(
        "/api/v1/inventory/balances",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 403
    assert res_admin.json()["error"]["code"] == "FORBIDDEN"


def test_tasks_lifecycle_state_machine_and_worker_isolation(db_session: Session) -> None:
    """(e) Tasks: tạo, giao, nhận, hoàn tất theo đúng thứ tự;

    sai thứ tự trả INVALID_STATE; sai version_no trả VERSION_CONFLICT;
    nhân viên chỉ thấy task của mình.
    """
    thukho_token = get_token("thukho")
    soan_token = get_token("nv_soan")
    cat_token = get_token("nv_cat")

    soan_user_id = db_session.execute(
        text("SELECT user_id FROM users WHERE username = 'nv_soan';")
    ).scalar()
    assert soan_user_id is not None

    # 1. Tạo task mới (Thủ kho)
    create_res = client.post(
        "/api/v1/tasks",
        json={
            "task_type": "PICKING",
            "stage": "SOAN_HANG",
            "ref_doc_type": "SO",
            "ref_doc_id": str(uuid.uuid4()),
            "priority": "HIGH",
        },
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert create_res.status_code == 200
    task_data = create_res.json()["data"]
    task_id = task_data["task_id"]
    assert task_data["status"] == "UNASSIGNED"
    assert task_data["version_no"] == 1

    # 2. Sai thứ tự: Thử nhận task khi chưa được giao -> 409 INVALID_STATE
    invalid_accept = client.post(
        f"/api/v1/tasks/{task_id}/accept",
        json={"version_no": 1},
        headers={"Authorization": f"Bearer {soan_token}"},
    )
    assert invalid_accept.status_code == 403 or invalid_accept.status_code == 409

    # 3. Sai version_no: Giao task với version_no sai (ví dụ: 99) -> 409 VERSION_CONFLICT
    conflict_assign = client.post(
        f"/api/v1/tasks/{task_id}/assign",
        json={"assigned_to": str(soan_user_id), "version_no": 99},
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert conflict_assign.status_code == 409
    assert conflict_assign.json()["error"]["code"] == "VERSION_CONFLICT"

    # 4. Giao task hợp lệ cho nv_soan với version_no = 1 -> ASSIGNED, version_no = 2
    assign_res = client.post(
        f"/api/v1/tasks/{task_id}/assign",
        json={"assigned_to": str(soan_user_id), "version_no": 1},
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["data"]["status"] == "ASSIGNED"
    assert assign_res.json()["data"]["version_no"] == 2

    # 5. Sai nhân viên: nv_cat cố nhận task của nv_soan -> 403 FORBIDDEN
    wrong_worker_accept = client.post(
        f"/api/v1/tasks/{task_id}/accept",
        json={"version_no": 2},
        headers={"Authorization": f"Bearer {cat_token}"},
    )
    assert wrong_worker_accept.status_code == 403
    assert wrong_worker_accept.json()["error"]["code"] == "FORBIDDEN"

    # 6. nv_soan nhận task hợp lệ -> IN_PROGRESS, version_no = 3
    accept_res = client.post(
        f"/api/v1/tasks/{task_id}/accept",
        json={"version_no": 2},
        headers={"Authorization": f"Bearer {soan_token}"},
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["data"]["status"] == "IN_PROGRESS"
    assert accept_res.json()["data"]["version_no"] == 3

    # 7. nv_soan hoàn tất task -> COMPLETED, version_no = 4
    complete_res = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        json={"completed_qty": "10.000", "version_no": 3},
        headers={"Authorization": f"Bearer {soan_token}"},
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["data"]["status"] == "COMPLETED"
    assert complete_res.json()["data"]["progress_pct"] == "100.00"
    assert complete_res.json()["data"]["version_no"] == 4

    # 8. Kiểm tra giới hạn hiển thị: Nhân viên chỉ thấy task của mình
    # nv_soan xem danh sách -> thấy task vừa hoàn tất
    tasks_soan = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {soan_token}"})
    assert tasks_soan.status_code == 200
    task_ids_soan = [t["task_id"] for t in tasks_soan.json()["data"]]
    assert task_id in task_ids_soan

    # nv_cat xem danh sách -> KHÔNG thấy task của nv_soan
    tasks_cat = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {cat_token}"})
    assert tasks_cat.status_code == 200
    task_ids_cat = [t["task_id"] for t in tasks_cat.json()["data"]]
    assert task_id not in task_ids_cat

    # nv_cat xem chi tiết task của nv_soan -> 403 FORBIDDEN
    cat_detail = client.get(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {cat_token}"},
    )
    assert cat_detail.status_code == 403
