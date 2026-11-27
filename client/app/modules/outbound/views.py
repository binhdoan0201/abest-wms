"""Web Controller cho phân hệ Xuất kho (Outbound)."""

import html
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


def _format_pick_session_option(row: dict[str, Any]) -> dict[str, str]:
    sid = str(row.get("pick_session_id") or row.get("session_id") or row.get("id") or "").strip()
    code = str(
        row.get("pick_session_code")
        or row.get("session_code")
        or row.get("pick_number")
        or row.get("order_number")
        or sid[:8]
    ).strip()
    status = str(row.get("status") or row.get("session_status") or "").strip()
    label = f"{code} ({status})" if status else code
    return {"id": sid, "label": label}


def _pick_session_label_from_detail(detail: dict[str, Any] | None, fallback_id: str) -> str:
    if isinstance(detail, dict):
        lines = detail.get("lines") or []
        if isinstance(lines, list):
            for line in lines:
                if isinstance(line, dict):
                    erp_no = str(line.get("erp_order_number") or "").strip()
                    if erp_no:
                        return f"Soạn đơn {erp_no}"
        for key in ("erp_order_number", "pick_session_code", "session_code"):
            val = str(detail.get(key) or "").strip()
            if val:
                return f"Soạn đơn {val}" if key == "erp_order_number" else val
    return f"Phiên {fallback_id[:8]}" if fallback_id else "Phiên soạn"


def _enrich_pick_session(session_data: Any, fallback_id: str = "") -> Any:
    if not isinstance(session_data, dict):
        return session_data
    sid = str(session_data.get("pick_session_id") or fallback_id or "").strip()
    label = _pick_session_label_from_detail(session_data, sid)
    enriched = dict(session_data)
    enriched["display_label"] = label
    if not str(enriched.get("pick_session_code") or "").strip():
        enriched["pick_session_code"] = label
    return enriched


def _load_pick_session_pickers(api: ApiClient) -> list[dict[str, str]]:
    pickers: list[dict[str, str]] = []
    seen: set[str] = set()
    for params in ({"page_size": 100, "limit": 100}, None):
        try:
            raw = (
                api.get("/users", params=params).get("data", [])
                if params
                else api.get("/users").get("data", [])
            )
        except ClientApiError:
            continue
        rows = raw.get("items", []) if isinstance(raw, dict) else raw
        if not isinstance(rows, list) or not rows:
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if "can_receive_tasks" in row and row.get("can_receive_tasks") is False:
                continue
            if "is_active" in row and row.get("is_active") is False:
                continue
            role_tokens: list[str] = []
            for k in ("role_code", "role", "role_name"):
                v = str(row.get(k) or "").strip().lower().replace("_", "-")
                if v:
                    role_tokens.append(v)
            roles_val = row.get("roles")
            if isinstance(roles_val, list):
                for r in roles_val:
                    if isinstance(r, dict):
                        rv = (
                            str(r.get("code") or r.get("role_code") or r.get("name") or "")
                            .strip()
                            .lower()
                            .replace("_", "-")
                        )
                    else:
                        rv = str(r or "").strip().lower().replace("_", "-")
                    if rv:
                        role_tokens.append(rv)
            if not any(t in {"nv-soan", "nv-soanhang", "picker"} for t in role_tokens):
                continue
            uid = str(row.get("user_id") or row.get("id") or row.get("sub") or "").strip()
            if not uid or uid in seen:
                continue
            full_name = str(row.get("full_name") or row.get("name") or "").strip()
            username = str(row.get("username") or "").strip()
            label = (
                f"{full_name} ({username})"
                if full_name and username
                else (full_name or username or uid[:8])
            )
            seen.add(uid)
            pickers.append({"id": uid, "label": label})
        if pickers:
            break
    return pickers


