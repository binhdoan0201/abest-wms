"""ABEST WMS - Kiểm thử Unit: Dịch lỗi CSDL (translate_db_error) bằng SQL thật.

Kiểm tra 5 trường hợp lỗi bắt buộc theo Mục 3 Chuẩn API:
1. BAN_GHI_BAT_BIEN (HTTP 500 INTERNAL_IMMUTABLE_RECORD): UPDATE vào inventory_transactions.
2. INVENTORY_INSUFFICIENT_QTY (HTTP 409): Trừ quá tồn, vi phạm check constraint qty_available.
3. ORDER_FROZEN (HTTP 409): Sửa trạng thái đơn hàng khi erp_change_pending = TRUE.
4. REAUTH_REQUIRED (HTTP 403): Phê duyệt hồ sơ vượt ngưỡng reauth_min_amount mà thiếu reauth_method.
5. SOD_VIOLATION (HTTP 403): Người lập đề xuất tự phê duyệt hồ sơ của chính mình.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.exceptions import translate_db_error


@pytest.fixture
def db_session() -> Session:  # type: ignore[misc]
    """Fixture cung cấp DB session độc lập, luôn rollback sau mỗi test."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_error_immutable_inventory_transactions(db_session: Session) -> None:
    """Kiểm tra lỗi BAN_GHI_BAT_BIEN khi UPDATE bảng inventory_transactions."""
    # 1. Lấy thông tin master data có sẵn từ seed
    wh_row = db_session.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).fetchone()
    sku_row = db_session.execute(text("SELECT sku_id FROM skus LIMIT 1")).fetchone()
    user_row = db_session.execute(text("SELECT user_id FROM users LIMIT 1")).fetchone()
    assert wh_row and sku_row and user_row

    warehouse_id = wh_row[0]
    sku_id = sku_row[0]
    user_id = user_row[0]

    # 2. INSERT một transaction hợp lệ
    insert_sql = text(
        """
        INSERT INTO inventory_transactions (
            warehouse_id, tx_type, sku_id, qty_change,
            unit_cost_snapshot, ref_doc_type, ref_doc_id, performed_by
        ) VALUES (
            :wh_id, 'RECEIVE', :sku_id, 10.0,
            1000.0, 'PO', :ref_doc_id, :user_id
        ) RETURNING tx_id;
        """
    )
    result = db_session.execute(
        insert_sql,
        {
            "wh_id": warehouse_id,
            "sku_id": sku_id,
            "ref_doc_id": uuid.uuid4(),
            "user_id": user_id,
        },
    )
    tx_id = result.scalar_one()

    # 3. Thử UPDATE dòng giao dịch vừa tạo -> phải kích hoạt trg_immutable_inventory_tx
    with pytest.raises(Exception) as exc_info:
        db_session.execute(
            text("UPDATE inventory_transactions SET qty_change = 20.0 WHERE tx_id = :tx_id;"),
            {"tx_id": tx_id},
        )

    # 4. Dịch lỗi và kiểm tra kết quả
    business_error = translate_db_error(exc_info.value)
    assert business_error.code == "INTERNAL_IMMUTABLE_RECORD"
    assert business_error.http_status == 500
    assert "Bản ghi bất biến" in business_error.message


def test_error_inventory_insufficient_qty(db_session: Session) -> None:
    """Kiểm tra vi phạm check constraint qty_available >= 0 (INVENTORY_INSUFFICIENT_QTY)."""
    wh_row = db_session.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).fetchone()
    loc_row = db_session.execute(text("SELECT location_id FROM locations LIMIT 1")).fetchone()
    sku_row = db_session.execute(text("SELECT sku_id FROM skus LIMIT 1")).fetchone()
    assert wh_row and loc_row and sku_row

    # Thử chèn bản ghi tồn kho có qty_available âm
    with pytest.raises(Exception) as exc_info:
        db_session.execute(
            text(
                """
                INSERT INTO inventory_balances (
                    warehouse_id, location_id, sku_id, qty_available
                ) VALUES (
                    :wh_id, :loc_id, :sku_id, -5.0
                );
                """
            ),
            {"wh_id": wh_row[0], "loc_id": loc_row[0], "sku_id": sku_row[0]},
        )

    business_error = translate_db_error(exc_info.value)
    assert business_error.code == "INVENTORY_INSUFFICIENT_QTY"
    assert business_error.http_status == 409


