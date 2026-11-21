"""ABEST WMS - Routers cho Phân hệ Nhập kho (Inbound).

Khai báo toàn bộ endpoint theo Mục 4.5 Chuẩn API:
Mọi endpoint trả về HTTP 501 Not Implemented kèm kiểm tra quyền RBAC.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.modules.inbound.schemas import (
    CreateGrnRequest,
    GrnLineCountRequest,
    PutawayConfirmRequest,
    PutawaySuggestRequest,
)

router = APIRouter(tags=["Inbound"])


@router.get("/purchase-orders", summary="Xem danh sách đơn mua hàng (PO)")
def get_purchase_orders(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /purchase-orders đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.get("/purchase-orders/{po_id}", summary="Xem chi tiết đơn mua hàng (PO)")
def get_purchase_order_by_id(
    po_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /purchase-orders/{id} đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.get("/asns", summary="Xem danh sách thông báo giao hàng trước (ASN)")
def get_asns(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /asns đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.post("/grns", summary="Tạo phiếu nhập kho GRN từ PO hoặc ASN")
def create_grn(
    req: CreateGrnRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /grns đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.get("/grns", summary="Xem danh sách phiếu nhập kho GRN")
def get_grns(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /grns đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.get("/grns/{grn_id}", summary="Xem chi tiết phiếu nhập kho GRN (ẩn tồn nếu đếm mù)")
def get_grn_by_id(
    grn_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /grns/{id} đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.post("/grns/{grn_id}/lines", summary="Ghi một dòng đếm cho GRN")
def add_grn_line(
    grn_id: uuid.UUID,
    req: GrnLineCountRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /grns/{id}/lines đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.post("/grns/{grn_id}/submit", summary="Chốt đếm và gọi giải quyết tầng duyệt")
def submit_grn(
    grn_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /grns/{id}/submit đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.post("/grns/{grn_id}/recount", summary="Yêu cầu kiểm đếm lại khi có chênh lệch")
def recount_grn(
    grn_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /grns/{id}/recount đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.post("/grns/{grn_id}/complete", summary="Hoàn tất phiếu nhập: tạo pallet và task cất hàng")
def complete_grn(
    grn_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("NH-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /grns/{id}/complete đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.post("/putaway/suggest", summary="Gợi ý vị trí cất cho pallet")
def suggest_putaway_location(
    req: PutawaySuggestRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("CAT-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /putaway/suggest đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )


@router.post("/pallets/{pallet_id}/putaway", summary="Xác nhận cất pallet vào vị trí đích")
def confirm_pallet_putaway(
    pallet_id: uuid.UUID,
    req: PutawayConfirmRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("CAT-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /pallets/{id}/putaway đang phát triển (TODO: Chủ module B)",
        http_status=501,
    )
