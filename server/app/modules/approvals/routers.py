"""ABEST WMS - API Routers cho Phân hệ Phê duyệt (Approvals)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from server.app.core.database import get_db
from server.app.core.rbac import UserContext, get_current_user
from server.app.modules.approvals import services
from server.app.modules.approvals.schemas import (
    ApprovalDetailResponse,
    ApprovalHistoryItem,
    ApprovalResponse,
    ApprovalSource,
    ApproveDecisionRequest,
    EscalateExpiredResponse,
    EscalateTierRequest,
    RejectDecisionRequest,
    RequestInfoDecisionRequest,
    StockAdjustmentProposalCreate,
)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _to_approval_response(item: Any) -> ApprovalResponse:
    return ApprovalResponse(
        approval_id=item.approval_id,
        warehouse_id=item.warehouse_id,
        object_type=str(item.object_type),
        object_id=item.object_id,
        proposer_user_id=item.proposer_user_id,
        current_tier=str(item.current_tier),
        status=str(item.status),
        execution_status=str(item.execution_status),
        discrepancy_value_amount=item.discrepancy_value_amount,
        sla_due_at=item.sla_due_at,
        locked_by_viewer_id=item.locked_by_viewer_id,
        locked_at=item.locked_at,
        final_decided_by=item.final_decided_by,
        final_decided_at=item.final_decided_at,
        version_no=item.version_no,
        created_at=item.created_at,
    )


def _to_history_response(item: Any) -> ApprovalHistoryItem:
    return ApprovalHistoryItem(
        history_id=item.history_id,
        tier=str(item.tier),
        actor_user_id=item.actor_user_id,
        action=item.action,
        recommendation_or_reason=item.recommendation_or_reason,
        reauth_method=item.reauth_method,
        created_at=item.created_at,
    )


@router.get("")
def list_approvals(
    status: str | None = Query(default=None),
    tier: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    expired: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
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
    refs = services.get_object_refs(db, items)
    data = []
    for item in items:
        resp = _to_approval_response(item)
        resp.object_ref = refs.get(item.object_id)
        data.append(resp.model_dump(mode="json"))
    return {
        "data": data,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    }


@router.get("/{approval_id}")
def get_approval_detail(
    approval_id: uuid.UUID,
    lock: bool = Query(default=True),
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    approval, histories = services.get_approval_detail(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        acquire_lock=lock,
    )
    db.commit()
    source = services.get_approval_source(db, approval)
    base = _to_approval_response(approval).model_dump()
    base["object_ref"] = services.get_object_refs(db, [approval]).get(approval.object_id)
    detail = ApprovalDetailResponse(
        **base,
        histories=[_to_history_response(h) for h in histories],
        source=ApprovalSource(**source) if source else None,
    )
    return {"data": detail.model_dump(mode="json")}


@router.post("/{approval_id}/unlock")
def unlock_approval(
    approval_id: uuid.UUID,
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    approval = services.unlock_approval(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
    )
    db.commit()
    return {"data": _to_approval_response(approval).model_dump(mode="json")}


@router.post("/stock-adjustments", status_code=201)
def propose_stock_adjustment(
    req: StockAdjustmentProposalCreate,
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    approval = services.propose_stock_adjustment(
        db=db,
        user_ctx=user_ctx,
        req=req,
    )
    db.commit()
    return {"data": _to_approval_response(approval).model_dump(mode="json")}


@router.post("/{approval_id}/approve")
def approve_request(
    approval_id: uuid.UUID,
    req: ApproveDecisionRequest,
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    approval = services.approve_request(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        req=req,
    )
    db.commit()
    return {"data": _to_approval_response(approval).model_dump(mode="json")}


@router.post("/{approval_id}/escalate")
def escalate_to_next_tier(
    approval_id: uuid.UUID,
    req: EscalateTierRequest,
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    approval = services.escalate_to_next_tier(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        req=req,
    )
    db.commit()
    return {"data": _to_approval_response(approval).model_dump(mode="json")}


@router.post("/{approval_id}/reject")
def reject_request(
    approval_id: uuid.UUID,
    req: RejectDecisionRequest,
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    approval = services.reject_request(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        req=req,
    )
    db.commit()
    return {"data": _to_approval_response(approval).model_dump(mode="json")}


@router.post("/{approval_id}/request-info")
def request_more_info(
    approval_id: uuid.UUID,
    req: RequestInfoDecisionRequest,
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    approval = services.request_more_info(
        db=db,
        user_ctx=user_ctx,
        approval_id=approval_id,
        req=req,
    )
    db.commit()
    return {"data": _to_approval_response(approval).model_dump(mode="json")}


@router.post("/escalate-expired")
def escalate_expired(
    db: Any = Depends(get_db),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    count = services.escalate_expired_requests(db=db, user_ctx=user_ctx)
    db.commit()
    res = EscalateExpiredResponse(escalated_count=count)
    return {"data": res.model_dump(mode="json")}
