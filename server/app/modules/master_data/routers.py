"""ABEST WMS - Routers cho Phân hệ Dữ liệu nguồn (Master Data).

Khai báo endpoint theo Mục 4.2 Chuẩn API và hợp đồng `docs/api/master_data.md`:
- 11 danh mục (thêm `vehicles`), mỗi danh mục 5 endpoint: GET /{res}, GET /{res}/{id}, POST /{res},
  PATCH /{res}/{id}, POST /{res}/{id}/deactivate. Đọc: mọi vai trò đã đăng nhập; ghi: `AD-1`.
- Cấu hình kho: GET, PATCH /warehouses/{id}/config.
- `GET /users` (chỉ đọc): `admin` xem mọi kho; `thukho`, `quanly` (TK-1.1) xem người trong kho
  mình để giao task. Các endpoint còn lại của `users`, `roles` làm cùng A-11, hiện trả 501.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.core.responses import success_response
from server.app.modules.master_data.schemas import (
    BoxTypeCreate,
    BoxTypeUpdate,
    CustomerCreate,
    CustomerUpdate,
    ItemCategoryCreate,
    ItemCategoryUpdate,
    LocationCreate,
    LocationUpdate,
    ReasonCodeCreate,
    ReasonCodeUpdate,
    SkuBarcodeCreate,
    SkuBarcodeUpdate,
    SkuCreate,
    SkuUpdate,
    SupplierCreate,
    SupplierUpdate,
    VehicleCreate,
    VehicleUpdate,
    WarehouseConfigUpdate,
    WarehouseCreate,
    WarehouseUpdate,
    ZoneCreate,
    ZoneUpdate,
)
from server.app.modules.master_data.services import MasterDataService, list_users

router = APIRouter(tags=["Master Data"])

WRITE_PERMISSION = "AD-1"
USER_DISPATCH_PERMISSION = "TK-1.1"  # điều phối task: cần xem danh sách nhân viên để giao việc

# Tài nguyên -> (schema tạo, schema sửa)
MASTER_DATA_RESOURCES: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "warehouses": (WarehouseCreate, WarehouseUpdate),
    "zones": (ZoneCreate, ZoneUpdate),
    "locations": (LocationCreate, LocationUpdate),
    "item-categories": (ItemCategoryCreate, ItemCategoryUpdate),
    "skus": (SkuCreate, SkuUpdate),
    "sku-barcodes": (SkuBarcodeCreate, SkuBarcodeUpdate),
    "suppliers": (SupplierCreate, SupplierUpdate),
    "customers": (CustomerCreate, CustomerUpdate),
    "reason-codes": (ReasonCodeCreate, ReasonCodeUpdate),
    "box-types": (BoxTypeCreate, BoxTypeUpdate),
    "vehicles": (VehicleCreate, VehicleUpdate),
}


# Cấu hình kho khai báo trước để không bị nhầm với /warehouses/{item_id}
@router.get(
    "/warehouses/{warehouse_id}/config",
    summary="Đọc cấu hình vận hành của kho",
    operation_id="get_warehouse_config",
)
def get_warehouse_config_endpoint(
    warehouse_id: str,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Đọc cấu hình kho (vai trò thường chỉ kho của mình, admin mọi kho)."""
    return success_response(data=MasterDataService.get_config(db, user_ctx, warehouse_id))


