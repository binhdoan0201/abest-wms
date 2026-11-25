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


def _v(v: int | None) -> dict[str, int]:
    return {"version_no": v} if v is not None else {}


def _extract_perms(user: dict[str, Any]) -> set[str]:
    perms: set[str] = set()
    for p in user.get("permissions", []):
        if isinstance(p, dict):
            c = p.get("permission_code") or p.get("code") or ""
            if c:
                perms.add(c)
        elif isinstance(p, str):
            perms.add(p)
    return perms


def _load_active_reason_codes(api: ApiClient) -> list[dict[str, Any]]:
    try:
        items = api.get("/reason-codes", params={"is_active": "true", "page_size": 100}).get(
            "data", []
        )
        if isinstance(items, list) and items:
            return items
    except ClientApiError:
        pass
    return [
        {"reason_code": "DISCREPANCY_SHORT", "description": "Giao thiếu số lượng"},
        {"reason_code": "DAMAGED_TRANSIT", "description": "Hàng hư hỏng"},
        {"reason_code": "EXPIRED_LOT", "description": "Hàng cận/hết hạn"},
    ]


def _render_403(
    request: Request,
    user: dict[str, Any],
    menu: list[dict[str, Any]],
    msg: str = "Không có quyền truy cập màn hình này",
    code: str = "FORBIDDEN",
) -> Response:
    ctx = {"request": request, "user": user, "menu": menu, "error_msg": msg, "error_code": code}
    return get_templates(request).TemplateResponse(
        request=request, name="_base/403.html", context=ctx, status_code=403
    )


@router.get("/outbound", response_class=HTMLResponse)
def outbound_page(
    request: Request,
    status: str | None = None,
    session_id: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    templates = get_templates(request)
    api = ApiClient(token=get_session_token(request))
    menu = build_user_menu(user)
    perms = _extract_perms(user)
    if "QL-2.1" not in perms and "SO-1" not in perms and "DG-1" not in perms:
        return _render_403(request, user, menu, "Không có quyền truy cập phân hệ Xuất kho")
    orders, pick_session, api_error = [], None, None
    if "QL-2.1" in perms:
        try:
            q = f"/outbound-orders?status={status}" if status else "/outbound-orders"
            orders = api.get(q).get("data", [])
        except ClientApiError as exc:
            if exc.http_status == 403:
                return _render_403(request, user, menu, exc.message, exc.code)
            api_error = {"code": exc.code, "message": exc.message}
    if session_id and "SO-1" in perms:
        try:
            pick_session = api.get(f"/pick-sessions/{session_id}").get("data")
        except ClientApiError as exc:
            api_error = {"code": exc.code, "message": exc.message}
    return templates.TemplateResponse(
        request=request,
        name="outbound/index.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "outbound",
            "role_code": user.get("role_code", ""),
            "perms": perms,
            "orders": orders,
            "selected_status": status or "",
            "pick_session": pick_session,
            "session_id": session_id or "",
            "pick_action_url": "/outbound",
            "reason_codes": _load_active_reason_codes(api),
            "api_error": api_error,
        },
    )


@router.get("/outbound/picking", response_class=HTMLResponse)
def outbound_picking_page(
    request: Request,
    session_id: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Màn hình chuyên biệt cho NV Soạn hàng (C-08)."""
    templates = get_templates(request)
    api = ApiClient(token=get_session_token(request))
    menu = build_user_menu(user)
    perms = _extract_perms(user)
    if "SO-1" not in perms:
        return _render_403(request, user, menu, "Chỉ nhân viên soạn hàng mới có quyền truy cập")
    pick_session, api_error = None, None
    if session_id:
        try:
            pick_session = api.get(f"/pick-sessions/{session_id}").get("data")
        except ClientApiError as exc:
            api_error = {"code": exc.code, "message": exc.message}
    return templates.TemplateResponse(
        request=request,
        name="outbound/picking.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "outbound",
            "perms": perms,
            "pick_session": pick_session,
            "session_id": session_id or "",
            "pick_action_url": "/outbound/picking",
            "api_error": api_error,
        },
    )


@router.get("/outbound/packing", response_class=HTMLResponse)
def outbound_packing_page(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Màn hình chuyên biệt cho NV Đóng gói & Xuất hàng GI (C-08)."""
    menu = build_user_menu(user)
    perms = _extract_perms(user)
    if "DG-1" not in perms:
        return _render_403(request, user, menu, "Chỉ nhân viên đóng gói mới có quyền truy cập")
    return get_templates(request).TemplateResponse(
        request=request,
        name="outbound/packing.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "outbound",
            "perms": perms,
        },
    )


