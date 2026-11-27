"""ABEST WMS - Routers cho Phân hệ Nhập kho (Inbound)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, status

from server.app.core.database import DbSession, get_db
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.core.responses import success_response
from server.app.modules.inbound.schemas import (
    CompleteGrnRequest,
    CreateGrnRequest,
    GrnLineCountRequest,
    PutawayConfirmRequest,
    PutawaySuggestRequest,
    RecountGrnRequest,
    SubmitGrnRequest,
)
from server.app.modules.inbound.services import InboundService

router = APIRouter(tags=["Inbound"])


@router.get("/purchase-orders", summary="Xem danh sách đơn mua hàng (PO)")
def get_purchase_orders(
    status: str | None = None,
    supplier_id: uuid.UUID | None = None,
    sort: str = "-created_at",
    page: int = 1,
    page_size: int = 20,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    items, total, page, page_size = InboundService.list_purchase_orders(
        db, user_ctx, status, supplier_id, sort, page, page_size
    )
    return success_response(data=items, page=page, page_size=page_size, total=total)


@router.get("/purchase-orders/{po_id}", summary="Xem chi tiết đơn mua hàng (PO)")
def get_purchase_order_by_id(
    po_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.get_purchase_order(db, user_ctx, po_id))


@router.get("/asns", summary="Xem danh sách thông báo giao hàng trước (ASN)")
def get_asns(
    status: str | None = None,
    po_id: uuid.UUID | None = None,
    sort: str = "-created_at",
    page: int = 1,
    page_size: int = 20,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    items, total, page, page_size = InboundService.list_asns(
        db, user_ctx, status, po_id, sort, page, page_size
    )
    return success_response(data=items, page=page, page_size=page_size, total=total)


@router.post(
    "/grns",
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiếu nhập kho GRN từ PO hoặc ASN",
)
def create_grn(
    req: CreateGrnRequest,
    user_ctx: UserContext = Depends(get_current_user),
    perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.create_grn(db, user_ctx, perm, req))


@router.get("/grns", summary="Xem danh sách phiếu nhập kho GRN")
def get_grns(
    status: str | None = None,
    po_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    items, total, page, page_size = InboundService.list_grns(
        db, user_ctx, status, po_id, page, page_size
    )
    return success_response(data=items, page=page, page_size=page_size, total=total)


@router.get("/grns/{grn_id}", summary="Xem chi tiết phiếu nhập kho GRN (ẩn tồn nếu đếm mù)")
def get_grn_by_id(
    grn_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.get_grn_detail(db, user_ctx, grn_id))


@router.post(
    "/grns/{grn_id}/lines",
    status_code=status.HTTP_201_CREATED,
    summary="Ghi một dòng đếm cho GRN",
)
def add_grn_line(
    grn_id: uuid.UUID,
    req: GrnLineCountRequest,
    user_ctx: UserContext = Depends(get_current_user),
    perm: str = Depends(require_permission("NH-2")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.add_grn_line(db, user_ctx, perm, grn_id, req))


@router.post("/grns/{grn_id}/submit", summary="Chốt đếm và gọi giải quyết tầng duyệt")
def submit_grn(
    grn_id: uuid.UUID,
    req: SubmitGrnRequest,
    user_ctx: UserContext = Depends(get_current_user),
    perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.submit_grn(db, user_ctx, perm, grn_id, req))


@router.post("/grns/{grn_id}/recount", summary="Yêu cầu kiểm đếm lại khi có chênh lệch")
def recount_grn(
    grn_id: uuid.UUID,
    req: RecountGrnRequest,
    user_ctx: UserContext = Depends(get_current_user),
    perm: str = Depends(require_permission("NH-5")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.recount_grn(db, user_ctx, perm, grn_id, req))


@router.post("/grns/{grn_id}/complete", summary="Hoàn tất phiếu nhập: tạo pallet và task cất hàng")
def complete_grn(
    grn_id: uuid.UUID,
    req: CompleteGrnRequest,
    user_ctx: UserContext = Depends(get_current_user),
    perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.complete_grn(db, user_ctx, perm, grn_id, req))


@router.post("/putaway/suggest", summary="Gợi ý vị trí cất cho pallet")
def suggest_putaway_location(
    req: PutawaySuggestRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("CAT-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.suggest_putaway(db, user_ctx, req))


@router.post("/pallets/{pallet_id}/putaway", summary="Xác nhận cất pallet vào vị trí đích")
def confirm_pallet_putaway(
    pallet_id: uuid.UUID,
    req: PutawayConfirmRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("CAT-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=InboundService.confirm_putaway(db, user_ctx, pallet_id, req))
