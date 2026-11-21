"""ABEST WMS - Routers cho Phân hệ Tích hợp (Integrations).

Khai báo toàn bộ endpoint theo Mục 4.4 Chuẩn API:
Mọi endpoint trả về HTTP 501 Not Implemented kèm kiểm tra quyền RBAC.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.modules.integrations.schemas import (
    ErpAsnRequest,
    ErpOrderChangeRequest,
    ErpOutboundOrderRequest,
    ErpPurchaseOrderRequest,
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.post("/erp/purchase-orders", summary="ERP mock đẩy đơn mua hàng (PO)")
def mock_erp_push_purchase_order(
    req: ErpPurchaseOrderRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("AD-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message=(
            "Endpoint POST /integrations/erp/purchase-orders đang phát triển "
            "(TODO: Chủ module A)"
        ),
        http_status=501,
    )


@router.post("/erp/asns", summary="ERP mock đẩy thông báo giao hàng (ASN)")
def mock_erp_push_asn(
    req: ErpAsnRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("AD-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint POST /integrations/erp/asns đang phát triển (TODO: Chủ module A)",
        http_status=501,
    )


@router.post("/erp/outbound-orders", summary="ERP mock đẩy đơn bán hàng (SO/Outbound Order)")
def mock_erp_push_outbound_order(
    req: ErpOutboundOrderRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("AD-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message=(
            "Endpoint POST /integrations/erp/outbound-orders đang phát triển "
            "(TODO: Chủ module A)"
        ),
        http_status=501,
    )


@router.post(
    "/erp/outbound-orders/{order_id}/changes",
    summary="ERP mock đổi hoặc hủy đơn bán hàng",
)
def mock_erp_change_outbound_order(
    order_id: uuid.UUID,
    req: ErpOrderChangeRequest,
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("AD-1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message=(
            "Endpoint POST /integrations/erp/outbound-orders/{order_id}/changes "
            "đang phát triển (TODO: Chủ module A)"
        ),
        http_status=501,
    )


@router.get("/sync-logs", summary="Xem nhật ký đồng bộ tích hợp hệ thống ngoài")
def get_sync_logs(
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("AD-1", "QL-2.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    raise BusinessError(
        code="NOT_IMPLEMENTED",
        message="Endpoint GET /integrations/sync-logs đang phát triển (TODO: Chủ module A)",
        http_status=501,
    )
