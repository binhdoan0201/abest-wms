"""ABEST WMS - Routers cho Phân hệ Tích hợp (Integrations), chỉ môi trường dev.

Theo chuẩn API 4.4 và hợp đồng `docs/api/integrations.md`:
- ERP mock đẩy PO, ASN, đơn xuất và yêu cầu đổi/hủy đơn (`admin`, AD-1).
- Xem nhật ký đồng bộ (`admin`, `quanly`, `thukho`); xử lý hàng đợi, thử lại, đánh dấu đã xử lý
  (`admin`, `quanly`).
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from server.app.core.database import DbSession, get_db
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.core.responses import error_response, success_response
from server.app.modules.integrations.schemas import (
    ErpAsnPush,
    ErpOrderChangePush,
    ErpOutboundOrderPush,
    ErpPurchaseOrderPush,
    MockFailureConfig,
)
from server.app.modules.integrations.services import IngestResult, IntegrationService

router = APIRouter(prefix="/integrations", tags=["Integrations"])

ERP_PUSH_PERMISSION = "AD-1"
LOG_PERMISSIONS = ("AD-1", "QL-2.1")


def _to_response(result: IngestResult) -> JSONResponse:
    """Trả phản hồi theo kết quả; lỗi vẫn commit dòng nhật ký (không ném ngoại lệ)."""
    if result.error is not None:
        content = error_response(
            code=result.error["code"],
            message=result.error["message"],
            details=result.error.get("details"),
        )
    else:
        content = success_response(data={**result.log, **result.extra})
    return JSONResponse(status_code=result.http_status, content=content)


@router.post(
    "/erp/purchase-orders",
    summary="ERP mock đẩy đơn mua hàng (PO)",
    status_code=201,
    responses={202: {"description": "Đã nhận, chờ module inbound xử lý"}},
)
def erp_push_purchase_order(
    req: ErpPurchaseOrderPush,
    _perm: str = Depends(require_permission(ERP_PUSH_PERMISSION)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> JSONResponse:
    return _to_response(IntegrationService.ingest_from_erp(db, user_ctx, "PO", req))


@router.post(
    "/erp/asns",
    summary="ERP mock đẩy thông báo giao hàng (ASN)",
    status_code=201,
    responses={202: {"description": "Đã nhận, chờ module inbound xử lý"}},
)
def erp_push_asn(
    req: ErpAsnPush,
    _perm: str = Depends(require_permission(ERP_PUSH_PERMISSION)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> JSONResponse:
    return _to_response(IntegrationService.ingest_from_erp(db, user_ctx, "ASN", req))


@router.post(
    "/erp/outbound-orders",
    summary="ERP mock đẩy đơn xuất (SO, chuyển kho, trả NCC)",
    status_code=201,
    responses={202: {"description": "Đã nhận, chờ module outbound xử lý"}},
)
def erp_push_outbound_order(
    req: ErpOutboundOrderPush,
    _perm: str = Depends(require_permission(ERP_PUSH_PERMISSION)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> JSONResponse:
    return _to_response(IntegrationService.ingest_from_erp(db, user_ctx, "SO", req))


@router.post(
    "/erp/outbound-orders/{order_id}/changes",
    summary="ERP mock đổi hoặc hủy đơn xuất",
)
def erp_change_outbound_order(
    order_id: str,
    req: ErpOrderChangePush,
    _perm: str = Depends(require_permission(ERP_PUSH_PERMISSION)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> JSONResponse:
    return _to_response(IntegrationService.receive_order_change(db, user_ctx, order_id, req))


@router.get("/sync-logs", summary="Xem nhật ký đồng bộ tích hợp")
def get_sync_logs(
    request: Request,
    _perm: str = Depends(require_permission(*LOG_PERMISSIONS)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    items, total, page, page_size = IntegrationService.list_logs(
        db, user_ctx, dict(request.query_params)
    )
    return success_response(data=items, page=page, page_size=page_size, total=total)


@router.post("/sync-logs/process", summary="Chạy hàng đợi tích hợp (gửi, thử lại)")
def process_sync_logs(
    _perm: str = Depends(require_permission(*LOG_PERMISSIONS)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=IntegrationService.process_pending(db, user_ctx))


@router.post("/sync-logs/{sync_id}/retry", summary="Thử lại một dòng nhật ký")
def retry_sync_log(
    sync_id: str,
    _perm: str = Depends(require_permission(*LOG_PERMISSIONS)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=IntegrationService.retry_log(db, user_ctx, sync_id))


@router.post("/sync-logs/{sync_id}/resolve", summary="Đánh dấu đã xử lý tay một dòng lỗi")
def resolve_sync_log(
    sync_id: str,
    _perm: str = Depends(require_permission(*LOG_PERMISSIONS)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    return success_response(data=IntegrationService.resolve_log(db, user_ctx, sync_id))


@router.post("/mock/failures", summary="Cấu hình lỗi giả lập ERP/TMS (chỉ dev)")
def configure_mock_failures(
    req: MockFailureConfig,
    _perm: str = Depends(require_permission(ERP_PUSH_PERMISSION)),
    user_ctx: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    return success_response(data=IntegrationService.configure_mock(user_ctx, req))
