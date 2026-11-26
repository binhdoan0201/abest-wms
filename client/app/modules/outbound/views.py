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


def _format_packing_order_option(order: dict[str, Any]) -> dict[str, str]:
    order_id = str(order.get("order_id") or order.get("outbound_order_id") or order.get("id") or "")
    order_no = str(
        order.get("erp_order_number")
        or order.get("order_number")
        or order.get("order_code")
        or order_id[:8]
    )
    customer = str(
        order.get("customer_name")
        or order.get("customer")
        or order.get("receiver_name")
        or order.get("ship_to_name")
        or ""
    ).strip()
    label = f"{order_no} – {customer}" if customer else order_no
    status = str(order.get("status") or order.get("order_status") or "")
    return {"id": order_id, "label": label, "status": status}


def _load_packing_lookups(
    api: ApiClient,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    boxes: list[dict[str, Any]] = []
    vehs: list[dict[str, Any]] = []
    orders: list[dict[str, str]] = []
    try:
        raw_b = api.get("/box-types", params={"page_size": 100}).get("data", [])
        if isinstance(raw_b, list):
            boxes = raw_b
    except ClientApiError:
        pass
    try:
        raw_v = api.get("/vehicles", params={"is_active": "true", "page_size": 100}).get("data", [])
        if isinstance(raw_v, list):
            vehs = raw_v
    except ClientApiError:
        pass
    seen: set[str] = set()
    for st in ("PICKED", "PACKING", "READY_TO_SHIP"):
        try:
            raw_o = api.get("/outbound-orders", params={"status": st, "page_size": 100}).get(
                "data", []
            )
            if isinstance(raw_o, list):
                for row in raw_o:
                    if isinstance(row, dict):
                        opt = _format_packing_order_option(row)
                        if opt["id"] and opt["id"] not in seen:
                            seen.add(opt["id"])
                            orders.append(opt)
        except ClientApiError:
            pass
    return boxes, vehs, orders


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
    api = ApiClient(token=get_session_token(request))
    box_types, vehicles, packing_orders = _load_packing_lookups(api)
    return get_templates(request).TemplateResponse(
        request=request,
        name="outbound/packing.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "outbound",
            "perms": perms,
            "box_types": box_types,
            "vehicles": vehicles,
            "packing_orders": packing_orders,
            "selected_order_id": "",
            "gi_info": None,
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
    box_type_id: str = Form(default=""),
    weight_kg: str = Form(default="1.0"),
    vehicle_id: str = Form(default=""),
    driver_signature_data: str = Form(default=""),
    version_no: int | None = Form(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    flash_msg, api_error, gi_info = None, None, None
    selected_order_id = order_id.strip()
    try:
        if action == "package":
            payload = {"weight_kg": weight_kg, **_v(version_no)}
            if box_type_id.strip():
                payload["box_type_id"] = box_type_id.strip()
            res = api.post(f"/outbound-orders/{order_id.strip()}/packages", json_data=payload).get(
                "data", {}
            )
            lbl = res.get("package_barcode") or res.get("package_id") or ""
            flash_msg = "Đã tạo kiện đóng gói" + (f" {lbl}" if lbl else "")
        elif action == "create_gi":
            payload = {"order_id": order_id.strip(), **_v(version_no)}
            if vehicle_id.strip():
                payload["vehicle_id"] = vehicle_id.strip()
            res = api.post("/goods-issues", json_data=payload).get("data", {})
            wb_text = res.get("tms_waybill_code") or "chờ vận đơn"
            ord_status = res.get("order_status") or res.get("status") or ""
            gi_info = {
                "gi_id": res.get("gi_id", ""),
                "gi_number": res.get("gi_number", ""),
                "order_status": ord_status,
                "waybill_text": wb_text,
            }
            flash_msg = (
                f"Đã lập phiếu GI {res.get('gi_number', '')} "
                f"({res.get('gi_id', '')}) — Vận đơn TMS: {wb_text}"
            )
        elif action == "confirm_gi":
            signer = driver_signature_data.strip()
            if not signer:
                api_error = {
                    "code": "DRIVER_SIGNATURE_REQUIRED",
                    "message": "Vui lòng nhập họ tên tài xế để xác nhận ký giao hàng.",
                }
            else:
                res = api.post(
                    f"/goods-issues/{gi_id.strip()}/confirm",
                    json_data={"driver_signature_data": signer, **_v(version_no)},
                ).get("data", {})
                final_status = res.get("order_status") or res.get("status") or ""
                flash_msg = f"Đã xuất kho {res.get('gi_number', '')} ({final_status})"
    except ClientApiError as exc:
        if exc.code == "OUTBOUND_WAYBILL_REQUIRED":
            api_error = {
                "code": exc.code,
                "message": (
                    "Chưa có mã vận đơn TMS cho phiếu xuất kho này. "
                    "Vui lòng cập nhật vận đơn trước khi xác nhận xuất hàng."
                ),
            }
        else:
            api_error = {"code": exc.code, "message": exc.message}
    box_types, vehicles, packing_orders = _load_packing_lookups(api)
    ctx = {
        "request": request,
        "flash_msg": flash_msg,
        "api_error": api_error,
        "box_types": box_types,
        "vehicles": vehicles,
        "packing_orders": packing_orders,
        "selected_order_id": selected_order_id,
        "gi_info": gi_info,
    }
    return get_templates(request).TemplateResponse(
        request=request, name="outbound/_pack_ship_panel.html", context=ctx
    )
