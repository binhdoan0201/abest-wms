"""ABEST WMS - Nghiệp vụ Phân hệ Phê duyệt (Approvals)."""

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
from server.app.core.security import verify_password
from server.app.modules.approvals import repositories as repo
from server.app.modules.approvals.models import (
    ApprovalHistory,
    ApprovalRequest,
    StockAdjustment,
)
from server.app.modules.approvals.schemas import (
    ApproveDecisionRequest,
    EscalateTierRequest,
    RejectDecisionRequest,
    RequestInfoDecisionRequest,
    StockAdjustmentProposalCreate,
)
from server.app.modules.inventory import apply_movement

PG_OBJECT_TYPE = PG_ENUM(name="approval_object_type", create_type=False)
PG_TIER_TYPE = PG_ENUM(name="approval_tier_type", create_type=False)
PG_STATUS_TYPE = PG_ENUM(name="approval_status_type", create_type=False)
PG_EXEC_STATUS_TYPE = PG_ENUM(name="post_approval_exec_status", create_type=False)

LOCK_TIMEOUT_MINUTES = 15

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
    return cast(value, pg_enum)


def _require_warehouse_id(user_ctx: UserContext) -> uuid.UUID:
    if user_ctx.warehouse_id is None:
        raise BusinessError(
            code="FORBIDDEN",
            message="Tài khoản hiện tại chưa được gán kho làm việc.",
            http_status=403,
        )
    return user_ctx.warehouse_id


def _compute_sla_due(config: dict[str, Any] | None, tier: str) -> datetime:
    default_hours = {"D1_THUKHO": 4, "D2_QUANLY": 8, "D3_BGD": 24}
    tier_short = tier.split("_")[0]
    sla_map = (config or {}).get("approval_sla_hours") or {}
    hours = float(sla_map.get(tier_short, default_hours.get(tier, 8)))
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _is_lock_active(approval: ApprovalRequest, now: datetime) -> bool:
    if approval.locked_by_viewer_id is None or approval.locked_at is None:
        return False
    locked_at = approval.locked_at
    if locked_at.tzinfo is None:
        locked_at = locked_at.replace(tzinfo=timezone.utc)
    return (now - locked_at) < timedelta(minutes=LOCK_TIMEOUT_MINUTES)


def _ensure_not_locked_by_other(approval: ApprovalRequest, user_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    if (
        _is_lock_active(approval, now)
        and approval.locked_by_viewer_id is not None
        and approval.locked_by_viewer_id != user_id
    ):
        raise BusinessError(
            code="APPROVAL_LOCKED_BY_OTHER",
            message="Hồ sơ đang được cán bộ duyệt khác mở xử lý.",
            http_status=409,
        )


def _check_tier_permission(user_ctx: UserContext, current_tier: str) -> None:
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
    if proposer_user_id == actor_user_id:
        raise BusinessError(
            code="SOD_VIOLATION",
            message="Người lập đề xuất không được phép tự phê duyệt/từ chối hồ sơ của chính mình.",
            http_status=403,
        )


def _verify_reauth(
    db: Session,
    user_ctx: UserContext,
    discrepancy_amount: Decimal,
    reauth_min: Decimal,
    reauth_method: str | None,
    reauth_password: str | None,
) -> None:
    if discrepancy_amount < reauth_min:
        return

    if not reauth_method or not reauth_password:
        raise BusinessError(
            code="REAUTH_REQUIRED",
            message=(
                "Hồ sơ có giá trị vượt ngưỡng xác thực lại, bắt buộc cung cấp "
                "reauth_method và reauth_password."
            ),
            http_status=403,
        )

    password_hash = repo.get_user_password_hash(db, user_ctx.user_id)
    if not password_hash or not verify_password(reauth_password, password_hash):
        raise BusinessError(
            code="REAUTH_FAILED",
            message="Mật khẩu xác thực lại không chính xác.",
            http_status=403,
        )


def _execute_post_approval(
    db: Session,
    approval: ApprovalRequest,
    actor_user_id: uuid.UUID,
) -> None:
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
    warehouse_id = _require_warehouse_id(user_ctx)
    if user_ctx.role_code != "thukho":
        raise BusinessError(
            code="FORBIDDEN",
            message="Chỉ Thủ kho mới có quyền đề xuất điều chỉnh tồn hoặc hủy hàng.",
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
        warehouse_id=warehouse_id,
        adjustment_type=req.adjustment_type,
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
        warehouse_id=warehouse_id,
        object_type=object_type,
        object_id=adj.adjustment_id,
        proposer_user_id=user_ctx.user_id,
        discrepancy_amount=total_value,
        force_review=True,
    )
    assert approval is not None
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
    warehouse_id = _require_warehouse_id(user_ctx)
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
        warehouse_id=warehouse_id,
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
    warehouse_id = _require_warehouse_id(user_ctx)
    if user_ctx.role_code not in ROLE_TO_TIER:
        raise BusinessError(
            code="FORBIDDEN",
            message="Vai trò hiện tại không có quyền xem chi tiết hồ sơ phê duyệt.",
            http_status=403,
        )

    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=warehouse_id,
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
        "EXPIRED",
    ):
        _check_tier_permission(user_ctx, str(approval.current_tier))
        _ensure_not_locked_by_other(approval, user_ctx.user_id)

        approval.locked_by_viewer_id = user_ctx.user_id
        approval.locked_at = datetime.now(timezone.utc)
        db.flush()

    histories = repo.list_histories_by_approval(db, approval_id)
    return approval, histories


