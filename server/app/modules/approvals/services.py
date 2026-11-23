"""ABEST WMS - Nghiệp vụ Phân hệ Phê duyệt (Approvals).

Sử dụng Repository pattern kết hợp lời gọi hàm DB fn_resolve_approval_tier và
fn_escalate_expired_approvals. Thực thi hậu kiểm tồn kho qua inventory.apply_movement.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from server.app.core.audit import create_audit_log
from server.app.core.exceptions import BusinessError, translate_db_error
from server.app.core.rbac import UserContext
from server.app.modules.approvals import repositories as repo
from server.app.modules.approvals.models import (
    ApprovalHistory,
    ApprovalRequest,
    StockAdjustment,
)
from server.app.modules.approvals.schemas import (
    ApproveDecisionRequest,
    RejectDecisionRequest,
    RequestInfoDecisionRequest,
    StockAdjustmentProposalCreate,
)
from server.app.modules.inventory import apply_movement

PG_OBJECT_TYPE = PG_ENUM(name="approval_object_type", create_type=False)
PG_TIER_TYPE = PG_ENUM(name="approval_tier_type", create_type=False)
PG_STATUS_TYPE = PG_ENUM(name="approval_status_type", create_type=False)
PG_EXEC_STATUS_TYPE = PG_ENUM(name="post_approval_exec_status", create_type=False)
PG_ADJ_TYPE = PG_ENUM(name="stock_adjustment_type", create_type=False)

ROLE_TO_TIER: dict[str, str] = {
    "thukho": "D1_THUKHO",
    "quanly": "D2_QUANLY",
    "bgd": "D3_BGD",
}

TIER_TO_PENDING_STATUS: dict[str, str] = {
    "D1_THUKHO": "PENDING_D1",
    "D2_QUANLY": "PENDING_D2",
    "D3_BGD": "PENDING_D3",
}


def _cast_enum(value: str, pg_enum: PG_ENUM) -> Any:
    """Ép kiểu chuỗi Python sang PostgreSQL ENUM tương ứng."""
    return cast(value, pg_enum)


def _compute_sla_due(config: dict[str, Any] | None, tier: str) -> datetime:
    """Tính mốc hạn SLA theo cấu hình kho."""
    default_hours = {"D1_THUKHO": 4, "D2_QUANLY": 8, "D3_BGD": 24}
    tier_short = tier.split("_")[0]  # D1, D2, D3
    sla_map = (config or {}).get("approval_sla_hours") or {}
    hours = float(sla_map.get(tier_short, default_hours.get(tier, 8)))
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _check_tier_permission(user_ctx: UserContext, current_tier: str) -> None:
    """Kiểm tra vai trò của người dùng có khớp với cấp đang chờ duyệt hay không."""
    expected_tier = ROLE_TO_TIER.get(user_ctx.role_code)
    if expected_tier != current_tier:
        raise BusinessError(
            code="FORBIDDEN",
            message=(
                f"Vai trò {user_ctx.role_code} không có quyền xử lý hồ sơ ở cấp {current_tier}."
            ),
            http_status=403,
        )


def _check_sod(proposer_user_id: uuid.UUID, actor_user_id: uuid.UUID) -> None:
    """Kiểm tra nguyên tắc tách biệt nhiệm vụ (SoD) ở tầng ứng dụng."""
    if proposer_user_id == actor_user_id:
        raise BusinessError(
            code="SOD_VIOLATION",
            message="Người lập đề xuất không được phép tự phê duyệt/từ chối hồ sơ của chính mình.",
            http_status=403,
        )


def _execute_post_approval(
    db: Session,
    approval: ApprovalRequest,
    actor_user_id: uuid.UUID,
) -> None:
    """D-05: Thực thi hậu kiểm sau khi hồ sơ được phê duyệt ở cấp cuối cùng."""
    if str(approval.object_type) in ("STOCK_ADJUSTMENT", "STOCK_SCRAP"):
        adj = repo.get_stock_adjustment_by_id(db, approval.object_id, for_update=True)
        if not adj:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy chứng từ điều chỉnh tồn kho liên kết.",
                http_status=404,
            )

        if str(adj.adjustment_type) == "ADJUSTMENT":
            apply_movement(
                db=db,
                warehouse_id=adj.warehouse_id,
                location_id=adj.location_id,
                sku_id=adj.sku_id,
                lot_id=adj.lot_id,
                pallet_id=adj.source_pallet_id,
                serial_number=None,
                tx_type="ADJUSTMENT",
                delta_available=adj.qty_adjustment,
                delta_allocated=Decimal("0"),
                delta_counting=Decimal("0"),
                delta_locked=Decimal("0"),
                delta_damaged=Decimal("0"),
                ref_doc_type="STOCK_ADJ",
                ref_doc_id=adj.adjustment_id,
                performed_by=actor_user_id,
            )
            adj.execution_status = _cast_enum("EXECUTED_INVENTORY", PG_EXEC_STATUS_TYPE)
            approval.execution_status = _cast_enum("EXECUTED_INVENTORY", PG_EXEC_STATUS_TYPE)
        else:
            # Loại SCRAP: chờ Thủ kho xác nhận tiêu hủy vật lý tại TK-5.10
            adj.execution_status = _cast_enum("WAITING_SCRAP_EXECUTION", PG_EXEC_STATUS_TYPE)
            approval.execution_status = _cast_enum("WAITING_SCRAP_EXECUTION", PG_EXEC_STATUS_TYPE)

        repo.enqueue_erp_approval_sync(
            db=db,
            warehouse_id=approval.warehouse_id,
            doc_type=str(adj.adjustment_type),
            doc_id=adj.adjustment_id,
            payload={
                "approval_id": str(approval.approval_id),
                "adjustment_id": str(adj.adjustment_id),
                "adjustment_type": str(adj.adjustment_type),
                "sku_id": str(adj.sku_id),
                "qty_adjustment": str(adj.qty_adjustment),
                "reason_code": adj.reason_code,
            },
        )
    else:
        # GRN_DISCREPANCY / CYCLE_COUNT_DIFF: trigger fn_approval_mirror_status đã cập nhật
        # trạng thái chứng từ gốc sang APPROVED; module sở hữu sẽ hoàn tất bước ghi tồn.
        approval.execution_status = _cast_enum("WAITING_EXECUTION", PG_EXEC_STATUS_TYPE)


def create_approval_request(
    db: Session,
    warehouse_id: uuid.UUID,
    object_type: str,
    object_id: uuid.UUID,
    proposer_user_id: uuid.UUID,
    discrepancy_amount: Decimal,
    discrepancy_percent: Decimal = Decimal("0"),
    force_review: bool = False,
) -> ApprovalRequest | None:
    """Hàm công khai (D-03) cho module khác gọi để phân luồng và tạo yêu cầu duyệt.

    Trả về None nếu giá trị nằm trong dung sai Z (AUTO_TOLERANCE_Z).
    """
    tier = repo.resolve_approval_tier_db(
        db=db,
        warehouse_id=warehouse_id,
        object_type=object_type,
        amount=discrepancy_amount,
        percent=discrepancy_percent,
        proposer_id=proposer_user_id,
        force_review=force_review,
    )
    if tier == "AUTO_TOLERANCE_Z":
        return None

    config = repo.get_warehouse_approval_config(db, warehouse_id)
    pending_status = TIER_TO_PENDING_STATUS[tier]
    sla_due = _compute_sla_due(config, tier)
    abs_amount = abs(discrepancy_amount)

    approval = ApprovalRequest(
        warehouse_id=warehouse_id,
        object_type=_cast_enum(object_type, PG_OBJECT_TYPE),
        object_id=object_id,
        proposer_user_id=proposer_user_id,
        current_tier=_cast_enum(tier, PG_TIER_TYPE),
        status=_cast_enum(pending_status, PG_STATUS_TYPE),
        execution_status=_cast_enum("WAITING_EXECUTION", PG_EXEC_STATUS_TYPE),
        discrepancy_value_amount=abs_amount,
        sla_due_at=sla_due,
        version_no=1,
    )
    try:
        db.add(approval)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=warehouse_id,
        actor_user_id=proposer_user_id,
        action_code="APPROVAL_CREATE",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        new_values={
            "object_type": object_type,
            "object_id": str(object_id),
            "tier": tier,
            "status": pending_status,
            "amount": str(abs_amount),
        },
    )
    return approval


def propose_stock_adjustment(
    db: Session,
    user_ctx: UserContext,
    req: StockAdjustmentProposalCreate,
) -> ApprovalRequest:
    """D-04: Thủ kho hoặc Quản lý đề xuất điều chỉnh tồn / hủy hàng (TK-4.3, TK-5.3)."""
    if user_ctx.role_code not in ("thukho", "quanly"):
        raise BusinessError(
            code="FORBIDDEN",
            message="Chỉ Thủ kho hoặc Quản lý kho mới được đề xuất điều chỉnh tồn/hủy hàng.",
            http_status=403,
        )

    unit_cost = repo.get_sku_unit_cost(db, req.sku_id)
    if unit_cost is None:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy SKU để tính giá trị đề xuất điều chỉnh.",
            http_status=404,
        )

    total_value = (abs(req.qty_adjustment) * unit_cost).quantize(Decimal("0.01"))
    object_type = "STOCK_SCRAP" if req.adjustment_type == "SCRAP" else "STOCK_ADJUSTMENT"

    adj = StockAdjustment(
        warehouse_id=user_ctx.warehouse_id,
        adjustment_type=_cast_enum(req.adjustment_type, PG_ADJ_TYPE),
        location_id=req.location_id,
        sku_id=req.sku_id,
        lot_id=req.lot_id,
        source_pallet_id=req.source_pallet_id,
        damaged_pallet_id=req.damaged_pallet_id,
        qty_adjustment=req.qty_adjustment,
        total_value_amount=total_value,
        reason_code=req.reason_code,
        proposal_photo_urls=req.proposal_photo_urls,
        proposed_by=user_ctx.user_id,
        proposed_by_role=user_ctx.role_code.upper(),
        status=_cast_enum("PENDING_D2", PG_STATUS_TYPE),
        execution_status=_cast_enum("WAITING_EXECUTION", PG_EXEC_STATUS_TYPE),
    )
    try:
        db.add(adj)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    approval = create_approval_request(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        object_type=object_type,
        object_id=adj.adjustment_id,
        proposer_user_id=user_ctx.user_id,
        discrepancy_amount=total_value,
        force_review=True,
    )
    assert approval is not None  # force_review=True luôn tạo phiếu duyệt
    return approval


def list_approvals_queue(
    db: Session,
    user_ctx: UserContext,
    status: str | None = None,
    tier: str | None = None,
    object_type: str | None = None,
    expired: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ApprovalRequest], int]:
    """Lấy hàng chờ duyệt theo kho và bộ lọc."""
    if user_ctx.role_code not in ROLE_TO_TIER:
        raise BusinessError(
            code="FORBIDDEN",
            message="Vai trò hiện tại không có quyền xem danh sách phê duyệt.",
            http_status=403,
        )

    effective_tier = tier
    if effective_tier is None and status is None:
        effective_tier = ROLE_TO_TIER[user_ctx.role_code]

    return repo.list_approvals(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        status=status,
        tier=effective_tier,
        object_type=object_type,
        expired=expired,
        page=page,
        page_size=page_size,
    )


def get_approval_detail(
    db: Session,
    user_ctx: UserContext,
    approval_id: uuid.UUID,
    acquire_lock: bool = True,
) -> tuple[ApprovalRequest, list[ApprovalHistory]]:
    """Xem chi tiết hồ sơ, ghi nhận khóa xem chống mở trùng phiếu và trả lịch sử."""
    if user_ctx.role_code not in ROLE_TO_TIER:
        raise BusinessError(
            code="FORBIDDEN",
            message="Vai trò hiện tại không có quyền xem chi tiết hồ sơ phê duyệt.",
            http_status=403,
        )

    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=user_ctx.warehouse_id,
        for_update=acquire_lock,
    )
    if not approval:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy hồ sơ phê duyệt trong kho hiện tại.",
            http_status=404,
        )

    if acquire_lock and str(approval.status) in (
        "PENDING_D1",
        "PENDING_D2",
        "PENDING_D3",
        "NEED_INFO",
    ):
        if (
            approval.locked_by_viewer_id is not None
            and approval.locked_by_viewer_id != user_ctx.user_id
        ):
            raise BusinessError(
                code="APPROVAL_LOCKED_BY_OTHER",
                message="Hồ sơ đang được cán bộ duyệt khác mở xử lý.",
                http_status=409,
            )
        approval.locked_by_viewer_id = user_ctx.user_id
        approval.locked_at = datetime.now(timezone.utc)
        db.flush()

    histories = repo.list_histories_by_approval(db, approval_id)
    return approval, histories


def approve_request(
    db: Session,
    user_ctx: UserContext,
    approval_id: uuid.UUID,
    req: ApproveDecisionRequest,
) -> ApprovalRequest:
    """D-03/D-04/D-05: Phê duyệt hồ sơ hoặc chuyển tiếp lên cấp trên nếu vượt ngưỡng."""
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=user_ctx.warehouse_id,
        for_update=True,
    )
    if not approval:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy hồ sơ phê duyệt.",
            http_status=404,
        )

    if approval.version_no != req.version_no:
        raise BusinessError(
            code="VERSION_CONFLICT",
            message="Hồ sơ phê duyệt đã được người khác cập nhật.",
            http_status=409,
            details={"current_version_no": approval.version_no},
        )

    old_status = str(approval.status)
    old_tier = str(approval.current_tier)

    if old_status not in ("PENDING_D1", "PENDING_D2", "PENDING_D3", "EXPIRED"):
        raise BusinessError(
            code="INVALID_STATE",
            message=f"Hồ sơ đang ở trạng thái {old_status}, không thể phê duyệt.",
            http_status=409,
        )

    _check_sod(approval.proposer_user_id, user_ctx.user_id)
    _check_tier_permission(user_ctx, old_tier)

    config = repo.get_warehouse_approval_config(db, user_ctx.warehouse_id)
    reauth_min = Decimal(str((config or {}).get("reauth_min_amount", "10000000.00")))
    if approval.discrepancy_value_amount >= reauth_min and not req.reauth_method:
        raise BusinessError(
            code="REAUTH_REQUIRED",
            message="Hồ sơ có giá trị vượt ngưỡng xác thực lại, bắt buộc cung cấp reauth_method.",
            http_status=403,
        )

    threshold_x = Decimal(str((config or {}).get("threshold_x_d1_amount", "5000000.00")))
    threshold_y = Decimal(str((config or {}).get("threshold_y_d2_amount", "20000000.00")))

    # Xác định có cần chuyển tiếp lên cấp cao hơn hay chốt APPROVED
    next_tier: str | None = None
    if old_tier == "D1_THUKHO" and approval.discrepancy_value_amount > threshold_x:
        next_tier = "D2_QUANLY"
    elif old_tier == "D2_QUANLY" and approval.discrepancy_value_amount > threshold_y:
        next_tier = "D3_BGD"

    if next_tier:
        history_action = "ESCALATE_NEXT_TIER"
        new_tier_str = next_tier
        new_status_str = TIER_TO_PENDING_STATUS[next_tier]
        approval.current_tier = _cast_enum(new_tier_str, PG_TIER_TYPE)
        approval.status = _cast_enum(new_status_str, PG_STATUS_TYPE)
        approval.sla_due_at = _compute_sla_due(config, next_tier)
    else:
        history_action = "APPROVE"
        new_tier_str = old_tier
        new_status_str = "APPROVED"
        approval.status = _cast_enum("APPROVED", PG_STATUS_TYPE)
        approval.final_decided_by = user_ctx.user_id
        approval.final_decided_at = datetime.now(timezone.utc)

    approval.locked_by_viewer_id = None
    approval.locked_at = None
    approval.version_no += 1

    history = ApprovalHistory(
        approval_id=approval.approval_id,
        tier=_cast_enum(old_tier, PG_TIER_TYPE),
        actor_user_id=user_ctx.user_id,
        action=history_action,
        recommendation_or_reason=req.recommendation_or_reason,
        reauth_method=req.reauth_method,
    )
    try:
        db.add(history)
        db.flush()
        if history_action == "APPROVE":
            _execute_post_approval(db=db, approval=approval, actor_user_id=user_ctx.user_id)
            db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        actor_user_id=user_ctx.user_id,
        action_code="TK-3.2" if old_tier == "D1_THUKHO" else "QL-7.2",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        old_values={"status": old_status, "tier": old_tier},
        new_values={
            "status": new_status_str,
            "tier": new_tier_str,
            "action": history_action,
        },
        reauth_verified=bool(req.reauth_method),
    )
    return approval


def reject_request(
    db: Session,
    user_ctx: UserContext,
    approval_id: uuid.UUID,
    req: RejectDecisionRequest,
) -> ApprovalRequest:
    """Từ chối hồ sơ phê duyệt kèm lý do."""
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=user_ctx.warehouse_id,
        for_update=True,
    )
    if not approval:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy hồ sơ phê duyệt.",
            http_status=404,
        )

    if approval.version_no != req.version_no:
        raise BusinessError(
            code="VERSION_CONFLICT",
            message="Hồ sơ phê duyệt đã được người khác cập nhật.",
            http_status=409,
            details={"current_version_no": approval.version_no},
        )

    old_status = str(approval.status)
    old_tier = str(approval.current_tier)

    if old_status not in ("PENDING_D1", "PENDING_D2", "PENDING_D3", "NEED_INFO", "EXPIRED"):
        raise BusinessError(
            code="INVALID_STATE",
            message=f"Hồ sơ đang ở trạng thái {old_status}, không thể từ chối.",
            http_status=409,
        )

    _check_sod(approval.proposer_user_id, user_ctx.user_id)
    _check_tier_permission(user_ctx, old_tier)

    approval.status = _cast_enum("REJECTED", PG_STATUS_TYPE)
    approval.execution_status = _cast_enum("NOT_APPLICABLE", PG_EXEC_STATUS_TYPE)
    approval.final_decided_by = user_ctx.user_id
    approval.final_decided_at = datetime.now(timezone.utc)
    approval.locked_by_viewer_id = None
    approval.locked_at = None
    approval.version_no += 1

    history = ApprovalHistory(
        approval_id=approval.approval_id,
        tier=_cast_enum(old_tier, PG_TIER_TYPE),
        actor_user_id=user_ctx.user_id,
        action="REJECT",
        recommendation_or_reason=req.rejection_reason,
    )
    try:
        db.add(history)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        actor_user_id=user_ctx.user_id,
        action_code="TK-3.3",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        old_values={"status": old_status},
        new_values={"status": "REJECTED", "reason": req.rejection_reason},
    )
    return approval


def request_more_info(
    db: Session,
    user_ctx: UserContext,
    approval_id: uuid.UUID,
    req: RequestInfoDecisionRequest,
) -> ApprovalRequest:
    """Trả hồ sơ về cho người lập bổ sung thông tin hoặc yêu cầu đếm lại."""
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=user_ctx.warehouse_id,
        for_update=True,
    )
    if not approval:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy hồ sơ phê duyệt.",
            http_status=404,
        )

    if approval.version_no != req.version_no:
        raise BusinessError(
            code="VERSION_CONFLICT",
            message="Hồ sơ phê duyệt đã được người khác cập nhật.",
            http_status=409,
            details={"current_version_no": approval.version_no},
        )

    old_status = str(approval.status)
    old_tier = str(approval.current_tier)

    if old_status not in ("PENDING_D1", "PENDING_D2", "PENDING_D3", "EXPIRED"):
        raise BusinessError(
            code="INVALID_STATE",
            message=f"Hồ sơ đang ở trạng thái {old_status}, không thể yêu cầu bổ sung.",
            http_status=409,
        )

    _check_tier_permission(user_ctx, old_tier)

    approval.status = _cast_enum("NEED_INFO", PG_STATUS_TYPE)
    approval.locked_by_viewer_id = None
    approval.locked_at = None
    approval.version_no += 1

    action = "REQUEST_RECOUNT" if req.request_recount else "RETURN_FOR_INFO"
    history = ApprovalHistory(
        approval_id=approval.approval_id,
        tier=_cast_enum(old_tier, PG_TIER_TYPE),
        actor_user_id=user_ctx.user_id,
        action=action,
        recommendation_or_reason=req.info_required_note,
    )
    try:
        db.add(history)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        actor_user_id=user_ctx.user_id,
        action_code="TK-3.4",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        old_values={"status": old_status},
        new_values={"status": "NEED_INFO", "action": action, "note": req.info_required_note},
    )
    return approval


def escalate_expired_requests(db: Session, user_ctx: UserContext) -> int:
    """Kích hoạt quét và tự động leo thang SLA hồ sơ quá hạn (gọi fn_escalate_expired_approvals)."""
    if user_ctx.role_code != "quanly":
        raise BusinessError(
            code="FORBIDDEN",
            message="Chỉ Quản lý kho mới có quyền kích hoạt leo thang SLA thủ công.",
            http_status=403,
        )

    try:
        count = repo.escalate_expired_approvals_db(db)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        actor_user_id=user_ctx.user_id,
        action_code="QL-5.3",
        entity_name="approval_requests",
        entity_id=None,
        new_values={"escalated_count": count},
    )
    return count
