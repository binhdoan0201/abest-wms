"""ABEST WMS - Routers cho Phân hệ Tổng quan (Dashboard).

Khai báo toàn bộ endpoint theo Mục 4.10 Chuẩn API:
Mọi endpoint trả về HTTP 501 Not Implemented kèm kiểm tra quyền RBAC.
"""

from typing import Any

from fastapi import APIRouter, Depends

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/tasks", summary="Số liệu tổng quan nhiệm vụ kho")
def get_dashboard_tasks(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-8.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /dashboard/tasks đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.get("/inventory", summary="Số liệu tổng quan tồn kho")
def get_dashboard_inventory(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-8.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /dashboard/inventory đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.get("/orders", summary="Số liệu tổng quan đơn nhập/xuất")
def get_dashboard_orders(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-8.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /dashboard/orders đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )
