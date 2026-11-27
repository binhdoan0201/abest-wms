"""Web Controller cho phân hệ Dữ liệu nguồn (Master Data) – màn hình Admin (A-11), chỉ đọc.

Mỗi danh mục một tab, có tìm kiếm và phân trang; tab «Người dùng» đọc `GET /users`. Dùng cho
bước 1 của kịch bản demo: admin kiểm tra danh mục kho, vị trí, SKU đã nạp.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user, has_permission
from client.app.core.session import get_session_token

router = APIRouter(prefix="/master-data", tags=["Master Data Views"])

PAGE_SIZE = 20
# tài nguyên API → (tên tab, [(trường, tiêu đề cột)])
RESOURCES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "warehouses": (
        "Kho",
        [("erp_warehouse_code", "Mã kho"), ("warehouse_name", "Tên kho"), ("address", "Địa chỉ")],
    ),
    "zones": ("Khu", [("zone_code", "Mã khu"), ("zone_name", "Tên khu"), ("zone_type", "Loại")]),
    "locations": (
        "Vị trí",
        [("location_code", "Mã vị trí"), ("barcode", "Mã vạch"), ("status", "Trạng thái")],
    ),
    "skus": (
        "SKU",
        [
            ("sku_code", "Mã SKU"),
            ("sku_name", "Tên"),
            ("base_uom", "ĐVT"),
            ("min_stock_level", "Tồn tối thiểu"),
            ("storage_requirement", "Bảo quản"),
        ],
    ),
    "sku-barcodes": (
        "Mã vạch",
        [("barcode", "Mã vạch"), ("uom_code", "ĐVT"), ("conversion_factor", "Quy đổi")],
    ),
    "item-categories": (
        "Nhóm hàng",
        [
            ("category_code", "Mã nhóm"),
            ("category_name", "Tên"),
            ("min_receiving_shelf_life_days", "HSD tối thiểu khi nhận (ngày)"),
        ],
    ),
    "suppliers": (
        "Nhà cung cấp",
        [("erp_supplier_code", "Mã NCC"), ("supplier_name", "Tên"), ("phone", "Điện thoại")],
    ),
    "customers": (
        "Khách hàng",
        [("erp_customer_code", "Mã KH"), ("customer_name", "Tên"), ("phone", "Điện thoại")],
    ),
    "reason-codes": (
        "Mã lý do",
        [("reason_code", "Mã"), ("reason_category", "Nhóm"), ("description", "Mô tả")],
    ),
    "box-types": (
        "Loại thùng",
        [("box_code", "Mã"), ("box_name", "Tên"), ("max_weight_kg", "Tải tối đa (kg)")],
    ),
    "vehicles": (
        "Xe, tài xế",
        [
            ("license_plate", "Biển số"),
            ("vehicle_type", "Loại xe"),
            ("driver_name", "Tài xế"),
            ("carrier_name", "Nhà vận tải"),
        ],
    ),
    "users": (
        "Người dùng",
        [
            ("username", "Tài khoản"),
            ("full_name", "Họ tên"),
            ("role_code", "Vai trò"),
            ("primary_stage", "Khâu"),
            ("status", "Trạng thái"),
        ],
    ),
}


def get_templates(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


def _cell(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    if value is None or value == "":
        return "–"
    return str(value)


@router.get("", response_class=HTMLResponse)
def master_data_page(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Danh mục chỉ đọc cho admin; tab theo `?res=`, tìm `?q=`, trang `?page=`."""
    templates = get_templates(request)
    menu = build_user_menu(user)
    resource = request.query_params.get("res", "warehouses")
    if resource not in RESOURCES:
        resource = "warehouses"
    q = request.query_params.get("q", "").strip()
    try:
        page = max(1, int(request.query_params.get("page", "1")))
    except ValueError:
        page = 1
    label, columns = RESOURCES[resource]
    params: dict[str, Any] = {"page": page, "page_size": PAGE_SIZE}
    if q:
        params["q"] = q
    base = {"request": request, "user": user, "menu": menu, "active_menu": "master_data"}
    if not has_permission(user, "AD-1"):
        return templates.TemplateResponse(
            request=request,
            name="_base/403.html",
            context={
                **base,
                "error_msg": "Màn hình Dữ liệu nguồn chỉ dành cho Quản trị hệ thống (AD-1)",
                "error_code": "FORBIDDEN",
            },
            status_code=403,
        )
    try:
        payload = ApiClient(token=get_session_token(request)).get(f"/{resource}", params=params)
    except ClientApiError as exc:
        if exc.http_status == 403:
            return templates.TemplateResponse(
                request=request,
                name="_base/403.html",
                context={**base, "error_msg": exc.message, "error_code": exc.code},
                status_code=403,
            )
        payload = {"data": [], "meta": {}, "api_error": {"code": exc.code, "message": exc.message}}
    rows = payload.get("data") or []
    total = int((payload.get("meta") or {}).get("total") or len(rows))
    has_active = any("is_active" in r for r in rows)
    table = [
        {
            "cells": [_cell(r, f) for f, _ in columns],
            "active": r.get("is_active", True) if has_active else None,
        }
        for r in rows
    ]
    return templates.TemplateResponse(
        request=request,
        name="master_data/index.html",
        context={
            **base,
            "tabs": [(key, name) for key, (name, _) in RESOURCES.items()],
            "resource": resource,
            "label": label,
            "headers": [title for _, title in columns],
            "has_active": has_active,
            "table": table,
            "q": q,
            "page": page,
            "total": total,
            "has_prev": page > 1,
            "has_next": page * PAGE_SIZE < total,
            "api_error": payload.get("api_error"),
        },
    )