@router.patch(
    "/warehouses/{warehouse_id}/config",
    summary="Sửa cấu hình vận hành của kho",
    operation_id="update_warehouse_config",
)
def update_warehouse_config_endpoint(
    warehouse_id: str,
    req: WarehouseConfigUpdate,
    _perm: str = Depends(require_permission(WRITE_PERMISSION)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Sửa tham số vận hành kho (admin)."""
    return success_response(data=MasterDataService.update_config(db, user_ctx, warehouse_id, req))


def _register_crud_routes(
    res_name: str, create_schema: type[BaseModel], update_schema: type[BaseModel]
) -> None:
    """Tạo bộ 5 endpoint chuẩn cho một danh mục."""
    op = res_name.replace("-", "_")

    @router.get(f"/{res_name}", summary=f"Danh sách {res_name}", operation_id=f"list_{op}")
    def list_items(
        request: Request,
        user_ctx: UserContext = Depends(get_current_user),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        params = dict(request.query_params)
        items, total, page, page_size = MasterDataService.list_items(db, user_ctx, res_name, params)
        return success_response(data=items, page=page, page_size=page_size, total=total)

    @router.get(
        f"/{res_name}/{{item_id}}",
        summary=f"Chi tiết {res_name}",
        operation_id=f"get_{op}_by_id",
    )
    def get_item(
        item_id: str,
        user_ctx: UserContext = Depends(get_current_user),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        return success_response(data=MasterDataService.get_item(db, user_ctx, res_name, item_id))

    @router.post(
        f"/{res_name}",
        summary=f"Tạo mới {res_name}",
        operation_id=f"create_{op}",
        status_code=status.HTTP_201_CREATED,
    )
    def create_item(
        req: create_schema,  # type: ignore[valid-type]
        _perm: str = Depends(require_permission(WRITE_PERMISSION)),
        user_ctx: UserContext = Depends(get_current_user),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        return success_response(data=MasterDataService.create_item(db, user_ctx, res_name, req))

    @router.patch(
        f"/{res_name}/{{item_id}}",
        summary=f"Cập nhật {res_name}",
        operation_id=f"update_{op}",
    )
    def update_item(
        item_id: str,
        req: update_schema,  # type: ignore[valid-type]
        _perm: str = Depends(require_permission(WRITE_PERMISSION)),
        user_ctx: UserContext = Depends(get_current_user),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        return success_response(
            data=MasterDataService.update_item(db, user_ctx, res_name, item_id, req)
        )

    @router.post(
        f"/{res_name}/{{item_id}}/deactivate",
        summary=f"Ngừng sử dụng {res_name}",
        operation_id=f"deactivate_{op}",
    )
    def deactivate_item(
        item_id: str,
        _perm: str = Depends(require_permission(WRITE_PERMISSION)),
        user_ctx: UserContext = Depends(get_current_user),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        return success_response(
            data=MasterDataService.deactivate_item(db, user_ctx, res_name, item_id)
        )


for _res_name, (_create_schema, _update_schema) in MASTER_DATA_RESOURCES.items():
    _register_crud_routes(_res_name, _create_schema, _update_schema)


def _not_implemented(path: str) -> BusinessError:
    return BusinessError(
        code="NOT_IMPLEMENTED",
        message=f"Endpoint {path} làm ở giai đoạn sau cùng màn hình Admin (A-11)",
        http_status=501,
    )


@router.get("/users", summary="Danh sách người dùng (chỉ đọc)", operation_id="list_users")
def list_users_route(
    request: Request,
    _perm: str = Depends(require_permission(WRITE_PERMISSION, USER_DISPATCH_PERMISSION)),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    items, total, page, page_size = list_users(db, user_ctx, dict(request.query_params))
    return success_response(data=items, page=page, page_size=page_size, total=total)


def _register_admin_routes(admin_res: str) -> None:
    """`users`, `roles`: giữ chỗ endpoint (yêu cầu AD-1), trả 501 đến khi làm A-11."""

    if admin_res != "users":

        @router.get(
            f"/{admin_res}", summary=f"Danh sách {admin_res}", operation_id=f"list_{admin_res}"
        )
        def list_admin_items(_perm: str = Depends(require_permission(WRITE_PERMISSION))) -> None:
            raise _not_implemented(f"GET /{admin_res}")

    @router.get(
        f"/{admin_res}/{{item_id}}",
        summary=f"Chi tiết {admin_res}",
        operation_id=f"get_{admin_res}_by_id",
    )
    def get_admin_item(
        item_id: str, _perm: str = Depends(require_permission(WRITE_PERMISSION))
    ) -> None:
        raise _not_implemented(f"GET /{admin_res}/{{id}}")

    @router.post(
        f"/{admin_res}", summary=f"Tạo mới {admin_res}", operation_id=f"create_{admin_res}"
    )
    def create_admin_item(_perm: str = Depends(require_permission(WRITE_PERMISSION))) -> None:
        raise _not_implemented(f"POST /{admin_res}")

    @router.patch(
        f"/{admin_res}/{{item_id}}",
        summary=f"Cập nhật {admin_res}",
        operation_id=f"update_{admin_res}",
    )
    def update_admin_item(
        item_id: str, _perm: str = Depends(require_permission(WRITE_PERMISSION))
    ) -> None:
        raise _not_implemented(f"PATCH /{admin_res}/{{id}}")

    @router.post(
        f"/{admin_res}/{{item_id}}/deactivate",
        summary=f"Ngừng sử dụng {admin_res}",
        operation_id=f"deactivate_{admin_res}",
    )
    def deactivate_admin_item(
        item_id: str, _perm: str = Depends(require_permission(WRITE_PERMISSION))
    ) -> None:
        raise _not_implemented(f"POST /{admin_res}/{{id}}/deactivate")


for _admin_res in ("users", "roles"):
    _register_admin_routes(_admin_res)
