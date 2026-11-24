"""ABEST WMS - Repository cho Phân hệ Phê duyệt (Approvals).

Chứa truy vấn SQLAlchemy và lời gọi trực tiếp các hàm DB (fn_resolve_approval_tier,
fn_escalate_expired_approvals) theo Quy tắc 6 của đặc tả.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Session

from server.app.modules.approvals.models import (
    ApprovalHistory,
    ApprovalRequest,
    StockAdjustment,
)

PG_APPROVAL_STATUS = PG_ENUM(name="approval_status_type", create_type=False)
PG_APPROVAL_TIER = PG_ENUM(name="approval_tier_type", create_type=False)
PG_APPROVAL_OBJECT = PG_ENUM(name="approval_object_type", create_type=False)


def resolve_approval_tier_db(
    db: Session,
    warehouse_id: uuid.UUID,
    object_type: str,
    amount: Decimal,
    percent: Decimal,
    proposer_id: uuid.UUID,
    force_review: bool = False,
) -> str:
    """Gọi hàm PostgreSQL fn_resolve_approval_tier để xác định tầng duyệt."""
    stmt = text(
        """
        SELECT fn_resolve_approval_tier(
            :warehouse_id,
            CAST(:object_type AS approval_object_type),
            :amount,
            :percent,
            :proposer_id,
            :force_review
        )::TEXT
        """
    )
    tier = db.execute(
        stmt,
        {
            "warehouse_id": warehouse_id,
            "object_type": object_type,
            "amount": amount,
            "percent": percent,
            "proposer_id": proposer_id,
            "force_review": force_review,
        },
    ).scalar_one()
    return str(tier)


def escalate_expired_approvals_db(db: Session) -> int:
    """Gọi hàm PostgreSQL fn_escalate_expired_approvals để leo thang SLA quá hạn."""
    stmt = text("SELECT fn_escalate_expired_approvals()")
    count = db.execute(stmt).scalar_one()
    return int(count or 0)


def get_warehouse_approval_config(db: Session, warehouse_id: uuid.UUID) -> dict[str, Any] | None:
    """Đọc cấu hình ngưỡng duyệt X, Y, xác thực lại và SLA của kho."""
    stmt = text(
        """
        SELECT threshold_x_d1_amount,
               threshold_y_d2_amount,
               reauth_min_amount,
               approval_sla_hours
        FROM warehouse_configs
        WHERE warehouse_id = :warehouse_id
        """
    )
    row = db.execute(stmt, {"warehouse_id": warehouse_id}).mappings().first()
    return dict(row) if row else None


def get_sku_unit_cost(db: Session, sku_id: uuid.UUID) -> Decimal | None:
    """Đọc đơn giá vốn của SKU để tính tổng giá trị đề xuất điều chỉnh/hủy."""
    stmt = text("SELECT unit_cost FROM skus WHERE sku_id = :sku_id")
    val = db.execute(stmt, {"sku_id": sku_id}).scalar_one_or_none()
    return Decimal(str(val)) if val is not None else None


def get_user_password_hash(db: Session, user_id: uuid.UUID) -> str | None:
    """Lấy password_hash của người dùng đang hoạt động để xác thực lại (reauth)."""
    stmt = text("SELECT password_hash FROM users WHERE user_id = :user_id AND status = 'ACTIVE'")
    val = db.execute(stmt, {"user_id": user_id}).scalar_one_or_none()
    return str(val) if val else None


def enqueue_erp_approval_sync(
    db: Session,
    warehouse_id: uuid.UUID,
    doc_type: str,
    doc_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    """Ghi hàng đợi đồng bộ kết quả sau duyệt sang ERP mock."""
    stmt = text(
        """
        INSERT INTO integration_sync_logs (
            warehouse_id, external_system, direction, doc_type, doc_id, business_payload, status
        ) VALUES (
            :warehouse_id, 'ERP', 'OUTBOUND', :doc_type, :doc_id, CAST(:payload AS jsonb), 'PENDING'
        )
        """
    )
    db.execute(
        stmt,
        {
            "warehouse_id": warehouse_id,
            "doc_type": doc_type,
            "doc_id": doc_id,
            "payload": json.dumps(payload, default=str),
        },
    )


def get_approval_by_id(
    db: Session,
    approval_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    for_update: bool = False,
) -> ApprovalRequest | None:
    """Lấy hồ sơ phê duyệt theo ID và phạm vi kho."""
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.approval_id == approval_id,
        ApprovalRequest.warehouse_id == warehouse_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def list_approvals(
    db: Session,
    warehouse_id: uuid.UUID,
    status: str | None = None,
    tier: str | None = None,
    object_type: str | None = None,
    expired: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ApprovalRequest], int]:
    """Lọc danh sách hồ sơ phê duyệt trong kho có phân trang."""
    conditions: list[Any] = [ApprovalRequest.warehouse_id == warehouse_id]

    if status:
        conditions.append(ApprovalRequest.status == cast(status, PG_APPROVAL_STATUS))
    if tier:
        conditions.append(ApprovalRequest.current_tier == cast(tier, PG_APPROVAL_TIER))
    if object_type:
        conditions.append(ApprovalRequest.object_type == cast(object_type, PG_APPROVAL_OBJECT))
    if expired is True:
        now = datetime.now(timezone.utc)
        conditions.append(
            or_(
                ApprovalRequest.status == cast("EXPIRED", PG_APPROVAL_STATUS),
                ApprovalRequest.sla_due_at < now,
            )
        )
    elif expired is False:
        now = datetime.now(timezone.utc)
        conditions.append(ApprovalRequest.status != cast("EXPIRED", PG_APPROVAL_STATUS))
        conditions.append(
            or_(
                ApprovalRequest.sla_due_at.is_(None),
                ApprovalRequest.sla_due_at >= now,
            )
        )

    total_stmt = select(func.count()).select_from(ApprovalRequest).where(*conditions)
    total = int(db.execute(total_stmt).scalar_one() or 0)

    items_stmt = (
        select(ApprovalRequest)
        .where(*conditions)
        .order_by(ApprovalRequest.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(items_stmt).scalars().all())
    return items, total


def list_histories_by_approval(db: Session, approval_id: uuid.UUID) -> list[ApprovalHistory]:
    """Lấy toàn bộ lịch sử duyệt của một hồ sơ theo thứ tự thời gian."""
    stmt = (
        select(ApprovalHistory)
        .where(ApprovalHistory.approval_id == approval_id)
        .order_by(ApprovalHistory.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_stock_adjustment_by_id(
    db: Session, adjustment_id: uuid.UUID, for_update: bool = False
) -> StockAdjustment | None:
    """Lấy đề xuất điều chỉnh tồn/hủy hàng theo ID."""
    stmt = select(StockAdjustment).where(StockAdjustment.adjustment_id == adjustment_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()
