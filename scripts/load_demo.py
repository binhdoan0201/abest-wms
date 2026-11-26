"""Nạp dữ liệu cho buổi demo (chạy sau scripts/reset_db.sh, không dùng trong CI).

    python -m scripts.load_demo

Chạy lại nhiều lần an toàn: phần nào đã có thì bỏ qua.

Nạp gì:
- Tài khoản `nv_nhan2`, `nv_kiemke2` (kho WH01, cùng mật khẩu demo): đếm lại GRN (NH-5) và
  đếm lại kiểm kê bắt buộc người khác người đếm trước, seed gốc chỉ có một người mỗi vai trò.
- Xe và tài xế mẫu nằm trong seed gốc `02_master_demo.sql` (danh mục `vehicles`).
- Tồn trên kệ dãy A02 qua `apply_movement` (`RECEIVE`), nên sổ cái và trạng thái vị trí khớp
  như hàng nhập thật:
    * Sữa SKU-FOOD-001: lô DEMO-SUA-A hết hạn sau 6 ngày (cảnh báo cận date, FEFO lấy trước)
      và lô DEMO-SUA-B hết hạn sau 90 ngày.
    * Bánh mì SKU-FOOD-002: lô DEMO-BANH-HH đã hết hạn (cảnh báo hết hạn, cấp phát bỏ qua).
    * Bàn ủi SKU-ELEC-003, hộp thủy tinh SKU-GEN-006: hàng không theo lô để demo xuất kho.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.modules.inventory import apply_movement

WAREHOUSE_CODE = "WH01"
DEMO_REF_TYPE = "DEMO_SEED"
DEMO_REF_ID = uuid.UUID("d0000000-0000-0000-0000-000000000001")
SECOND_RECEIVER_ID = uuid.UUID("c0000000-0000-0000-0000-000000000010")
SECOND_COUNTER_ID = uuid.UUID("c0000000-0000-0000-0000-000000000011")

# (username mới, sao chép từ, user_id, họ tên, email, điện thoại)
DEMO_USERS: list[tuple[str, str, uuid.UUID, str, str, str]] = [
    (
        "nv_nhan2",
        "nv_nhan",
        SECOND_RECEIVER_ID,
        "Ngô Thị Nhận Hai",
        "nv_nhan2@abest-wms.local",
        "0901000010",
    ),
    (
        "nv_kiemke2",
        "nv_kiemke",
        SECOND_COUNTER_ID,
        "Đặng Văn Kiểm Hai",
        "nv_kiemke2@abest-wms.local",
        "0901000011",
    ),
]

# (sku_code, lot_number hoặc None, số ngày tới hạn hoặc None, số lượng, vị trí)
DEMO_STOCK: list[tuple[str, str | None, int | None, int, str]] = [
    ("SKU-FOOD-001", "DEMO-SUA-A", 6, 24, "LOC-A02-01"),
    ("SKU-FOOD-001", "DEMO-SUA-B", 90, 60, "LOC-A02-02"),
    ("SKU-FOOD-002", "DEMO-BANH-HH", -1, 6, "LOC-A02-03"),
    ("SKU-ELEC-003", None, None, 40, "LOC-A02-04"),
    ("SKU-GEN-006", None, None, 50, "LOC-A02-05"),
]


def _one(db: Session, sql: str, **params: object) -> object:
    return db.execute(text(sql), params).scalar_one()


def _copy_user(
    db: Session, username: str, source: str, user_id: uuid.UUID, name: str, email: str, phone: str
) -> bool:
    """Tạo tài khoản bằng cách sao chép hồ sơ `source` (vai trò, kho, khâu, mật khẩu)."""
    exists = db.execute(text("SELECT 1 FROM users WHERE username = :u"), {"u": username}).first()
    if exists:
        return False
    db.execute(
        text(
            """
            INSERT INTO users (user_id, username, full_name, email, phone, auth_provider,
                               password_hash, must_change_password, primary_warehouse_id,
                               primary_role_id, primary_stage, status)
            SELECT :uid, :username, :name, :email, :phone, auth_provider, password_hash, FALSE,
                   primary_warehouse_id, primary_role_id, primary_stage, 'ACTIVE'
            FROM users WHERE username = :source
            """
        ),
        {
            "uid": user_id,
            "username": username,
            "name": name,
            "email": email,
            "phone": phone,
            "source": source,
        },
    )
    return True


def add_demo_users(db: Session) -> list[str]:
    """Tạo các tài khoản thứ hai cho bước đếm lại; trả về tên đã tạo mới."""
    return [
        username
        for username, source, user_id, name, email, phone in DEMO_USERS
        if _copy_user(db, username, source, user_id, name, email, phone)
    ]


def add_second_receiver(db: Session) -> bool:
    """Chỉ tạo `nv_nhan2` (test e2e dùng)."""
    return _copy_user(db, *DEMO_USERS[0])


def add_demo_stock(db: Session) -> int:
    """Nhập tồn demo; bỏ qua dòng đã nạp (cùng SKU, lô, vị trí còn hàng)."""
    warehouse_id = _one(
        db, "SELECT warehouse_id FROM warehouses WHERE erp_warehouse_code = :c", c=WAREHOUSE_CODE
    )
    actor = _one(db, "SELECT user_id FROM users WHERE username = 'quanly'")
    today = date.today()
    added = 0
    for sku_code, lot_number, days_to_expiry, qty, location_code in DEMO_STOCK:
        sku_id = _one(db, "SELECT sku_id FROM skus WHERE sku_code = :c", c=sku_code)
        location_id = _one(
            db,
            "SELECT location_id FROM locations WHERE location_code = :c AND warehouse_id = :w",
            c=location_code,
            w=warehouse_id,
        )
        lot_id = None
        if lot_number is not None:
            expiry = today + timedelta(days=days_to_expiry) if days_to_expiry is not None else None
            lot_id = db.execute(
                text(
                    """
                    INSERT INTO lots (sku_id, lot_number, expiry_date)
                    VALUES (:s, :n, :e)
                    ON CONFLICT (sku_id, lot_number)
                    DO UPDATE SET expiry_date = EXCLUDED.expiry_date
                    RETURNING lot_id
                    """
                ),
                {"s": sku_id, "n": lot_number, "e": expiry},
            ).scalar_one()
        on_hand = db.execute(
            text(
                """
                SELECT COALESCE(SUM(qty_available), 0) FROM inventory_balances
                WHERE location_id = :l AND sku_id = :s AND lot_id IS NOT DISTINCT FROM :lot
                """
            ),
            {"l": location_id, "s": sku_id, "lot": lot_id},
        ).scalar_one()
        if on_hand > 0:
            continue
        apply_movement(
            db=db,
            warehouse_id=warehouse_id,  # type: ignore[arg-type]
            location_id=location_id,  # type: ignore[arg-type]
            sku_id=sku_id,  # type: ignore[arg-type]
            lot_id=lot_id,
            pallet_id=None,
            serial_number=None,
            tx_type="RECEIVE",
            delta_available=Decimal(qty),
            ref_doc_type=DEMO_REF_TYPE,
            ref_doc_id=DEMO_REF_ID,
            performed_by=actor,  # type: ignore[arg-type]
        )
        added += 1
    return added


def main() -> None:
    db = SessionLocal()
    try:
        created_users = add_demo_users(db)
        added_stock = add_demo_stock(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print("== Dữ liệu demo ABEST WMS ==")
    for username, source, *_ in DEMO_USERS:
        state = "đã tạo" if username in created_users else "đã có, bỏ qua"
        print(f"- {username}: {state} (cùng vai trò, mật khẩu demo như {source})")
    print(f"- Tồn demo: nhập {added_stock}/{len(DEMO_STOCK)} dòng (dòng đã có hàng thì bỏ qua)")
    for sku_code, lot_number, days, qty, location_code in DEMO_STOCK:
        lot = (
            f"lô {lot_number}, hạn {'+' if (days or 0) >= 0 else ''}{days} ngày"
            if lot_number
            else "không lô"
        )
        print(f"    {sku_code:<13} {qty:>3} tại {location_code} ({lot})")


if __name__ == "__main__":
    main()