@router.post("/outbound/orders/{order_id}/allocate", response_class=HTMLResponse)
def outbound_allocate_htmx(
    request: Request,
    order_id: str,
    strategy: str = Form(default="FEFO"),
    version_no: int | None = Form(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    flash_msg, api_error = None, None
    try:
        api.post(
            f"/outbound-orders/{order_id}/allocate",
            json_data={"strategy": strategy, **_v(version_no)},
        )
        flash_msg = "Đã cấp phát tồn kho thành công!"
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}
    try:
        orders = api.get("/outbound-orders").get("data", [])
    except ClientApiError:
        orders = []
    ctx = {
        "request": request,
        "perms": _extract_perms(user),
        "orders": orders,
        "flash_msg": flash_msg,
        "api_error": api_error,
    }
    return get_templates(request).TemplateResponse(
        request=request, name="outbound/_orders_table.html", context=ctx
    )


@router.post("/outbound/pick-sessions/create", response_class=HTMLResponse)
def outbound_create_pick_htmx(
    request: Request,
    order_id: str = Form(...),
    pick_mode: str = Form(default="SINGLE_ORDER"),
    picker_user_id: str = Form(default=""),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    flash_msg, api_error = None, None
    payload: dict[str, Any] = {"order_ids": [order_id], "pick_mode": pick_mode}
    if picker_user_id.strip():
        payload["picker_user_id"] = picker_user_id.strip()
    try:
        res = api.post("/pick-sessions", json_data=payload).get("data", {})
        flash_msg = f"Đã tạo phiên soạn {res.get('pick_session_id', '')}!"
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}
    try:
        orders = api.get("/outbound-orders").get("data", [])
    except ClientApiError:
        orders = []
    ctx = {
        "request": request,
        "perms": _extract_perms(user),
        "orders": orders,
        "flash_msg": flash_msg,
        "api_error": api_error,
    }
    return get_templates(request).TemplateResponse(
        request=request, name="outbound/_orders_table.html", context=ctx
    )


@router.post(
    "/outbound/pick-sessions/{pick_session_id}/lines/{pick_line_id}/confirm",
    response_class=HTMLResponse,
)
def outbound_confirm_pick_htmx(
    request: Request,
    pick_session_id: str,
    pick_line_id: str,
    qty_picked: str = Form(...),
    target_tote_barcode: str = Form(default=""),
    version_no: int | None = Form(default=None),
    pick_action_url: str = Form(default="/outbound"),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    flash_msg, api_error, ps = None, None, None
    payload: dict[str, Any] = {"qty_picked": qty_picked, **_v(version_no)}
    if target_tote_barcode.strip():
        payload["target_tote_barcode"] = target_tote_barcode.strip()
    try:
        api.post(
            f"/pick-sessions/{pick_session_id}/lines/{pick_line_id}/confirm", json_data=payload
        )
        flash_msg = "Đã xác nhận soạn dòng hàng!"
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}
    try:
        ps = api.get(f"/pick-sessions/{pick_session_id}").get("data")
    except ClientApiError:
        pass
    ctx = {
        "request": request,
        "pick_session": ps,
        "session_id": pick_session_id,
        "pick_action_url": pick_action_url,
        "reason_codes": _load_active_reason_codes(api),
        "flash_msg": flash_msg,
        "api_error": api_error,
    }
    return get_templates(request).TemplateResponse(
        request=request, name="outbound/_pick_panel.html", context=ctx
    )


@router.post(
    "/outbound/pick-sessions/{pick_session_id}/lines/{pick_line_id}/exception",
    response_class=HTMLResponse,
)
def outbound_exception_pick_htmx(
    request: Request,
    pick_session_id: str,
    pick_line_id: str,
    exception_type: str = Form(default="EXCEPTION_SHORT"),
    exception_reason: str = Form(...),
    qty_actual: str = Form(default="0"),
    version_no: int = Form(default=1),
    pick_action_url: str = Form(default="/outbound"),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    flash_msg, api_error, ps = None, None, None
    payload: dict[str, Any] = {
        "exception_type": exception_type,
        "exception_reason": exception_reason.strip(),
        "qty_actual": qty_actual,
        "version_no": version_no,
    }
    try:
        api.post(
            f"/pick-sessions/{pick_session_id}/lines/{pick_line_id}/exception",
            json_data=payload,
        )
        flash_msg = "Đã ghi nhận ngoại lệ dòng soạn hàng!"
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}
    try:
        ps = api.get(f"/pick-sessions/{pick_session_id}").get("data")
    except ClientApiError:
        pass
    ctx = {
        "request": request,
        "pick_session": ps,
        "session_id": pick_session_id,
        "pick_action_url": pick_action_url,
        "reason_codes": _load_active_reason_codes(api),
        "flash_msg": flash_msg,
        "api_error": api_error,
    }
    resp: Response = request.app.state.templates.TemplateResponse(
        request=request, name="outbound/_pick_panel.html", context=ctx
    )
    return resp


@router.post("/outbound/pack-and-ship", response_class=HTMLResponse)
def outbound_pack_ship_htmx(
    request: Request,
    action: str = Form(...),
    order_id: str = Form(default=""),
    gi_id: str = Form(default=""),
    weight_kg: str = Form(default="1.0"),
    driver_signature_data: str = Form(default=""),
    version_no: int | None = Form(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    flash_msg, api_error = None, None
    try:
        if action == "package":
            res = api.post(
                f"/outbound-orders/{order_id}/packages",
                json_data={"weight_kg": weight_kg, **_v(version_no)},
            ).get("data", {})
            flash_msg = (
                f"Đã tạo kiện {res.get('package_barcode', '')} ({res.get('package_id', '')})"
            )
        elif action == "create_gi":
            res = api.post("/goods-issues", json_data={"order_id": order_id, **_v(version_no)}).get(
                "data", {}
            )
            flash_msg = f"Đã lập phiếu GI {res.get('gi_number', '')} ({res.get('gi_id', '')})"
        elif action == "confirm_gi":
            res = api.post(
                f"/goods-issues/{gi_id}/confirm",
                json_data={
                    "driver_signature_data": driver_signature_data or None,
                    **_v(version_no),
                },
            ).get("data", {})
            flash_msg = f"Đã xuất kho {res.get('gi_number', '')} ({res.get('status', '')})"
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}
    ctx = {"request": request, "flash_msg": flash_msg, "api_error": api_error}
    return get_templates(request).TemplateResponse(
        request=request, name="outbound/_pack_ship_panel.html", context=ctx
    )