def unlock_approval(
    db: Session,
    user_ctx: UserContext,
    approval_id: uuid.UUID,
) -> ApprovalRequest:
    warehouse_id = _require_warehouse_id(user_ctx)
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=warehouse_id,
        for_update=True,
    )
    if not approval:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy hồ sơ phê duyệt.",
            http_status=404,
        )

    if approval.locked_by_viewer_id is not None:
        now = datetime.now(timezone.utc)
        if approval.locked_by_viewer_id != user_ctx.user_id and _is_lock_active(approval, now):
            raise BusinessError(
                code="APPROVAL_LOCKED_BY_OTHER",
                message="Hồ sơ đang được cán bộ duyệt khác khóa xử lý.",
                http_status=409,
            )
        approval.locked_by_viewer_id = None
        approval.locked_at = None
        db.flush()

    return approval


def approve_request(
    db: Session,
    user_ctx: UserContext,
    approval_id: uuid.UUID,
    req: ApproveDecisionRequest,
) -> ApprovalRequest:
    warehouse_id = _require_warehouse_id(user_ctx)
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=warehouse_id,
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
    _ensure_not_locked_by_other(approval, user_ctx.user_id)

    config = repo.get_warehouse_approval_config(db, warehouse_id)
    reauth_min = Decimal(str((config or {}).get("reauth_min_amount", "10000000.00")))
    _verify_reauth(
        db=db,
        user_ctx=user_ctx,
        discrepancy_amount=approval.discrepancy_value_amount,
        reauth_min=reauth_min,
        reauth_method=req.reauth_method,
        reauth_password=req.reauth_password,
    )

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
        action="APPROVE",
        recommendation_or_reason=req.recommendation_or_reason,
        reauth_method=req.reauth_method,
    )
    try:
        db.add(history)
        db.flush()
        _execute_post_approval(db=db, approval=approval, actor_user_id=user_ctx.user_id)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=warehouse_id,
        actor_user_id=user_ctx.user_id,
        action_code="TK-3.2" if old_tier == "D1_THUKHO" else "QL-7.2",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        old_values={"status": old_status, "tier": old_tier},
        new_values={
            "status": "APPROVED",
            "tier": old_tier,
            "action": "APPROVE",
        },
        reauth_verified=bool(req.reauth_method),
    )
    return approval


def escalate_to_next_tier(
    db: Session,
    user_ctx: UserContext,
    approval_id: uuid.UUID,
    req: EscalateTierRequest,
) -> ApprovalRequest:
    warehouse_id = _require_warehouse_id(user_ctx)
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=warehouse_id,
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

    if old_tier != "D1_THUKHO" or old_status not in ("PENDING_D1", "EXPIRED"):
        raise BusinessError(
            code="INVALID_STATE",
            message="Chỉ hồ sơ đang chờ ở cấp D1_THUKHO mới được chuyển tiếp lên D2_QUANLY.",
            http_status=409,
        )

    _check_sod(approval.proposer_user_id, user_ctx.user_id)
    _check_tier_permission(user_ctx, old_tier)
    _ensure_not_locked_by_other(approval, user_ctx.user_id)

    config = repo.get_warehouse_approval_config(db, warehouse_id)
    approval.current_tier = _cast_enum("D2_QUANLY", PG_TIER_TYPE)
    approval.status = _cast_enum("PENDING_D2", PG_STATUS_TYPE)
    approval.sla_due_at = _compute_sla_due(config, "D2_QUANLY")
    approval.locked_by_viewer_id = None
    approval.locked_at = None
    approval.version_no += 1

    history = ApprovalHistory(
        approval_id=approval.approval_id,
        tier=_cast_enum(old_tier, PG_TIER_TYPE),
        actor_user_id=user_ctx.user_id,
        action="ESCALATE_NEXT_TIER",
        recommendation_or_reason=req.recommendation_or_reason,
    )
    try:
        db.add(history)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=warehouse_id,
        actor_user_id=user_ctx.user_id,
        action_code="TK-3.2",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        old_values={"status": old_status, "tier": old_tier},
        new_values={
            "status": "PENDING_D2",
            "tier": "D2_QUANLY",
            "action": "ESCALATE_NEXT_TIER",
        },
    )
    return approval


