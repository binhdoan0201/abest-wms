"""ABEST WMS - Routers cho Phân hệ Xuất kho (Outbound).

Triển khai đầy đủ 11 endpoint theo Mục 4.6 Chuẩn API.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from server.app.core.database import DbSession, get_db
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.core.responses import success_response
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
from server.app.modules.outbound.services import OutboundService

router = APIRouter(tags=["Outbound"])


@router.get("/outbound-orders", summary="Xem danh sách đơn xuất kho")
def get_outbound_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("QL-2.1", "DG-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    items, total = OutboundService.list_orders(
        db=db,
        access_type=access_type,
        user_ctx=user_ctx,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return success_response(data=items, page=page, page_size=page_size, total=total)


@router.get("/outbound-orders/{order_id}", summary="Xem chi tiết đơn xuất kho")
def get_outbound_order_by_id(
    order_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("QL-2.1", "DG-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.get_order_detail(db=db, user_ctx=user_ctx, order_id=order_id)
    return success_response(data=data)


@router.post("/outbound-orders/{order_id}/allocate", summary="Cấp phát tồn kho FEFO/FIFO")
def allocate_outbound_order(
    order_id: uuid.UUID,
    req: AllocateOrderRequest | None = None,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    payload = req or AllocateOrderRequest()
    data = OutboundService.allocate_order(
        db=db,
        access_type=access_type,
        user_ctx=user_ctx,
        order_id=order_id,
        req=payload,
    )
    return success_response(data=data)


@router.post(
    "/pick-sessions",
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiên soạn hàng từ một hoặc nhiều đơn",
)
def create_pick_session(
    req: CreatePickSessionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.create_pick_session(
        db=db, user_ctx=user_ctx, req=req, access_type=access_type
    )
    return success_response(data=data)


@router.get("/pick-sessions/{pick_session_id}", summary="Xem chi tiết phiên soạn hàng")
def get_pick_session_by_id(
    pick_session_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.get_pick_session_detail(
        db=db,
        access_type=access_type,
        user_ctx=user_ctx,
        pick_session_id=pick_session_id,
    )
    return success_response(data=data)


@router.post(
    "/pick-sessions/{pick_session_id}/lines/{pick_line_id}/confirm",
    summary="Xác nhận soạn một dòng hàng",
)
def confirm_pick_line(
    pick_session_id: uuid.UUID,
    pick_line_id: uuid.UUID,
    req: ConfirmPickLineRequest,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.confirm_pick_line(
        db=db,
        access_type=access_type,
        user_ctx=user_ctx,
        pick_session_id=pick_session_id,
        pick_line_id=pick_line_id,
        req=req,
    )
    return success_response(data=data)


@router.post(
    "/pick-sessions/{pick_session_id}/lines/{pick_line_id}/exception",
    summary="Báo cáo ngoại lệ khi lấy hàng (thiếu, hư, sai lô)",
)
def report_pick_line_exception(
    pick_session_id: uuid.UUID,
    pick_line_id: uuid.UUID,
    req: PickLineExceptionRequest,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("SO-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.report_pick_line_exception(
        db=db,
        access_type=access_type,
        user_ctx=user_ctx,
        pick_session_id=pick_session_id,
        pick_line_id=pick_line_id,
        req=req,
    )
    return success_response(data=data)


@router.post(
    "/outbound-orders/{order_id}/packages",
    status_code=status.HTTP_201_CREATED,
    summary="Đóng gói: tạo kiện hàng và dòng kiện",
)
def create_package(
    order_id: uuid.UUID,
    req: CreatePackageRequest,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("DG-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.create_package(
        db=db,
        access_type=access_type,
        user_ctx=user_ctx,
        order_id=order_id,
        req=req,
    )
    return success_response(data=data)


@router.post(
    "/goods-issues",
    status_code=status.HTTP_201_CREATED,
    summary="Lập phiếu xuất kho GI và gán phương tiện",
)
def create_goods_issue(
    req: CreateGoodsIssueRequest,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("DG-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.create_goods_issue(
        db=db, user_ctx=user_ctx, req=req, access_type=access_type
    )
    return success_response(data=data)


@router.post(
    "/goods-issues/{gi_id}/confirm",
    summary="Xác nhận giao hàng, đơn SHIPPED và trừ tồn kho",
)
def confirm_goods_issue(
    gi_id: uuid.UUID,
    req: ConfirmGoodsIssueRequest,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("DG-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.confirm_goods_issue(
        db=db,
        access_type=access_type,
        user_ctx=user_ctx,
        gi_id=gi_id,
        req=req,
    )
    return success_response(data=data)


@router.post(
    "/order-changes/{request_id}/decide",
    summary="Quản lý chốt yêu cầu đổi/hủy đơn từ ERP",
)
def decide_order_change(
    request_id: uuid.UUID,
    req: DecideOrderChangeRequest,
    user_ctx: UserContext = Depends(get_current_user),
    access_type: str = Depends(require_permission("QL-5.3")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    data = OutboundService.decide_order_change(
        db=db,
        access_type=access_type,
        user_ctx=user_ctx,
        request_id=request_id,
        req=req,
    )
    return success_response(data=data)
