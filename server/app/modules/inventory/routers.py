"""ABEST WMS - Bộ định tuyến API (Routers) cho Phân hệ Tồn kho.

Khai báo các endpoint tra cứu theo Mục 4.3 Chuẩn API.
Không có endpoint ghi tồn công khai: mọi biến động đều đi qua service nội bộ.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.core.responses import success_response
from server.app.modules.inventory.services import InventoryService

router = APIRouter(tags=["Inventory"])


@router.get("/inventory/balances", summary="Tra cứu số dư tồn kho")
def get_balances(
    sku_id: uuid.UUID | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    lot_id: uuid.UUID | None = Query(None),
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-1.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Endpoint tra cứu tồn kho theo kho của user trong token.

    Vai trò cho phép: nv-nhan, nv-cat, nv-soan, nv-dongoi, thukho, quanly, bgd.
    Bị chặn 403: admin, nv-kiemke.
    """
    if not user_ctx.warehouse_id:
        raise BusinessError(
            code="NOT_FOUND",
            message="Tài khoản chưa được gán kho hoạt động",
            http_status=404,
        )

    balances = InventoryService.get_balances(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        sku_id=sku_id,
        location_id=location_id,
        lot_id=lot_id,
    )
    return success_response(
        data=[b.model_dump() for b in balances],
        total=len(balances),
    )


@router.get("/inventory/transactions", summary="Tra cứu sổ cái giao dịch tồn kho")
def get_transactions(
    sku_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Sổ cái giao dịch tồn kho (chỉ dành cho thukho, quanly)."""
    if user_ctx.role_code not in ("thukho", "quanly"):
        raise BusinessError(
            code="FORBIDDEN",
            message="Chỉ Thủ kho và Quản lý mới có quyền xem sổ cái tồn kho",
            http_status=403,
        )

    if not user_ctx.warehouse_id:
        raise BusinessError(code="NOT_FOUND", message="Chưa gán kho", http_status=404)

    txs = InventoryService.get_transactions(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        sku_id=sku_id,
        limit=limit,
    )
    return success_response(data=[t.model_dump() for t in txs], total=len(txs))


@router.get("/lots", summary="Danh sách lô hàng và hạn dùng")
def get_lots(
    sku_id: uuid.UUID | None = Query(None),
    user_ctx: UserContext = Depends(get_current_user),
    _perm: str = Depends(require_permission("QL-1.1")),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Danh sách lô hàng và hạn dùng: mọi vai trò xem được tồn (QL-1.1), để nhân viên biết lô nào
    sắp hết hạn. `nv-kiemke` không có QL-1.1 nên vẫn bị chặn (đếm mù), `admin` bị chặn.
    """
    lots = InventoryService.get_lots(db=db, sku_id=sku_id)
    return success_response(data=[lo.model_dump() for lo in lots], total=len(lots))


@router.get("/pallets", summary="Danh sách Pallet")
def get_pallets(
    status: str | None = None,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Danh sách Pallet trong kho (thukho, quanly, nv_cat)."""
    if user_ctx.role_code not in ("thukho", "quanly", "nv-cat", "nv_cat"):
        raise BusinessError(code="FORBIDDEN", message="Không có quyền truy cập", http_status=403)

    if not user_ctx.warehouse_id:
        raise BusinessError(code="NOT_FOUND", message="Chưa gán kho", http_status=404)

    pallets = InventoryService.get_pallets(db=db, warehouse_id=user_ctx.warehouse_id)
    if status:
        target_status = status.strip().upper()
        pallets = [p for p in pallets if str(p.status).upper() == target_status]
    return success_response(data=[p.model_dump() for p in pallets], total=len(pallets))


@router.get("/pallets/{pallet_id}", summary="Chi tiết Pallet")
def get_pallet_detail(
    pallet_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Chi tiết một Pallet (thukho, quanly, nv_cat)."""
    if user_ctx.role_code not in ("thukho", "quanly", "nv-cat", "nv_cat"):
        raise BusinessError(code="FORBIDDEN", message="Không có quyền truy cập", http_status=403)

    if not user_ctx.warehouse_id:
        raise BusinessError(code="NOT_FOUND", message="Chưa gán kho", http_status=404)

    pallet = InventoryService.get_pallet_by_id(
        db=db,
        pallet_id=pallet_id,
        warehouse_id=user_ctx.warehouse_id,
    )
    if not pallet:
        raise BusinessError(code="NOT_FOUND", message="Không tìm thấy Pallet", http_status=404)

    return success_response(data=pallet.model_dump())


@router.get("/locations/{location_id}/stock", summary="Tồn kho tại một vị trí")
def get_location_stock(
    location_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Tra cứu hàng đang có tại một vị trí (thukho, quanly)."""
    if user_ctx.role_code not in ("thukho", "quanly"):
        raise BusinessError(code="FORBIDDEN", message="Không có quyền truy cập", http_status=403)

    if not user_ctx.warehouse_id:
        raise BusinessError(code="NOT_FOUND", message="Chưa gán kho", http_status=404)

    balances = InventoryService.get_location_stock(
        db=db,
        location_id=location_id,
        warehouse_id=user_ctx.warehouse_id,
    )
    return success_response(data=[b.model_dump() for b in balances], total=len(balances))
