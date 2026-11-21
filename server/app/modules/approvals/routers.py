"""ABEST WMS - Routers cho Phân hệ Phê duyệt (Approvals).

Khai báo toàn bộ endpoint theo Mục 4.8 Chuẩn API:
Mọi endpoint trả về HTTP 501 Not Implemented kèm kiểm tra quyền RBAC.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.modules.approvals.schemas import (
    ApproveDecisionRequest,
    RejectDecisionRequest,
    RequestInfoDecisionRequest,
)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("", summary="Xem hàng chờ duyệt hồ sơ chênh lệch")
def get_approvals(
    status: str | None = Query(None),
    tier: str | None = Query(None),
    object_type: str | None = Query(None),
    expired: bool | None = Query(None),
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /approvals đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.get("/{approval_id}", summary="Xem chi tiết hồ sơ và lịch sử duyệt")
def get_approval_by_id(
    approval_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /approvals/{id} đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.post("/{approval_id}/approve", summary="Phê duyệt hồ sơ chênh lệch")
def approve_request(
    approval_id: uuid.UUID,
    req: ApproveDecisionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /approvals/{id}/approve đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.post("/{approval_id}/reject", summary="Từ chối hồ sơ chênh lệch kèm lý do")
def reject_request(
    approval_id: uuid.UUID,
    req: RejectDecisionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /approvals/{id}/reject đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.post("/{approval_id}/request-info", summary="Yêu cầu bổ sung thêm thông tin")
def request_info(
    approval_id: uuid.UUID,
    req: RequestInfoDecisionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-3.2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /approvals/{id}/request-info đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.post("/escalate-expired", summary="Chạy tự động leo thang SLA hồ sơ quá hạn")
def escalate_expired(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-5.3")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /approvals/escalate-expired đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )
