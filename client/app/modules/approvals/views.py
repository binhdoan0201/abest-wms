"""Web Controller cho ph?n h? Ph? duy?t (Approvals) ? Task D-08."""

from typing import Any

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user
from client.app.core.session import get_session_token

router = APIRouter(prefix="/approvals", tags=["Approvals Views"])


def get_templates(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


def _extract_perms(user: dict[str, Any]) -> set[str]:
    perms: set[str] = set()
    for p in user.get("permissions", []):
        if isinstance(p, dict):
            code = p.get("permission_code") or p.get("code") or ""
            if code:
                perms.add(code)
        elif isinstance(p, str):
            perms.add(p)
    return perms


def _has_approval_access(perms: set[str]) -> bool:
    return "TK-3.2" in perms or "DY-1" in perms


def _render_403(
    request: Request,
    user: dict[str, Any],
    menu: list[dict[str, Any]],
    msg: str = "Kh?ng c? quy?n truy c?p ph?n h? Ph? duy?t",
    code: str = "FORBIDDEN",
) -> Response:
    return get_templates(request).TemplateResponse(
        request=request,
        name="_base/403.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "error_msg": msg,
            "error_code": code,
        },
        status_code=403,
    )


def _fetch_queue(
    api: ApiClient,
    status: str | None = None,
    tier: str | None = None,
    object_type: str | None = None,
    expired: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str] | None]:
    params: dict[str, Any] = {"page": 1, "page_size": 50}
    if status:
        params["status"] = status
    if tier:
        params["tier"] = tier
    if object_type:
        params["object_type"] = object_type
    if expired is not None:
        params["expired"] = str(expired).lower()
    try:
        res = api.get("/approvals", params=params)
        return res.get("data", []), res.get("meta", {}), None
    except ClientApiError as exc:
        if exc.http_status == 403:
            raise
        return [], {}, {"code": exc.code, "message": exc.message}


@router.get("", response_class=HTMLResponse)
def approvals_page(
    request: Request,
    status: str | None = None,
    tier: str | None = None,
    object_type: str | None = None,
    expired: str | None = None,
    selected_id: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """M?n h?nh h?ng ch? ph? duy?t cho Th? kho (D1) v? Qu?n l? (D2)."""
    templates = get_templates(request)
    menu = build_user_menu(user)
    perms = _extract_perms(user)
    if not _has_approval_access(perms):
        return _render_403(request, user, menu)

    api = ApiClient(token=get_session_token(request))
    expired_bool: bool | None = True if expired == "true" else None
    try:
        items, meta, api_error = _fetch_queue(
            api,
            status=status or None,
            tier=tier or None,
            object_type=object_type or None,
            expired=expired_bool,
        )
    except ClientApiError as exc:
        return _render_403(request, user, menu, exc.message, exc.code)

    detail: dict[str, Any] | None = None
    if selected_id:
        try:
            detail = api.get(f"/approvals/{selected_id}", params={"lock": "true"}).get("data")
        except ClientApiError as exc:
            api_error = {"code": exc.code, "message": exc.message}

    return templates.TemplateResponse(
        request=request,
        name="approvals/index.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "approvals",
            "perms": perms,
            "items": items,
            "meta": meta,
            "detail": detail,
            "filters": {
                "status": status or "",
                "tier": tier or "",
                "object_type": object_type or "",
                "expired": expired or "",
            },
            "api_error": api_error,
            "flash_msg": None,
        },
    )


@router.get("/{approval_id}/panel", response_class=HTMLResponse)
def approval_detail_panel_htmx(
    request: Request,
    approval_id: str,
    lock: bool = True,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """HTMX: t?i panel chi ti?t h? s? duy?t k?m kh?a xem."""
    api = ApiClient(token=get_session_token(request))
    detail, api_error = None, None
    try:
        detail = api.get(f"/approvals/{approval_id}", params={"lock": str(lock).lower()}).get(
            "data"
        )
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}

    return get_templates(request).TemplateResponse(
        request=request,
        name="approvals/_detail_panel.html",
        context={
            "request": request,
            "user": user,
            "perms": _extract_perms(user),
            "detail": detail,
            "api_error": api_error,
            "flash_msg": None,
        },
    )


@router.post("/{approval_id}/unlock", response_class=HTMLResponse)
def approval_unlock_htmx(
    request: Request,
    approval_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """HTMX: m? kh?a h? s? ?ang xem."""
    api = ApiClient(token=get_session_token(request))
    detail, flash_msg, api_error = None, None, None
    try:
        api.post(f"/approvals/{approval_id}/unlock")
        flash_msg = "?? gi?i ph?ng kh?a xem h? s?."
        detail = api.get(f"/approvals/{approval_id}", params={"lock": "false"}).get("data")
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}

    return get_templates(request).TemplateResponse(
        request=request,
        name="approvals/_detail_panel.html",
        context={
            "request": request,
            "user": user,
            "perms": _extract_perms(user),
            "detail": detail,
            "api_error": api_error,
            "flash_msg": flash_msg,
        },
    )


@router.post("/{approval_id}/decide", response_class=HTMLResponse)
def approval_decide_htmx(
    request: Request,
    approval_id: str,
    action: str = Form(...),
    version_no: int = Form(...),
    reason_or_note: str = Form(default=""),
    reauth_method: str = Form(default="PASSWORD"),
    reauth_password: str = Form(default=""),
    request_recount: str | None = Form(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """HTMX: x? l? duy?t, t? ch?i, y?u c?u ??m l?i/b? sung ho?c chuy?n c?p tr?n."""
    api = ApiClient(token=get_session_token(request))
    flash_msg, api_error, detail = None, None, None
    note = reason_or_note.strip()

    try:
        if action == "approve":
            payload: dict[str, Any] = {"version_no": version_no}
            if note:
                payload["recommendation_or_reason"] = note
            if reauth_password.strip():
                payload["reauth_method"] = reauth_method or "PASSWORD"
                payload["reauth_password"] = reauth_password.strip()
            api.post(f"/approvals/{approval_id}/approve", json_data=payload)
            flash_msg = "?? ph? duy?t h? s? th?nh c?ng."
        elif action == "reject":
            api.post(
                f"/approvals/{approval_id}/reject",
                json_data={"rejection_reason": note, "version_no": version_no},
            )
            flash_msg = "?? t? ch?i h? s? ph? duy?t."
        elif action == "request_info":
            is_recount = request_recount == "true"
            api.post(
                f"/approvals/{approval_id}/request-info",
                json_data={
                    "info_required_note": note,
                    "request_recount": is_recount,
                    "version_no": version_no,
                },
            )
            flash_msg = (
                "?? g?i y?u c?u ??m l?i ki?m k?."
                if is_recount
                else "?? g?i y?u c?u b? sung th?ng tin."
            )
        elif action == "escalate":
            payload_esc: dict[str, Any] = {"version_no": version_no}
            if note:
                payload_esc["recommendation_or_reason"] = note
            api.post(f"/approvals/{approval_id}/escalate", json_data=payload_esc)
            flash_msg = "?? chuy?n h? s? l?n c?p ph? duy?t cao h?n."
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}

    try:
        detail = api.get(f"/approvals/{approval_id}", params={"lock": "false"}).get("data")
    except ClientApiError:
        pass

    return get_templates(request).TemplateResponse(
        request=request,
        name="approvals/_detail_panel.html",
        context={
            "request": request,
            "user": user,
            "perms": _extract_perms(user),
            "detail": detail,
            "api_error": api_error,
            "flash_msg": flash_msg,
        },
    )
