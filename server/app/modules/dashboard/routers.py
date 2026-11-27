"""ABEST WMS - Routers cho Phân hệ Tổng quan (Dashboard).

Chuẩn API mục 4.10: ba endpoint chỉ đọc cho `thukho`, `quanly`, `bgd` (quyền QL-8.1).
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from server.app.core.database import DbSession, get_db
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.core.responses import success_response
from server.app.modules.dashboard.services import DEFAULT_NEAR_EXPIRY_DAYS, DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

WarehouseQuery = Query(None, description="Chỉ dùng cho người dùng không gắn kho")


@router.get("/tasks", summary="Thẻ số task, task quá hạn và cảnh báo (TK-2.1)")
def get_dashboard_tasks(
    warehouse_id: uuid.UUID | None = WarehouseQuery,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-8.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = DashboardService.get_tasks(db, user_ctx, warehouse_id)
    return success_response(data=data.model_dump(mode="json"))


@router.get("/inventory", summary="Tổng quan tồn kho, vị trí, hạn dùng và cảnh báo")
def get_dashboard_inventory(
    warehouse_id: uuid.UUID | None = WarehouseQuery,
    near_expiry_days: int = Query(DEFAULT_NEAR_EXPIRY_DAYS, ge=1, le=365),
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-8.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = DashboardService.get_inventory(db, user_ctx, warehouse_id, near_expiry_days)
    return success_response(data=data.model_dump(mode="json"))


@router.get("/orders", summary="Đơn nhập, xuất trong ngày, hồ sơ chờ duyệt và cảnh báo")
def get_dashboard_orders(
    warehouse_id: uuid.UUID | None = WarehouseQuery,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-8.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = DashboardService.get_orders(db, user_ctx, warehouse_id)
    return success_response(data=data.model_dump(mode="json"))