def test_error_order_frozen(db_session: Session) -> None:
    """Kiểm tra lỗi DON_BI_DONG_BANG khi sửa đơn hàng đang có yêu cầu đổi/hủy từ ERP."""
    wh_row = db_session.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).fetchone()
    cust_row = db_session.execute(text("SELECT customer_id FROM customers LIMIT 1")).fetchone()
    assert wh_row and cust_row

    order_id = uuid.uuid4()
    erp_order_num = f"SO-FROZEN-{uuid.uuid4().hex[:8]}"

    # Tạo đơn hàng với erp_change_pending = TRUE
    db_session.execute(
        text(
            """
            INSERT INTO outbound_orders (
                order_id, erp_order_number, order_type, warehouse_id, customer_id,
                status, cutoff_time, erp_change_pending
            ) VALUES (
                :order_id, :erp_num, 'SO', :wh_id, :cust_id,
                'NEW', NOW() + INTERVAL '1 day', TRUE
            );
            """
        ),
        {
            "order_id": order_id,
            "erp_num": erp_order_num,
            "wh_id": wh_row[0],
            "cust_id": cust_row[0],
        },
    )

    # Thử đổi trạng thái đơn hàng bị đóng băng -> kích hoạt trigger fn_freeze_order_status
    with pytest.raises(Exception) as exc_info:
        db_session.execute(
            text("UPDATE outbound_orders SET status = 'PICKING' WHERE order_id = :order_id;"),
            {"order_id": order_id},
        )

    business_error = translate_db_error(exc_info.value)
    assert business_error.code == "ORDER_FROZEN"
    assert business_error.http_status == 409
    assert "đóng băng" in business_error.message


def test_error_reauth_required(db_session: Session) -> None:
    """Kiểm tra lỗi THIEU_XAC_THUC_LAI khi phê duyệt giá trị lớn mà thiếu reauth_method."""
    wh_row = db_session.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).fetchone()
    users = db_session.execute(text("SELECT user_id FROM users LIMIT 2")).fetchall()
    assert wh_row and len(users) >= 2

    warehouse_id = wh_row[0]
    proposer_id = users[0][0]
    approver_id = users[1][0]

    approval_id = uuid.uuid4()
    # Tạo approval_request có giá trị chênh lệch 50,000,000 (vượt ngưỡng 10,000,000 của WH01)
    db_session.execute(
        text(
            """
            INSERT INTO approval_requests (
                approval_id, warehouse_id, object_type, object_id,
                proposer_user_id, current_tier, status, discrepancy_value_amount
            ) VALUES (
                :app_id, :wh_id, 'OVERTIME_REQUEST', :obj_id,
                :prop_id, 'D2_QUANLY', 'PENDING_D2', 50000000.00
            );
            """
        ),
        {
            "app_id": approval_id,
            "wh_id": warehouse_id,
            "obj_id": uuid.uuid4(),
            "prop_id": proposer_id,
        },
    )

    # Approver duyệt mà không có reauth_method -> kích hoạt trg_enforce_reauth
    with pytest.raises(Exception) as exc_info:
        db_session.execute(
            text(
                """
                INSERT INTO approval_histories (
                    approval_id, tier, actor_user_id, action, reauth_method
                ) VALUES (
                    :app_id, 'D2_QUANLY', :approver_id, 'APPROVE', NULL
                );
                """
            ),
            {"app_id": approval_id, "approver_id": approver_id},
        )

    business_error = translate_db_error(exc_info.value)
    assert business_error.code == "REAUTH_REQUIRED"
    assert business_error.http_status == 403
    assert "xác thực lại" in business_error.message


def test_error_sod_violation(db_session: Session) -> None:
    """Kiểm tra lỗi SOD_VIOLATION khi người lập tự duyệt hồ sơ của chính mình."""
    wh_row = db_session.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).fetchone()
    user_row = db_session.execute(text("SELECT user_id FROM users LIMIT 1")).fetchone()
    assert wh_row and user_row

    warehouse_id = wh_row[0]
    proposer_id = user_row[0]
    approval_id = uuid.uuid4()

    db_session.execute(
        text(
            """
            INSERT INTO approval_requests (
                approval_id, warehouse_id, object_type, object_id,
                proposer_user_id, current_tier, status, discrepancy_value_amount
            ) VALUES (
                :app_id, :wh_id, 'OVERTIME_REQUEST', :obj_id,
                :prop_id, 'D1_THUKHO', 'PENDING_D1', 5000.00
            );
            """
        ),
        {
            "app_id": approval_id,
            "wh_id": warehouse_id,
            "obj_id": uuid.uuid4(),
            "prop_id": proposer_id,
        },
    )

    # Chính proposer tự duyệt phiếu của mình -> kích hoạt trigger trg_enforce_sod_all_tiers
    with pytest.raises(Exception) as exc_info:
        db_session.execute(
            text(
                """
                INSERT INTO approval_histories (
                    approval_id, tier, actor_user_id, action, reauth_method
                ) VALUES (
                    :app_id, 'D1_THUKHO', :proposer_id, 'APPROVE', 'PASSWORD'
                );
                """
            ),
            {"app_id": approval_id, "proposer_id": proposer_id},
        )

    business_error = translate_db_error(exc_info.value)
    assert business_error.code == "SOD_VIOLATION"
    assert business_error.http_status == 403
    assert "phân tách nhiệm vụ" in business_error.message
