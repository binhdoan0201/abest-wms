"""Web Controller cho phân hệ Kiểm kê (Cycle Count - B-10)."""

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus

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


def _safe_list(
    api: ApiClient, path: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    try:
        raw = api.get(path, params=params).get("data", [])
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
        if isinstance(raw, dict) and isinstance(raw.get("items"), list):
            return [x for x in raw["items"] if isinstance(x, dict)]
    except ClientApiError:
        pass
    return []


@router.get("/cycle-count", response_class=HTMLResponse)
def cycle_count_index(
    request: Request,
    sheet_id: str | None = None,
    count_sheet_id: str | None = None,
    msg: str | None = None,
    err: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    menu = build_user_menu(user)
    perms = _perms(user)
    if "KK-1" not in perms and "TK-1.1" not in perms:
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

    active_sheet_id = (sheet_id or count_sheet_id or "").strip() or None
    sheets, selected_sheet, api_err = [], None, err
    locations: list[dict[str, Any]] = []
    location_code_map: dict[str, str] = {}
    sku_code_map: dict[str, str] = {}

    try:
        sheets = api.get("/cycle-counts").get("data", [])
        if active_sheet_id:
            selected_sheet = api.get(f"/cycle-counts/{active_sheet_id}").get("data")
    except ClientApiError as exc:
        api_err = exc.message

    locations = _safe_list(api, "/locations", {"page_size": 100})
    for loc in locations:
        lid = str(loc.get("location_id") or "")
        lcode = str(loc.get("location_code") or loc.get("code") or "")
        if lid and lcode:
            location_code_map[lid] = lcode

    for sku in _safe_list(api, "/skus", {"page_size": 100}):
        sid = str(sku.get("sku_id") or "")
        scode = str(sku.get("sku_code") or "")
        if sid and scode:
            sku_code_map[sid] = scode

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
            "locations": locations,
            "location_code_map": location_code_map,
            "sku_code_map": sku_code_map,
            "flash_msg": msg,
            "api_error": api_err,
        },
    )


@router.post("/cycle-count/create")
def cycle_count_create(
    request: Request,
    count_type: str = Form(default="PERIODIC"),
    location_ids: list[str] = Form(default=[]),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    loc_ids = [x.strip() for x in location_ids if x and x.strip()]
    due_at = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
    try:
        data = api.post(
            "/cycle-counts",
            json_data={"count_type": count_type, "due_at": due_at, "location_ids": loc_ids},
        ).get("data", {})
        msg = quote_plus("Đã tạo phiếu kiểm kê")
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={data.get('count_sheet_id', '')}&msg={msg}",
            status_code=303,
        )
    except ClientApiError as exc:
        return RedirectResponse(url=f"/cycle-count?err={quote_plus(exc.message)}", status_code=303)


def _submit_count(
    request: Request,
    sheet_id: str,
    line_id: str,
    blind_counted_qty: str,
    override_reason: str,
    is_recount: bool,
) -> Response:
    api = ApiClient(token=get_session_token(request))
    endpoint = "recount" if is_recount else "count"
    try:
        api.post(
            f"/cycle-counts/{sheet_id}/lines/{line_id}/{endpoint}",
            json_data={
                "blind_counted_qty": blind_counted_qty.strip(),
                "same_counter_override_reason": override_reason.strip() or None,
            },
        )
        msg_text = "Đã ghi nhận kết quả đếm lại" if is_recount else "Đã ghi nhận kết quả đếm mù"
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={sheet_id}&msg={quote_plus(msg_text)}",
            status_code=303,
        )
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={sheet_id}&err={quote_plus(exc.message)}", status_code=303
        )


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
    return _submit_count(
        request=request,
        sheet_id=sheet_id,
        line_id=line_id,
        blind_counted_qty=blind_counted_qty,
        override_reason=override_reason,
        is_recount=(mode == "recount"),
    )


@router.post("/cycle-count/{sheet_id}/lines/{line_id}/recount")
def cycle_count_recount(
    request: Request,
    sheet_id: str,
    line_id: str,
    blind_counted_qty: str = Form(...),
    override_reason: str = Form(default=""),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    return _submit_count(
        request=request,
        sheet_id=sheet_id,
        line_id=line_id,
        blind_counted_qty=blind_counted_qty,
        override_reason=override_reason,
        is_recount=True,
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
        msg = quote_plus("Đã đóng phiếu và mở khóa vị trí")
        return RedirectResponse(url=f"/cycle-count?sheet_id={sheet_id}&msg={msg}", status_code=303)
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/cycle-count?sheet_id={sheet_id}&err={quote_plus(exc.message)}", status_code=303
        )
