"""ABEST WMS - Routers cho Phân hệ Dữ liệu nguồn (Master Data).

Khai báo toàn bộ endpoint theo Mục 4.2 Chuẩn API:
Mẫu chung cho 12 tài nguyên:
GET /{res}, GET /{res}/{id}, POST /{res}, PATCH /{res}/{id}, POST /{res}/{id}/deactivate.
Mọi endpoint trả về HTTP 501 Not Implemented kèm kiểm tra quyền RBAC.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user, require_permission
from server.app.modules.master_data.schemas import (
    CreateResourceRequest,
    UpdateResourceRequest,
)

router = APIRouter(tags=["Master Data"])

# Danh sách 10 tài nguyên danh mục dùng chung
MASTER_DATA_RESOURCES = [
    "warehouses",
    "zones",
    "locations",
    "item-categories",
    "skus",
    "sku-barcodes",
    "suppliers",
    "customers",
    "reason-codes",
    "box-types",
]


def _register_crud_routes(res_name: str, read_perm: str | None = None) -> None:
    """Tạo bộ 5 endpoint chuẩn REST cho từng tài nguyên danh mục."""

    @router.get(
        f"/{res_name}",
        summary=f"Danh sách {res_name}",
        operation_id=f"list_{res_name.replace('-', '_')}",
    )
    def list_items(
        user_ctx: UserContext = Depends(get_current_user),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint GET /{res_name} đang phát triển (TODO: Chủ module B)",
            http_status=501,
        )

    @router.get(
        f"/{res_name}/{{item_id}}",
        summary=f"Chi tiết {res_name}",
        operation_id=f"get_{res_name.replace('-', '_')}_by_id",
    )
    def get_item(
        item_id: uuid.UUID,
        user_ctx: UserContext = Depends(get_current_user),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint GET /{res_name}/{{id}} đang phát triển (TODO: Chủ module B)",
            http_status=501,
        )

    @router.post(
        f"/{res_name}",
        summary=f"Tạo mới {res_name}",
        operation_id=f"create_{res_name.replace('-', '_')}",
    )
    def create_item(
        req: CreateResourceRequest,
        _perm: str = Depends(require_permission("AD-1")),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint POST /{res_name} đang phát triển (TODO: Chủ module B)",
            http_status=501,
        )

    @router.patch(
        f"/{res_name}/{{item_id}}",
        summary=f"Cập nhật {res_name}",
        operation_id=f"update_{res_name.replace('-', '_')}",
    )
    def update_item(
        item_id: uuid.UUID,
        req: UpdateResourceRequest,
        _perm: str = Depends(require_permission("AD-1")),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint PATCH /{res_name}/{{id}} đang phát triển (TODO: Chủ module B)",
            http_status=501,
        )

    @router.post(
        f"/{res_name}/{{item_id}}/deactivate",
        summary=f"Ngừng kích hoạt {res_name}",
        operation_id=f"deactivate_{res_name.replace('-', '_')}",
    )
    def deactivate_item(
        item_id: uuid.UUID,
        _perm: str = Depends(require_permission("AD-1")),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint POST /{res_name}/{{id}}/deactivate đang phát triển",
            http_status=501,
        )


# 1. Đăng ký cho 10 tài nguyên danh mục chung
for resource in MASTER_DATA_RESOURCES:
    _register_crud_routes(resource)


# 2. Đăng ký cho users và roles (yêu cầu quyền AD-1 cho cả đọc và ghi)
def _register_admin_routes(admin_res: str) -> None:
    @router.get(
        f"/{admin_res}",
        summary=f"Danh sách {admin_res}",
        operation_id=f"list_{admin_res}",
    )
    def list_admin_items(
        _perm: str = Depends(require_permission("AD-1")),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint GET /{admin_res} đang phát triển",
            http_status=501,
        )

    @router.get(
        f"/{admin_res}/{{item_id}}",
        summary=f"Chi tiết {admin_res}",
        operation_id=f"get_{admin_res}_by_id",
    )
    def get_admin_item(
        item_id: uuid.UUID,
        _perm: str = Depends(require_permission("AD-1")),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint GET /{admin_res}/{{id}} đang phát triển",
            http_status=501,
        )

    @router.post(
        f"/{admin_res}",
        summary=f"Tạo mới {admin_res}",
        operation_id=f"create_{admin_res}",
    )
    def create_admin_item(
        req: CreateResourceRequest,
        _perm: str = Depends(require_permission("AD-1")),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint POST /{admin_res} đang phát triển",
            http_status=501,
        )

    @router.patch(
        f"/{admin_res}/{{item_id}}",
        summary=f"Cập nhật {admin_res}",
        operation_id=f"update_{admin_res}",
    )
    def update_admin_item(
        item_id: uuid.UUID,
        req: UpdateResourceRequest,
        _perm: str = Depends(require_permission("AD-1")),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint PATCH /{admin_res}/{{id}} đang phát triển",
            http_status=501,
        )

    @router.post(
        f"/{admin_res}/{{item_id}}/deactivate",
        summary=f"Ngừng kích hoạt {admin_res}",
        operation_id=f"deactivate_{admin_res}",
    )
    def deactivate_admin_item(
        item_id: uuid.UUID,
        _perm: str = Depends(require_permission("AD-1")),
        db: DbSession = Depends(get_db),
    ) -> dict[str, Any]:
        raise BusinessError(
            code="NOT_IMPLEMENTED",
            message=f"Endpoint POST /{admin_res}/{{id}}/deactivate đang phát triển",
            http_status=501,
        )


for admin_res in ["users", "roles"]:
    _register_admin_routes(admin_res)
