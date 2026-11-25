"""Web Controller cho phân hệ Tổng quan (Dashboard) – A-13, màn hình của `bgd`.

Thukho và quanly cũng có QL-8.1 nên dùng chung màn hình. Ba khối số liệu gọi ba API độc lập:
một API lỗi chỉ làm trống khối đó, các khối khác vẫn hiện.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user
from client.app.core.session import get_session_token

router = APIRouter(prefix="/dashboard", tags=["Dashboard Views"])

SECTIONS = ("tasks", "inventory", "orders")
ALERT_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
VN_TZ = timezone(timedelta(hours=7))


def get_templates(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


def load_dashboard(token: str | None) -> dict[str, Any]:
    """Gọi ba API dashboard; trả số liệu từng khối, lỗi từng khối và cảnh báo gộp."""
    api = ApiClient(token=token)
    data: dict[str, Any] = {}
    errors: dict[str, dict[str, str]] = {}
    for section in SECTIONS:
        try:
            data[section] = api.get(f"/dashboard/{section}").get("data") or {}
        except ClientApiError as exc:
            if exc.http_status == 403:
                raise
            data[section] = None
            errors[section] = {"code": exc.code, "message": exc.message}

    alerts = [a for s in SECTIONS if data.get(s) for a in data[s].get("alerts", [])]
    alerts.sort(key=lambda a: ALERT_ORDER.get(a.get("level", "INFO"), 9))
    return {
        **data,
        "errors": errors,
        "alerts": alerts,
        "updated_at": datetime.now(VN_TZ).strftime("%H:%M:%S"),
    }


@router.get("", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Bảng điều hành: cảnh báo, thẻ số task, tồn kho, đơn trong ngày."""
    templates = get_templates(request)
    menu = build_user_menu(user)
    try:
        dash = load_dashboard(get_session_token(request))
    except ClientApiError as exc:
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
        name="dashboard/index.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "dashboard",
            "dash": dash,
        },
    )


@router.post("/refresh", response_class=HTMLResponse)
def dashboard_refresh_htmx(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """HTMX: trả lại phần thân bảng điều hành (tự làm mới mỗi 60 giây hoặc bấm nút)."""
    templates = get_templates(request)
    try:
        dash = load_dashboard(get_session_token(request))
    except ClientApiError as exc:
        dash = {
            "errors": {s: {"code": exc.code, "message": exc.message} for s in SECTIONS},
            "alerts": [],
            "updated_at": datetime.now(VN_TZ).strftime("%H:%M:%S"),
        }
    return templates.TemplateResponse(
        request=request,
        name="dashboard/_panels.html",
        context={"request": request, "dash": dash},
    )
