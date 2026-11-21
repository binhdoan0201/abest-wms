"""ABEST WMS - Routers cho Phân hệ Xuất kho (Outbound).

Khai báo toàn bộ endpoint theo Mục 4.6 Chuẩn API:
Mọi endpoint trả về HTTP 501 Not Implemented kèm kiểm tra quyền RBAC.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.modules.outbound.schemas import (
    AllocateOrderRequest,
    ConfirmGoodsIssueRequest,
    ConfirmPickLineRequest,
    CreateGoodsIssueRequest,
    CreatePackageRequest,
    CreatePickSessionRequest,
    DecideOrderChangeRequest,
    PickLineExceptionRequest,
)

router = APIRouter(tags=["Outbound"])


@router.get("/outbound-orders", summary="Xem danh sách đơn xuất kho")
def get_outbound_orders(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /outbound-orders đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )


@router.get("/outbound-orders/{order_id}", summary="Xem chi tiết đơn xuất kho")
def get_outbound_order_by_id(
    order_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /outbound-orders/{id} đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )


@router.post("/outbound-orders/{order_id}/allocate", summary="Cấp phát tồn kho FEFO/FIFO cho đơn")
def allocate_outbound_order(
    order_id: uuid.UUID,
    req: AllocateOrderRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /outbound-orders/{id}/allocate đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )


@router.post("/pick-sessions", summary="Tạo phiên lấy hàng từ một hoặc nhiều đơn")
def create_pick_session(
    req: CreatePickSessionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /pick-sessions đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )


@router.get("/pick-sessions/{session_id}", summary="Xem chi tiết phiên lấy hàng và các dòng pick")
def get_pick_session_by_id(
    session_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /pick-sessions/{id} đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )


@router.post(
    "/pick-sessions/{session_id}/lines/{line_id}/confirm",
    summary="Xác nhận lấy hàng một dòng pick",
)
def confirm_pick_line(
    session_id: uuid.UUID,
    line_id: uuid.UUID,
    req: ConfirmPickLineRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /pick-sessions/{id}/lines/{line_id}/confirm đang phát triển",
        http_status=501,
    )


@router.post(
    "/pick-sessions/{session_id}/lines/{line_id}/exception",
    summary="Báo cáo ngoại lệ thiếu, hư, sai lô",
)
def report_pick_line_exception(
    session_id: uuid.UUID,
    line_id: uuid.UUID,
    req: PickLineExceptionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /pick-sessions/{id}/lines/{line_id}/exception đang phát triển",
        http_status=501,
    )


@router.post(
    "/outbound-orders/{order_id}/packages", summary="Đóng gói: tạo kiện và danh sách dòng kiện"
)
def create_order_package(
    order_id: uuid.UUID,
    req: CreatePackageRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("DG-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /outbound-orders/{id}/packages đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )


@router.post("/goods-issues", summary="Lập phiếu xuất kho GI, gán xe và tài xế")
def create_goods_issue(
    req: CreateGoodsIssueRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("DG-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /goods-issues đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )


@router.post("/goods-issues/{gi_id}/confirm", summary="Xác nhận giao hàng, đơn SHIPPED, trừ tồn")
def confirm_goods_issue(
    gi_id: uuid.UUID,
    req: ConfirmGoodsIssueRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("DG-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /goods-issues/{id}/confirm đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )


@router.post(
    "/order-changes/{request_id}/decide",
    summary="Quản lý chốt yêu cầu đổi/hủy đơn từ ERP (ACCEPT/REJECT)",
)
def decide_order_change(
    request_id: uuid.UUID,
    req: DecideOrderChangeRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-5.3")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /order-changes/{id}/decide đang phát triển (TODO: Chủ module C)",
        http_status=501,
    )
