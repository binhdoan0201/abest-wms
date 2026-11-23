"""ABEST WMS - Routers cho Phân hệ Phê duyệt (Approvals).

Chỉ nhận request, kiểm quyền RBAC và ủy quyền cho services.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from server.app.core.database import DbSession, get_db
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.core.responses import success_response
from server.app.modules.approvals import services
from server.app.modules.approvals.schemas import (
    ApprovalDetailResponse,
    ApprovalHistoryItem,
    ApprovalResponse,
    ApproveDecisionRequest,
    EscalateExpiredResponse,
    RejectDecisionRequest,
    RequestInfoDecisionRequest,
    StockAdjustmentProposalCreate,
)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("", summary="Xem hàng chờ duyệt hồ sơ chênh lệch")
def get_approvals(
    status: str | None = Query(None),
    tier: str | None = Query(None),
    object_type: str | None = Query(None),
    expired: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    items, total = services.list_approvals_queue(
        db=db,
        user_ctx=user_ctx,
        status=status,
        tier=tier,
        object_type=object_type,
        expired=expired,
        page=page,
        page_size=page_size,
    )
    data = [ApprovalResponse.model_validate(item).model_dump(mode="json") for item in items]
    return success_response(
        data=data,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{approval_id}", summary="Xem chi tiết hồ sơ và lịch sử duyệt")
def get_approval_by_id(
    approval_id: uuid.UUID,
    lock: bool = Query(True, description="Khóa hồ sơ khi mở xem chi tiết"),
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    approval, histories = services.get_approval_detail(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        acquire_lock=lock,
    )
    detail = ApprovalDetailResponse.model_validate(approval)
    detail.histories = [ApprovalHistoryItem.model_validate(h) for h in histories]
    return success_response(data=detail.model_dump(mode="json"))


@router.post("/stock-adjustments", status_code=201, summary="Đề xuất điều chỉnh tồn hoặc hủy hàng")
def create_stock_adjustment_proposal(
    req: StockAdjustmentProposalCreate,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-4.3")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    approval = services.propose_stock_adjustment(db=db, user_ctx=user_ctx, req=req)
    data = ApprovalResponse.model_validate(approval).model_dump(mode="json")
    return success_response(data=data)


@router.post("/{approval_id}/approve", summary="Phê duyệt hồ sơ chênh lệch")
def approve_request(
    approval_id: uuid.UUID,
    req: ApproveDecisionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    approval = services.approve_request(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        req=req,
    )
    data = ApprovalResponse.model_validate(approval).model_dump(mode="json")
    return success_response(data=data)


@router.post("/{approval_id}/reject", summary="Từ chối hồ sơ chênh lệch kèm lý do")
def reject_request(
    approval_id: uuid.UUID,
    req: RejectDecisionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    approval = services.reject_request(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        req=req,
    )
    data = ApprovalResponse.model_validate(approval).model_dump(mode="json")
    return success_response(data=data)


@router.post("/{approval_id}/request-info", summary="Yêu cầu bổ sung thêm thông tin")
def request_info(
    approval_id: uuid.UUID,
    req: RequestInfoDecisionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    approval = services.request_more_info(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        req=req,
    )
    data = ApprovalResponse.model_validate(approval).model_dump(mode="json")
    return success_response(data=data)


@router.post("/escalate-expired", summary="Chạy tự động leo thang SLA hồ sơ quá hạn")
def escalate_expired(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-5.3")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    count = services.escalate_expired_requests(db=db, user_ctx=user_ctx)
    data = EscalateExpiredResponse(escalated_count=count).model_dump(mode="json")
    return success_response(data=data)