def reject_request(
    db: Session,
    user_ctx: UserContext,
    approval_id: uuid.UUID,
    req: RejectDecisionRequest,
) -> ApprovalRequest:
    warehouse_id = _require_warehouse_id(user_ctx)
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=warehouse_id,
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
    _ensure_not_locked_by_other(approval, user_ctx.user_id)

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
        warehouse_id=warehouse_id,
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
    warehouse_id = _require_warehouse_id(user_ctx)
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=warehouse_id,
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
    _ensure_not_locked_by_other(approval, user_ctx.user_id)

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
        warehouse_id=warehouse_id,
        actor_user_id=user_ctx.user_id,
        action_code="TK-3.4",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        old_values={"status": old_status},
        new_values={"status": "NEED_INFO", "action": action, "note": req.info_required_note},
    )
    return approval


def resubmit_approval_info(
    db: Session,
    approval_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    note: str,
    new_discrepancy_amount: Decimal | None = None,
    new_discrepancy_percent: Decimal = Decimal("0"),
) -> ApprovalRequest:
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=warehouse_id,
        for_update=True,
    )
    if not approval:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy hồ sơ phê duyệt cần bổ sung.",
            http_status=404,
        )

    if str(approval.status) != "NEED_INFO":
        raise BusinessError(
            code="INVALID_STATE",
            message=f"Hồ sơ đang ở trạng thái {approval.status}, không thể gửi bổ sung.",
            http_status=409,
        )

    target_tier = str(approval.current_tier)
    if new_discrepancy_amount is not None:
        resolved_tier = repo.resolve_approval_tier_db(
            db=db,
            warehouse_id=warehouse_id,
            object_type=str(approval.object_type),
            amount=new_discrepancy_amount,
            percent=new_discrepancy_percent,
            proposer_id=approval.proposer_user_id,
            force_review=True,
        )
        target_tier = resolved_tier
        approval.discrepancy_value_amount = abs(new_discrepancy_amount)
        approval.current_tier = _cast_enum(target_tier, PG_TIER_TYPE)

    config = repo.get_warehouse_approval_config(db, warehouse_id)
    new_status = TIER_TO_PENDING_STATUS[target_tier]
    approval.status = _cast_enum(new_status, PG_STATUS_TYPE)
    approval.sla_due_at = _compute_sla_due(config, target_tier)
    approval.version_no += 1

    history = ApprovalHistory(
        approval_id=approval.approval_id,
        tier=_cast_enum(target_tier, PG_TIER_TYPE),
        actor_user_id=actor_user_id,
        action="RESUBMIT_INFO",
        recommendation_or_reason=note,
    )
    try:
        db.add(history)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=warehouse_id,
        actor_user_id=actor_user_id,
        action_code="APPROVAL_RESUBMIT",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        old_values={"status": "NEED_INFO"},
        new_values={"status": new_status, "tier": target_tier, "note": note},
    )
    return approval


def supersede_approval_for_recount(
    db: Session,
    approval_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    note: str = "Đóng hồ sơ cũ để đếm lại theo yêu cầu người duyệt",
) -> ApprovalRequest:
    approval = repo.get_approval_by_id(
        db=db,
        approval_id=approval_id,
        warehouse_id=warehouse_id,
        for_update=True,
    )
    if not approval:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy hồ sơ phê duyệt cần thay thế.",
            http_status=404,
        )

    if str(approval.status) != "NEED_INFO":
        raise BusinessError(
            code="INVALID_STATE",
            message=f"Hồ sơ đang ở trạng thái {approval.status}, không thể chuyển SUPERSEDED.",
            http_status=409,
        )

    current_tier = str(approval.current_tier)
    approval.status = _cast_enum("SUPERSEDED", PG_STATUS_TYPE)
    approval.execution_status = _cast_enum("NOT_APPLICABLE", PG_EXEC_STATUS_TYPE)
    approval.locked_by_viewer_id = None
    approval.locked_at = None
    approval.version_no += 1

    history = ApprovalHistory(
        approval_id=approval.approval_id,
        tier=_cast_enum(current_tier, PG_TIER_TYPE),
        actor_user_id=actor_user_id,
        action="SUPERSEDED_BY_RECOUNT",
        recommendation_or_reason=note,
    )
    try:
        db.add(history)
        db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise translate_db_error(exc) from exc

    create_audit_log(
        db=db,
        warehouse_id=warehouse_id,
        actor_user_id=actor_user_id,
        action_code="APPROVAL_SUPERSEDED",
        entity_name="approval_requests",
        entity_id=approval.approval_id,
        old_values={"status": "NEED_INFO"},
        new_values={"status": "SUPERSEDED", "note": note},
    )
    return approval


def escalate_expired_requests(db: Session, user_ctx: UserContext) -> int:
    warehouse_id = _require_warehouse_id(user_ctx)
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
        warehouse_id=warehouse_id,
        actor_user_id=user_ctx.user_id,
        action_code="QL-5.3",
        entity_name="approval_requests",
        entity_id=None,
        new_values={"escalated_count": count},
    )
    return count
