"""ABEST WMS - Routers cho Phân hệ Kiểm kê (Cycle Count).

Khai báo toàn bộ endpoint theo Mục 4.9 Chuẩn API:
Mọi endpoint trả về HTTP 501 Not Implemented kèm kiểm tra quyền RBAC.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.modules.cycle_count.schemas import (
    CreateCycleCountRequest,
    RecordCountRequest,
)

router = APIRouter(prefix="/cycle-counts", tags=["Cycle Count"])


@router.post("", summary="Tạo phiếu kiểm kê, khóa các vị trí kiểm kê")
def create_cycle_count(
    req: CreateCycleCountRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-1.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /cycle-counts đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.get("", summary="Xem danh sách phiếu kiểm kê")
def get_cycle_counts(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("KK-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /cycle-counts đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.get("/{count_sheet_id}", summary="Xem chi tiết phiếu kiểm kê (đếm mù thì ẩn tồn hệ thống)")
def get_cycle_count_by_id(
    count_sheet_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("KK-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /cycle-counts/{id} đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )


@router.post("/{count_sheet_id}/lines/{line_id}/count", summary="Ghi nhận số lượng đếm mù")
def record_line_count(
    count_sheet_id: uuid.UUID,
    line_id: uuid.UUID,
    req: RecordCountRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("KK-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /cycle-counts/{id}/lines/{line_id}/count đang phát triển",
        http_status=501,
    )


@router.post(
    "/{count_sheet_id}/lines/{line_id}/recount",
    summary="Đếm lại dòng kiểm kê (bắt buộc khác người đếm lần trước)",
)
def record_line_recount(
    count_sheet_id: uuid.UUID,
    line_id: uuid.UUID,
    req: RecordCountRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("KK-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /cycle-counts/{id}/lines/{line_id}/recount đang phát triển",
        http_status=501,
    )


@router.post("/{count_sheet_id}/close", summary="Đóng phiếu kiểm kê và mở khóa vị trí")
def close_cycle_count(
    count_sheet_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-1.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /cycle-counts/{id}/close đang phát triển (TODO: Chủ module D)",
        http_status=501,
    )