def _build_orders_table_context(
    request: Request,
    api: ApiClient,
    user: dict[str, Any],
    *,
    flash_msg: str | None = None,
    api_error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        orders = api.get("/outbound-orders").get("data", [])
    except ClientApiError:
        orders = []
    return {
        "request": request,
        "perms": _extract_perms(user),
        "orders": orders,
        "pickers": _load_pick_session_pickers(api),
        "flash_msg": flash_msg,
        "api_error": api_error,
    }


def _load_pick_session_options(
    api: ApiClient,
    user: dict[str, Any],
    current_session_id: str = "",
    current_session: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    seen: set[str] = set()
    user_id = str(user.get("user_id") or user.get("id") or user.get("sub") or "").strip()
    params: dict[str, Any] = {"task_type": "PICKING", "page_size": 100}
    if user_id:
        params["assigned_to"] = user_id

    closed_statuses = {"COMPLETED", "DONE", "CANCELLED", "CLOSED"}

    try:
        raw = api.get("/tasks", params=params).get("data", [])
        if isinstance(raw, list):
            for row in raw:
                if not isinstance(row, dict):
                    continue
                task_type = str(row.get("task_type") or "").strip().upper()
                ref_doc_type = str(row.get("ref_doc_type") or "").strip().upper()
                status = str(row.get("status") or "").strip().upper()
                if task_type and task_type != "PICKING":
                    continue
                if ref_doc_type and ref_doc_type != "PICK_SESSION":
                    continue
                if status in closed_statuses:
                    continue
                sid = str(row.get("ref_doc_id") or "").strip()
                if not sid or sid in seen:
                    continue

                detail: dict[str, Any] | None = None
                if (
                    isinstance(current_session, dict)
                    and str(current_session.get("pick_session_id") or "").strip() == sid
                ):
                    detail = current_session
                else:
                    try:
                        d_raw = api.get(f"/pick-sessions/{sid}").get("data")
                        if isinstance(d_raw, dict):
                            detail = d_raw
                    except ClientApiError:
                        detail = None

                label = _pick_session_label_from_detail(detail, sid)
                seen.add(sid)
                options.append({"id": sid, "label": label})
    except ClientApiError:
        pass

    if current_session_id and current_session_id not in seen:
        label = _pick_session_label_from_detail(current_session, current_session_id)
        seen.add(current_session_id)
        options.insert(0, {"id": current_session_id, "label": label})

    return options


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
    selected_session_id = (session_id or "").strip()
    if "QL-2.1" in perms:
        try:
            q = f"/outbound-orders?status={status}" if status else "/outbound-orders"
            orders = api.get(q).get("data", [])
        except ClientApiError as exc:
            if exc.http_status == 403:
                return _render_403(request, user, menu, exc.message, exc.code)
            api_error = {"code": exc.code, "message": exc.message}
    if selected_session_id and "SO-1" in perms:
        try:
            pick_session = _enrich_pick_session(
                api.get(f"/pick-sessions/{selected_session_id}").get("data"),
                selected_session_id,
            )
        except ClientApiError as exc:
            api_error = {"code": exc.code, "message": exc.message}
    pick_sessions = (
        _load_pick_session_options(api, user, selected_session_id, pick_session)
        if "SO-1" in perms
        else []
    )
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
            "pickers": _load_pick_session_pickers(api),
            "selected_status": status or "",
            "pick_session": pick_session,
            "pick_sessions": pick_sessions,
            "session_id": selected_session_id,
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
    selected_session_id = (session_id or "").strip()
    if selected_session_id:
        try:
            pick_session = _enrich_pick_session(
                api.get(f"/pick-sessions/{selected_session_id}").get("data"),
                selected_session_id,
            )
        except ClientApiError as exc:
            api_error = {"code": exc.code, "message": exc.message}
    pick_sessions = _load_pick_session_options(api, user, selected_session_id, pick_session)
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
            "pick_sessions": pick_sessions,
            "session_id": selected_session_id,
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


def _format_gi_option(gi: dict[str, Any]) -> dict[str, str]:
    gi_id = str(gi.get("gi_id") or gi.get("goods_issue_id") or gi.get("id") or "").strip()
    gi_no = str(
        gi.get("gi_number") or gi.get("gi_code") or gi.get("document_number") or gi_id[:8]
    ).strip()
    status = str(gi.get("status") or gi.get("gi_status") or "").strip()
    waybill = str(gi.get("tms_waybill_code") or "").strip()
    parts = [gi_no]
    if status:
        parts.append(status)
    if waybill:
        parts.append(f"WB: {waybill}")
    label = " – ".join(parts) if len(parts) > 1 else gi_no
    return {"id": gi_id, "label": label, "gi_number": gi_no, "status": status}


def _load_gi_options(
    api: ApiClient,
    order_id: str = "",
    gi_info: dict[str, Any] | None = None,
    selected_gi_id: str = "",
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    seen: set[str] = set()

    if order_id:
        try:
            order_data = api.get(f"/outbound-orders/{order_id}").get("data", {})
            if isinstance(order_data, dict):
                pkgs = order_data.get("packages") or []
                if isinstance(pkgs, list):
                    for pkg in pkgs:
                        if not isinstance(pkg, dict):
                            continue
                        gid = str(pkg.get("gi_id") or "").strip()
                        if not gid or gid in seen:
                            continue
                        gi_no = str(pkg.get("gi_number") or gid[:8]).strip()
                        seen.add(gid)
                        options.append({"id": gid, "label": gi_no})
        except ClientApiError:
            pass

    if isinstance(gi_info, dict):
        gid = str(gi_info.get("gi_id") or "").strip()
        if gid:
            gi_no = str(gi_info.get("gi_number") or gid[:8]).strip()
            if gid not in seen:
                seen.add(gid)
                options.insert(0, {"id": gid, "label": gi_no})

    sel_gid = selected_gi_id.strip()
    if sel_gid and sel_gid not in seen:
        seen.add(sel_gid)
        options.insert(0, {"id": sel_gid, "label": f"GI {sel_gid[:8]}"})

    return options


def _load_packing_lookups(
    api: ApiClient,
    selected_order_id: str = "",
    gi_info: dict[str, Any] | None = None,
    selected_gi_id: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
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
    gi_options = _load_gi_options(
        api,
        order_id=selected_order_id,
        gi_info=gi_info,
        selected_gi_id=selected_gi_id,
    )
    return boxes, vehs, orders, gi_options


@router.get("/outbound/packing", response_class=HTMLResponse)
def outbound_packing_page(
    request: Request,
    order_id: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Màn hình chuyên biệt cho NV Đóng gói & Xuất hàng GI (C-08)."""
    menu = build_user_menu(user)
    perms = _extract_perms(user)
    if "DG-1" not in perms:
        return _render_403(request, user, menu, "Chỉ nhân viên đóng gói mới có quyền truy cập")
    api = ApiClient(token=get_session_token(request))
    selected_oid = (order_id or "").strip()
    box_types, vehicles, packing_orders, gi_options = _load_packing_lookups(
        api, selected_order_id=selected_oid
    )
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
            "gi_options": gi_options,
            "selected_order_id": selected_oid,
            "selected_gi_id": "",
            "gi_info": None,
        },
    )


@router.get("/outbound/pack-and-ship/gi-options", response_class=HTMLResponse)
def outbound_pack_gi_options_htmx(
    request: Request,
    order_id: str = "",
    gi_id: str = "",
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    selected_oid = order_id.strip()
    selected_gid = gi_id.strip()
    gi_options = _load_gi_options(api, order_id=selected_oid, selected_gi_id=selected_gid)
    parts = ['<option value="">-- Chọn phiếu GI --</option>']
    for opt in gi_options:
        opt_id = str(opt.get("id") or "")
        opt_label = str(opt.get("label") or "")
        sel = " selected" if opt_id == selected_gid else ""
        safe_id = html.escape(opt_id, quote=True)
        safe_label = html.escape(opt_label, quote=False)
        parts.append(f'<option value="{safe_id}"{sel}>{safe_label}</option>')
    return HTMLResponse(content="\n".join(parts))


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
    ctx = _build_orders_table_context(
        request,
        api,
        user,
        flash_msg=flash_msg,
        api_error=api_error,
    )
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
    if not picker_user_id.strip():
        ctx = _build_orders_table_context(
            request,
            api,
            user,
            api_error={
                "code": "PICKER_REQUIRED",
                "message": "Vui lòng chọn người soạn hàng trước khi tạo phiên soạn.",
            },
        )
        return get_templates(request).TemplateResponse(
            request=request, name="outbound/_orders_table.html", context=ctx
        )
    flash_msg, api_error = None, None
    payload: dict[str, Any] = {"order_ids": [order_id], "pick_mode": pick_mode}
    payload["picker_user_id"] = picker_user_id.strip()
    try:
        res = api.post("/pick-sessions", json_data=payload).get("data", {})
        created_sid = str(res.get("pick_session_id") or "").strip()
        created_detail: dict[str, Any] | None = None
        if created_sid:
            try:
                d_raw = api.get(f"/pick-sessions/{created_sid}").get("data")
                if isinstance(d_raw, dict):
                    created_detail = d_raw
            except ClientApiError:
                created_detail = None
        created_label = _pick_session_label_from_detail(created_detail, created_sid)
        flash_msg = f"Đã tạo phiên soạn {created_label}!"
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}
    ctx = _build_orders_table_context(
        request,
        api,
        user,
        flash_msg=flash_msg,
        api_error=api_error,
    )
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
        ps = _enrich_pick_session(
            api.get(f"/pick-sessions/{pick_session_id}").get("data"),
            pick_session_id,
        )
    except ClientApiError:
        pass
    ctx = {
        "request": request,
        "pick_session": ps,
        "pick_sessions": _load_pick_session_options(api, user, pick_session_id, ps),
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
        ps = _enrich_pick_session(
            api.get(f"/pick-sessions/{pick_session_id}").get("data"),
            pick_session_id,
        )
    except ClientApiError:
        pass
    ctx = {
        "request": request,
        "pick_session": ps,
        "pick_sessions": _load_pick_session_options(api, user, pick_session_id, ps),
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
    selected_gi_id = gi_id.strip()
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
            created_gi_id = str(res.get("gi_id") or "").strip()
            created_gi_no = str(res.get("gi_number") or "").strip()
            gi_info = {
                "gi_id": created_gi_id,
                "gi_number": created_gi_no,
                "order_status": ord_status,
                "waybill_text": wb_text,
            }
            if created_gi_id:
                selected_gi_id = created_gi_id
            flash_msg = f"Đã lập phiếu GI {created_gi_no} — Vận đơn TMS: {wb_text}"
        elif action == "confirm_gi":
            signer = driver_signature_data.strip()
            if not signer:
                api_error = {
                    "code": "DRIVER_SIGNATURE_REQUIRED",
                    "message": "Vui lòng nhập họ tên tài xế để xác nhận ký giao hàng.",
                }
            else:
                res = api.post(
                    f"/goods-issues/{selected_gi_id}/confirm",
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
    if gi_info is None and selected_gi_id:
        gi_info = {
            "gi_id": selected_gi_id,
            "gi_number": selected_gi_id[:8],
            "order_status": "",
            "waybill_text": "chờ vận đơn",
        }
    box_types, vehicles, packing_orders, gi_options = _load_packing_lookups(
        api,
        selected_order_id=selected_order_id,
        gi_info=gi_info,
        selected_gi_id=selected_gi_id,
    )
    ctx = {
        "request": request,
        "flash_msg": flash_msg,
        "api_error": api_error,
        "box_types": box_types,
        "vehicles": vehicles,
        "packing_orders": packing_orders,
        "gi_options": gi_options,
        "selected_order_id": selected_order_id,
        "selected_gi_id": selected_gi_id,
        "gi_info": gi_info,
    }
    return get_templates(request).TemplateResponse(
        request=request, name="outbound/_pack_ship_panel.html", context=ctx
    )
