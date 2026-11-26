"""Web Controller cho phân hệ Nhập kho (Inbound - B-08)."""

from typing import Any
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user
from client.app.core.session import get_session_token

router = APIRouter(tags=["Inbound Views"])


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


@router.get("/inbound", response_class=HTMLResponse)
def inbound_index(
    request: Request,
    grn_id: str | None = None,
    pallet_id: str | None = None,
    msg: str | None = None,
    err: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    menu = build_user_menu(user)
    perms = _perms(user)
    if "NH-1" not in perms and "NH-5" not in perms and "CAT-1" not in perms:
        return _tpl(request).TemplateResponse(
            request=request,
            name="_base/403.html",
            context={
                "request": request,
                "user": user,
                "menu": menu,
                "error_msg": "Không có quyền Nhập kho",
            },
            status_code=403,
        )

    pos, grns, selected_grn, suggestions, api_err = [], [], None, [], err
    if "NH-1" in perms or "NH-5" in perms:
        try:
            pos = api.get("/purchase-orders").get("data", [])
            grns = api.get("/grns").get("data", [])
            if grn_id:
                selected_grn = api.get(f"/grns/{grn_id}").get("data")
        except ClientApiError as exc:
            api_err = exc.message

    if pallet_id and "CAT-1" in perms:
        try:
            raw_suggestions = (
                api.post("/putaway/suggest", json_data={"pallet_id": pallet_id})
                .get("data", {})
                .get("suggestions", [])
            )
            suggestions = raw_suggestions[:5]
        except ClientApiError as exc:
            api_err = exc.message

    return _tpl(request).TemplateResponse(
        request=request,
        name="inbound/index.html",
        context={
            "request": request,
            "user": user,
            "menu": menu,
            "active_menu": "inbound",
            "perms": perms,
            "pos": pos,
            "grns": grns,
            "selected_grn": selected_grn,
            "pallet_id": pallet_id or "",
            "suggestions": suggestions,
            "flash_msg": msg,
            "api_error": api_err,
        },
    )


@router.post("/inbound/grns/create")
def inbound_create_grn(
    request: Request,
    po_id: str = Form(default=""),
    asn_id: str = Form(default=""),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    payload: dict[str, Any] = {
        "po_id": po_id.strip() or None,
        "asn_id": asn_id.strip() or None,
    }
    try:
        data = api.post("/grns", json_data=payload).get("data", {})
        msg = quote_plus("Đã mở phiếu nhập kho")
        return RedirectResponse(
            url=f"/inbound?grn_id={data.get('grn_id', '')}&msg={msg}",
            status_code=303,
        )
    except ClientApiError as exc:
        return RedirectResponse(url=f"/inbound?err={quote_plus(exc.message)}", status_code=303)


@router.post("/inbound/grns/{grn_id}/lines")
def inbound_add_line(
    request: Request,
    grn_id: str,
    sku_id: str = Form(...),
    lot_number: str = Form(default=""),
    expiry_date: str = Form(default=""),
    uom_code: str = Form(...),
    qty_actual: str = Form(...),
    qty_damaged: str = Form(default="0"),
    reason_code: str = Form(default=""),
    version_no: int = Form(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    payload: dict[str, Any] = {
        "sku_id": sku_id.strip(),
        "lot_number": lot_number.strip() or None,
        "expiry_date": expiry_date.strip() or None,
        "uom_code": uom_code.strip(),
        "qty_actual": qty_actual.strip(),
        "qty_damaged": qty_damaged.strip() or "0",
        "reason_code": reason_code.strip() or None,
        "version_no": version_no,
    }
    try:
        api.post(f"/grns/{grn_id}/lines", json_data=payload)
        return RedirectResponse(
            url=f"/inbound?grn_id={grn_id}&msg={quote_plus('Đã ghi dòng kiểm đếm')}",
            status_code=303,
        )
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/inbound?grn_id={grn_id}&err={quote_plus(exc.message)}", status_code=303
        )


@router.post("/inbound/grns/{grn_id}/submit")
def inbound_submit_grn(
    request: Request,
    grn_id: str,
    version_no: int = Form(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    try:
        res = api.post(f"/grns/{grn_id}/submit", json_data={"version_no": version_no}).get(
            "data", {}
        )
        msg = quote_plus(f"Kết quả nộp: {res.get('status', '')}")
        return RedirectResponse(url=f"/inbound?grn_id={grn_id}&msg={msg}", status_code=303)
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/inbound?grn_id={grn_id}&err={quote_plus(exc.message)}", status_code=303
        )


@router.post("/inbound/grns/{grn_id}/recount")
async def inbound_recount_grn(
    request: Request,
    grn_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    form = await request.form()
    version_no = int(str(form.get("version_no", 1)))
    line_ids = [str(x).strip() for x in form.getlist("grn_line_id") if str(x).strip()]
    qty_actuals = [str(x).strip() for x in form.getlist("qty_actual")]
    qty_damageds = [str(x).strip() for x in form.getlist("qty_damaged")]

    lines: list[dict[str, Any]] = []
    for idx, line_id in enumerate(line_ids):
        lines.append(
            {
                "grn_line_id": line_id,
                "qty_actual": qty_actuals[idx] if idx < len(qty_actuals) else "0",
                "qty_damaged": (
                    qty_damageds[idx] if idx < len(qty_damageds) and qty_damageds[idx] else "0"
                ),
            }
        )

    try:
        res = api.post(
            f"/grns/{grn_id}/recount",
            json_data={"version_no": version_no, "lines": lines},
        ).get("data", {})
        msg = quote_plus(f"Đã ghi nhận đếm lại GRN (Trạng thái: {res.get('status', '')})")
        return RedirectResponse(url=f"/inbound?grn_id={grn_id}&msg={msg}", status_code=303)
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/inbound?grn_id={grn_id}&err={quote_plus(exc.message)}", status_code=303
        )


@router.post("/inbound/grns/{grn_id}/complete")
def inbound_complete_grn(
    request: Request,
    grn_id: str,
    version_no: int = Form(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    try:
        api.post(f"/grns/{grn_id}/complete", json_data={"version_no": version_no})
        msg = quote_plus("Đã hoàn tất nhập tồn và tạo Pallet")
        return RedirectResponse(url=f"/inbound?grn_id={grn_id}&msg={msg}", status_code=303)
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/inbound?grn_id={grn_id}&err={quote_plus(exc.message)}", status_code=303
        )


@router.post("/inbound/pallets/{pallet_id}/putaway")
def inbound_confirm_putaway(
    request: Request,
    pallet_id: str,
    location_id: str = Form(...),
    version_no: int = Form(default=1),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    try:
        api.post(
            f"/pallets/{pallet_id}/putaway",
            json_data={"location_id": location_id.strip(), "version_no": version_no},
        )
        msg = quote_plus("Đã xác nhận cất pallet lên kệ thành công")
        return RedirectResponse(url=f"/inbound?msg={msg}", status_code=303)
    except ClientApiError as exc:
        return RedirectResponse(
            url=f"/inbound?pallet_id={pallet_id}&err={quote_plus(exc.message)}", status_code=303
        )
