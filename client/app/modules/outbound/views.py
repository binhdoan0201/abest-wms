"""Web Controller cho phân hệ Xuất kho (Outbound)."""

from typing import Any

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user
from client.app.core.session import get_session_token

router = APIRouter(tags=["Outbound Views"])


def get_templates(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


@router.get("/outbound", response_class=HTMLResponse)
def outbound_page(
    request: Request,
    status: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Trang quản lý danh sách đơn xuất kho và điều phối soạn/đóng gói/xuất hàng."""
    templates = get_templates(request)
    token = get_session_token(request)
    menu = build_user_menu(user)
    api = ApiClient(token=token)

    query = f"/outbound-orders?status={status}" if status else "/outbound-orders"
    try:
        response_data = api.get(query)
        orders = response_data.get("data", [])
        return templates.TemplateResponse(
            request=request,
            name="outbound/index.html",
            context={
                "request": request,
                "user": user,
                "menu": menu,
                "active_menu": "outbound",
                "orders": orders,
                "selected_status": status or "",
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
        return templates.TemplateResponse(
            request=request,
            name="outbound/index.html",
            context={
                "request": request,
                "user": user,
                "menu": menu,
                "active_menu": "outbound",
                "orders": [],
                "selected_status": status or "",
                "api_error": {"code": exc.code, "message": exc.message},
            },
            status_code=exc.http_status,
        )


@router.post("/outbound/orders/{order_id}/allocate", response_class=HTMLResponse)
def outbound_allocate_htmx(
    request: Request,
    order_id: str,
    strategy: str = Form(default="FEFO"),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """HTMX action cấp phát tồn kho FEFO/FIFO trực tiếp từ giao diện danh sách đơn."""
    templates = get_templates(request)
    token = get_session_token(request)
    api = ApiClient(token=token)

    flash_msg: str | None = None
    api_error: dict[str, str] | None = None

    try:
        api.post(f"/outbound-orders/{order_id}/allocate", json_data={"strategy": strategy})
        flash_msg = "Đã cấp phát tồn kho thành công!"
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}

    try:
        orders = api.get("/outbound-orders").get("data", [])
    except ClientApiError:
        orders = []

    return templates.TemplateResponse(
        request=request,
        name="outbound/_orders_table.html",
        context={
            "request": request,
            "orders": orders,
            "flash_msg": flash_msg,
            "api_error": api_error,
        },
    )
