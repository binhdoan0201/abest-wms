"""Web Controller cho phân hệ Quản lý Tồn kho (Inventory)."""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user
from client.app.core.session import get_session_token

router = APIRouter(tags=["Inventory Views"])


def get_templates(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Trang hiển thị danh sách tồn kho cân đối (chuẩn MVC phân tách Controller - View - Model)."""
    templates = get_templates(request)
    token = get_session_token(request)
    menu = build_user_menu(user)
    api = ApiClient(token=token)

    try:
        response_data = api.get("/inventory/balances")
        balances = response_data.get("data", [])
        return templates.TemplateResponse(
            request=request,
            name="inventory/index.html",
            context={
                "request": request,
                "user": user,
                "menu": menu,
                "active_menu": "inventory",
                "balances": balances,
            },
        )
    except ClientApiError as exc:
        if exc.http_status == 403:
            return templates.TemplateResponse(
                request=request,
                name="_base/403.html",
                context={
                    "request": request,
                    "user": user,
                    "menu": menu,
                    "error_msg": exc.message,
                    "error_code": exc.code,
                },
                status_code=403,
            )
        # Các lỗi khác (409, 500, ...)
        return templates.TemplateResponse(
            request=request,
            name="inventory/index.html",
            context={
                "request": request,
                "user": user,
                "menu": menu,
                "active_menu": "inventory",
                "balances": [],
                "api_error": {"code": exc.code, "message": exc.message},
            },
            status_code=exc.http_status,
        )


@router.post("/inventory/refresh", response_class=HTMLResponse)
def inventory_refresh_htmx(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Endpoint HTMX trả về phần bảng HTML (_table.html) cập nhật dữ liệu tức thì."""
    templates = get_templates(request)
    token = get_session_token(request)
    api = ApiClient(token=token)

    try:
        response_data = api.get("/inventory/balances")
        balances = response_data.get("data", [])
    except ClientApiError:
        balances = []

    return templates.TemplateResponse(
        request=request,
        name="inventory/_table.html",
        context={
            "request": request,
            "balances": balances,
        },
    )
