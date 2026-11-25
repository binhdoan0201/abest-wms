"""Web Controller cho ph?n h? ?i?u ph?i & Th?c thi Nhi?m v? (Tasks) ? Task D-08."""

from typing import Any

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user
from client.app.core.session import get_session_token

router = APIRouter(prefix="/tasks", tags=["Tasks Views"])

SUPERVISOR_ROLES = {"thukho", "quanly"}
BLOCKED_ROLES = {"admin", "bgd"}


def get_templates(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


def _render_403(
    request: Request,
    user: dict[str, Any],
    menu: list[dict[str, Any]],
    msg: str = "Kh?ng c? quy?n truy c?p ph?n h? Nhi?m v?",
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


def _load_workers(api: ApiClient) -> list[dict[str, Any]]:
    """T?i danh s?ch nh?n vi?n trong kho ?? Th? kho/Qu?n l? ch?n khi giao vi?c."""
    try:
        data = api.get("/users", params={"page_size": 100}).get("data", [])
        if isinstance(data, list):
            return [
                u
                for u in data
                if str(u.get("role_code", "")).startswith("nv-") and u.get("is_active", True)
            ]
    except ClientApiError:
        pass
    return []


def _fetch_tasks(
    api: ApiClient,
    scope: str,
    status: str | None = None,
    priority: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
    params: dict[str, Any] = {"scope": scope}
    if status:
        params["status"] = status
    try:
        tasks = api.get("/tasks", params=params).get("data", [])
        if not isinstance(tasks, list):
            tasks = []
        if priority:
            tasks = [t for t in tasks if t.get("priority") == priority]
        return tasks, None
    except ClientApiError as exc:
        if exc.http_status == 403:
            raise
        return [], {"code": exc.code, "message": exc.message}


@router.get("", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    scope: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """M?n h?nh ?i?u ph?i nhi?m v? (thukho, quanly) v? danh s?ch vi?c c?a nh?n vi?n."""
    templates = get_templates(request)
    menu = build_user_menu(user)
    role_code = user.get("role_code", "")
    if role_code in BLOCKED_ROLES:
        return _render_403(request, user, menu)

    is_supervisor = role_code in SUPERVISOR_ROLES
    effective_scope = scope or ("all" if is_supervisor else "mine")
    api = ApiClient(token=get_session_token(request))

    try:
        tasks, api_error = _fetch_tasks(
            api,
            scope=effective_scope,
            status=status or None,
            priority=priority or None,
        )
    except ClientApiError as exc:
        return _render_403(request, user, menu, exc.message, exc.code)

    workers = _load_workers(api) if is_supervisor else []

    return templates.TemplateResponse(
        request=request,
        name="tasks/index.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "tasks",
            "is_supervisor": is_supervisor,
            "tasks": tasks,
            "workers": workers,
            "filters": {
                "scope": effective_scope,
                "status": status or "",
                "priority": priority or "",
            },
            "api_error": api_error,
            "flash_msg": None,
        },
    )


@router.post("/create", response_class=HTMLResponse)
def create_task_htmx(
    request: Request,
    task_type: str = Form(...),
    stage: str = Form(...),
    ref_doc_type: str = Form(...),
    ref_doc_id: str = Form(...),
    priority: str = Form(default="NORMAL"),
    zone_id: str = Form(default=""),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """HTMX: Th? kho/Qu?n l? t?o nhi?m v? th? c?ng k?m m?c ?? ?u ti?n."""
    api = ApiClient(token=get_session_token(request))
    role_code = user.get("role_code", "")
    is_supervisor = role_code in SUPERVISOR_ROLES
    flash_msg, api_error = None, None

    payload: dict[str, Any] = {
        "task_type": task_type,
        "stage": stage,
        "ref_doc_type": ref_doc_type.strip(),
        "ref_doc_id": ref_doc_id.strip(),
        "priority": priority,
    }
    if zone_id.strip():
        payload["zone_id"] = zone_id.strip()

    try:
        res = api.post("/tasks", json_data=payload).get("data", {})
        flash_msg = f"?? t?o nhi?m v? m?i ({res.get('task_id', '')}) v?i ?u ti?n {priority}."
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}

    tasks, _ = _fetch_tasks(api, scope="all" if is_supervisor else "mine")
    return get_templates(request).TemplateResponse(
        request=request,
        name="tasks/_tasks_panel.html",
        context={
            "request": request,
            "user": user,
            "is_supervisor": is_supervisor,
            "tasks": tasks,
            "workers": _load_workers(api) if is_supervisor else [],
            "flash_msg": flash_msg,
            "api_error": api_error,
        },
    )


@router.post("/{task_id}/dispatch", response_class=HTMLResponse)
def dispatch_task_htmx(
    request: Request,
    task_id: str,
    action: str = Form(...),
    version_no: int = Form(...),
    worker_user_id: str = Form(default=""),
    note_or_reason: str = Form(default=""),
    completed_qty: str = Form(default=""),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """HTMX: Giao vi?c, ?i?u chuy?n, h?y task (qu?n l?) ho?c nh?n/t? ch?i/ho?n t?t (nh?n vi?n)."""
    api = ApiClient(token=get_session_token(request))
    role_code = user.get("role_code", "")
    is_supervisor = role_code in SUPERVISOR_ROLES
    flash_msg, api_error = None, None

    try:
        if action == "assign":
            api.post(
                f"/tasks/{task_id}/assign",
                json_data={
                    "assigned_to_user_id": worker_user_id.strip(),
                    "version_no": version_no,
                },
            )
            flash_msg = "?? giao nhi?m v? cho nh?n vi?n."
        elif action == "reassign":
            payload_re: dict[str, Any] = {
                "new_assigned_to_user_id": worker_user_id.strip(),
                "version_no": version_no,
            }
            if note_or_reason.strip():
                payload_re["reason"] = note_or_reason.strip()
            api.post(f"/tasks/{task_id}/reassign", json_data=payload_re)
            flash_msg = "?? ?i?u chuy?n nhi?m v? sang nh?n vi?n kh?c."
        elif action == "cancel":
            payload_can: dict[str, Any] = {"version_no": version_no}
            if note_or_reason.strip():
                payload_can["cancel_reason"] = note_or_reason.strip()
            api.post(f"/tasks/{task_id}/cancel", json_data=payload_can)
            flash_msg = "?? h?y nhi?m v?."
        elif action == "accept":
            api.post(f"/tasks/{task_id}/accept", json_data={"version_no": version_no})
            flash_msg = "?? ti?p nh?n nhi?m v?."
        elif action == "reject":
            api.post(
                f"/tasks/{task_id}/reject",
                json_data={
                    "rejection_reason": note_or_reason.strip(),
                    "version_no": version_no,
                },
            )
            flash_msg = "?? t? ch?i nhi?m v?."
        elif action == "complete":
            payload_done: dict[str, Any] = {"version_no": version_no}
            if completed_qty.strip():
                payload_done["completed_qty"] = completed_qty.strip()
            api.post(f"/tasks/{task_id}/complete", json_data=payload_done)
            flash_msg = "?? ho?n t?t nhi?m v?."
    except ClientApiError as exc:
        api_error = {"code": exc.code, "message": exc.message}

    tasks, _ = _fetch_tasks(api, scope="all" if is_supervisor else "mine")
    return get_templates(request).TemplateResponse(
        request=request,
        name="tasks/_tasks_panel.html",
        context={
            "request": request,
            "user": user,
            "is_supervisor": is_supervisor,
            "tasks": tasks,
            "workers": _load_workers(api) if is_supervisor else [],
            "flash_msg": flash_msg,
            "api_error": api_error,
        },
    )
