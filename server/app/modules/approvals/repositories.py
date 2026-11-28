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


def get_latest_approved_by_object(
    db: Session,
    warehouse_id: uuid.UUID,
    object_type: str,
    object_id: uuid.UUID,
    for_update: bool = False,
) -> ApprovalRequest | None:
    """Lấy hồ sơ phê duyệt đã `APPROVED` mới nhất theo đối tượng nguồn."""
    stmt = (
        select(ApprovalRequest)
        .where(
            ApprovalRequest.warehouse_id == warehouse_id,
            ApprovalRequest.object_type == cast(object_type, PG_APPROVAL_OBJECT),
            ApprovalRequest.object_id == object_id,
            ApprovalRequest.status == cast("APPROVED", PG_APPROVAL_STATUS),
        )
        .order_by(ApprovalRequest.created_at.desc())
        .limit(1)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Chứng từ nguồn của hồ sơ duyệt: người duyệt phải thấy lệch gì trước khi quyết định.
# Đọc thẳng bảng (không gọi service inbound/cycle_count) để tránh import vòng và để cấp
# D3 (bgd, không có quyền NH-1/KK-1) vẫn xem được hồ sơ mình duyệt.
# ---------------------------------------------------------------------------


def get_object_refs(db: Session, pairs: list[tuple[str, uuid.UUID]]) -> dict[uuid.UUID, str]:
    """Số chứng từ hiển thị cho từng hồ sơ: số GRN, hoặc `số phiếu kiểm kê / vị trí`."""
    grn_ids = [oid for otype, oid in pairs if otype == "GRN_DISCREPANCY"]
    line_ids = [oid for otype, oid in pairs if otype == "CYCLE_COUNT_DIFF"]
    refs: dict[uuid.UUID, str] = {}
    if grn_ids:
        rows = db.execute(
            text("SELECT grn_id, grn_number FROM grns WHERE grn_id = ANY(:ids)"),
            {"ids": grn_ids},
        ).fetchall()
        refs.update({r[0]: r[1] for r in rows})
    if line_ids:
        rows = db.execute(
            text(
                """
                SELECT cl.count_line_id, cs.sheet_number || ' / ' || l.location_code
                FROM cycle_count_lines cl
                JOIN cycle_count_sheets cs ON cs.count_sheet_id = cl.count_sheet_id
                JOIN locations l ON l.location_id = cl.location_id
                WHERE cl.count_line_id = ANY(:ids)
                """
            ),
            {"ids": line_ids},
        ).fetchall()
        refs.update({r[0]: r[1] for r in rows})
    return refs


def get_user_display_name(db: Session, user_id: uuid.UUID) -> str | None:
    row = db.execute(
        text("SELECT full_name, username FROM users WHERE user_id = :uid"), {"uid": user_id}
    ).first()
    if row is None:
        return None
    return f"{row[0]} ({row[1]})" if row[0] else str(row[1])


def get_grn_source(db: Session, grn_id: uuid.UUID) -> dict[str, Any] | None:
    head = db.execute(
        text(
            """
            SELECT g.grn_number, g.status::text, g.recount_count, po.erp_po_number
            FROM grns g
            LEFT JOIN purchase_orders po ON po.po_id = g.po_id
            WHERE g.grn_id = :gid
            """
        ),
        {"gid": grn_id},
    ).first()
    if head is None:
        return None
    lines = db.execute(
        text(
            """
            SELECT s.sku_code, s.sku_name, gl.uom_code, lt.lot_number,
                   gl.qty_expected, gl.qty_actual, gl.qty_damaged, gl.qty_variance,
                   gl.variance_amount, gl.reason_code, rc.description
            FROM grn_lines gl
            JOIN skus s ON s.sku_id = gl.sku_id
            LEFT JOIN lots lt ON lt.lot_id = gl.lot_id
            LEFT JOIN reason_codes rc ON rc.reason_code = gl.reason_code
            WHERE gl.grn_id = :gid
            ORDER BY s.sku_code
            """
        ),
        {"gid": grn_id},
    ).fetchall()
    return {
        "doc_type": "GRN",
        "doc_number": head[0],
        "doc_status": head[1],
        "recount_count": head[2],
        "parent_doc_number": head[3],
        "lines": [
            {
                "sku_code": r[0],
                "sku_name": r[1],
                "uom_code": r[2],
                "lot_number": r[3],
                "location_code": None,
                "qty_expected": r[4],
                "qty_counted": r[5],
                "qty_damaged": r[6],
                "qty_variance": r[7],
                "variance_amount": r[8],
                "reason_code": r[9],
                "reason_description": r[10],
            }
            for r in lines
        ],
    }


def get_cycle_count_source(db: Session, line_id: uuid.UUID) -> dict[str, Any] | None:
    r = db.execute(
        text(
            """
            SELECT cs.sheet_number, cs.status::text, cl.recount_count,
                   s.sku_code, s.sku_name, s.base_uom, lt.lot_number, l.location_code,
                   cl.system_qty_snapshot, cl.final_counted_qty, cl.variance_qty,
                   cl.variance_amount, cl.anomaly_type
            FROM cycle_count_lines cl
            JOIN cycle_count_sheets cs ON cs.count_sheet_id = cl.count_sheet_id
            JOIN locations l ON l.location_id = cl.location_id
            LEFT JOIN skus s ON s.sku_id = cl.sku_id
            LEFT JOIN lots lt ON lt.lot_id = cl.lot_id
            WHERE cl.count_line_id = :lid
            """
        ),
        {"lid": line_id},
    ).first()
    if r is None:
        return None
    return {
        "doc_type": "CYCLE_COUNT",
        "doc_number": r[0],
        "doc_status": r[1],
        "recount_count": r[2],
        "parent_doc_number": None,
        "lines": [
            {
                "sku_code": r[3],
                "sku_name": r[4],
                "uom_code": r[5],
                "lot_number": r[6],
                "location_code": r[7],
                "qty_expected": r[8],
                "qty_counted": r[9],
                "qty_damaged": None,
                "qty_variance": r[10],
                "variance_amount": r[11],
                "reason_code": None if (r[12] or "NONE") == "NONE" else r[12],
                "reason_description": None,
            }
        ],
    }
