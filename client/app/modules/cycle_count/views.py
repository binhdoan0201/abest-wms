"""Web Controller cho phân hệ Kiểm kê (Cycle Count - B-10)."""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user
from client.app.core.session import get_session_token

router = APIRouter(tags=["Cycle Count Views"])


def _tpl(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


def _perms(user: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for p in user.get("permissions", []):
        if isinstance(p, dict):
            code = p.get("permission_code") or p.get("code") or ""
            if code:
                out.add(code)
        elif isinstance(p, str):
            out.add(p)
    return out


@router.get("/cycle-count", response_class=HTMLResponse)
def cycle_count_index(
    request: Request,
    sheet_id: str | None = None,
    msg: str | None = None,
    err: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    menu = build_user_menu(user)
    perms = _perms(user)
    if "KK-1" not in perms:
        return _tpl(request).TemplateResponse(
            request=request,
            name="_base/403.html",
            context={
                "request": request,
                "user": user,
                "menu": menu,
                "error_msg": "Không có quyền Kiểm kê",
            },
            status_code=403,
        )

    sheets, selected_sheet, api_err = [], None, err
    try:
        sheets = api.get("/cycle-counts").get("data", [])
        if sheet_id:
            selected_sheet = api.get(f"/cycle-counts/{sheet_id}").get("data")
    except ClientApiError as exc:
        api_err = exc.message

    return _tpl(request).TemplateResponse(
        request=request,
        name="cycle_count/index.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "cycle_count",
            "perms": perms,
            "sheets": sheets,
            "selected_sheet": selected_sheet,
            "flash_msg": msg,
            "api_error": api_err,
        },
    )


@router.post("/cycle-count/create")
def cycle_count_create(
    request: Request,
    count_type: str = Form(default="PERIODIC"),
    location_ids_raw: str = Form(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    loc_ids = [x.strip() for x in location_ids_raw.split(",") if x.strip()]
    due_at = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
    try:
        data = api.post(
            "/cycle-counts",
            json_data={"count_type": count_type, "due_at": due_at, "location_ids": loc_ids},
        ).get("data", {})
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={data.get('count_sheet_id', '')}&msg=Đã+tạo+phiếu+kiểm+kê",
            status_code=303,
        )
    except ClientApiError as exc:
        return RedirectResponse(url=f"/cycle-count?err={exc.message}", status_code=303)


@router.post("/cycle-count/{sheet_id}/lines/{line_id}/count")
def cycle_count_record(
    request: Request,
    sheet_id: str,
    line_id: str,
    blind_counted_qty: str = Form(...),
    mode: str = Form(default="count"),
    override_reason: str = Form(default=""),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    endpoint = "recount" if mode == "recount" else "count"
    try:
        api.post(
            f"/cycle-counts/{sheet_id}/lines/{line_id}/{endpoint}",
            json_data={
                "blind_counted_qty": blind_counted_qty.strip(),
                "same_counter_override_reason": override_reason.strip() or None,
            },
        )
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={sheet_id}&msg=Đã+ghi+nhận+kết+quả+đếm+mù",
            status_code=303,
        )
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={sheet_id}&err={exc.message}", status_code=303
        )


@router.post("/cycle-count/{sheet_id}/close")
def cycle_count_close(
    request: Request,
    sheet_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    try:
        api.post(f"/cycle-counts/{sheet_id}/close", json_data={})
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={sheet_id}&msg=Đã+đóng+phiếu+và+mở+khóa+vị+trí",
            status_code=303,
        )
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={sheet_id}&err={exc.message}", status_code=303
        )
