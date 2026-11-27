"""ABEST WMS - Routers cho Phân hệ Kiểm kê (Cycle Count)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, status

from server.app.core.database import DbSession, get_db
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.core.responses import success_response
from server.app.modules.cycle_count.schemas import (
    CreateCycleCountRequest,
    RecordCountRequest,
)
from server.app.modules.cycle_count.services import CycleCountService

router = APIRouter(prefix="/cycle-counts", tags=["Cycle Count"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiếu kiểm kê, khóa các vị trí kiểm kê",
)
def create_cycle_count(
    req: CreateCycleCountRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-1.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=CycleCountService.create_sheet(db, user_ctx, req))


@router.get("", summary="Xem danh sách phiếu kiểm kê")
def get_cycle_counts(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("KK-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    items, total, page, page_size = CycleCountService.list_sheets(
        db, user_ctx, status, page, page_size
    )
    return success_response(data=items, page=page, page_size=page_size, total=total)


@router.get("/{count_sheet_id}", summary="Xem chi tiết phiếu kiểm kê (đếm mù thì ẩn tồn hệ thống)")
def get_cycle_count_by_id(
    count_sheet_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("KK-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=CycleCountService.get_sheet_detail(db, user_ctx, count_sheet_id))


@router.post("/{count_sheet_id}/lines/{line_id}/count", summary="Ghi nhận số lượng đếm mù")
def record_line_count(
    count_sheet_id: uuid.UUID,
    line_id: uuid.UUID,
    req: RecordCountRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("KK-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(
        data=CycleCountService.record_count(
            db, user_ctx, count_sheet_id, line_id, req, is_recount=False
        )
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
    return success_response(
        data=CycleCountService.record_count(
            db, user_ctx, count_sheet_id, line_id, req, is_recount=True
        )
    )


@router.post("/{count_sheet_id}/close", summary="Đóng phiếu kiểm kê và mở khóa vị trí")
def close_cycle_count(
    count_sheet_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("TK-1.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=CycleCountService.close_sheet(db, user_ctx, count_sheet_id))
