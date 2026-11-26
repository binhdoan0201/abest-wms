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


def _safe_dict(api: ApiClient, path: str) -> dict[str, Any] | None:
    try:
        raw = api.get(path).get("data")
        if isinstance(raw, dict):
            return raw
    except ClientApiError:
        pass
    return None


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

    pos: list[dict[str, Any]] = []
    grns: list[dict[str, Any]] = []
    selected_grn: dict[str, Any] | None = None
    sku_options: list[dict[str, Any]] = []
    reason_codes: list[dict[str, Any]] = []
    sku_code_map: dict[str, str] = {}
    staged_pallets: list[dict[str, Any]] = []
    putaway_version_no = 1
    suggestions: list[dict[str, Any]] = []
    api_err = err

    if "NH-1" in perms or "NH-5" in perms:
        pos = _safe_list(api, "/purchase-orders", {"page_size": 100})
        try:
            grns = api.get("/grns").get("data", [])
        except ClientApiError as exc:
            api_err = exc.message
        if grn_id:
            try:
                selected_grn = api.get(f"/grns/{grn_id}").get("data")
            except ClientApiError as exc:
                api_err = exc.message

        all_skus = _safe_list(api, "/skus", {"page_size": 200})
        for s in all_skus:
            sid = str(s.get("sku_id") or "")
            scode = str(s.get("sku_code") or "")
            sname = str(s.get("sku_name") or s.get("name") or "")
            if sid:
                sku_code_map[sid] = scode or sid
            if sid or scode:
                sku_options.append(
                    {
                        "sku_id": sid,
                        "sku_code": scode,
                        "sku_name": sname,
                        "uom_code": s.get("uom_code") or s.get("base_uom") or "",
                        "qty_expected": None,
                    }
                )

        reason_codes = _safe_list(api, "/reason-codes", {"is_active": "true", "page_size": 100})

        if isinstance(selected_grn, dict):
            po_id_val = selected_grn.get("po_id")
            if po_id_val:
                po_detail = _safe_dict(api, f"/purchase-orders/{po_id_val}")
                po_lines = po_detail.get("lines", []) if isinstance(po_detail, dict) else []
                if isinstance(po_lines, list) and po_lines:
                    po_sku_opts: list[dict[str, Any]] = []
                    for ln in po_lines:
                        if not isinstance(ln, dict):
                            continue
                        sid = str(ln.get("sku_id") or "")
                        scode = str(ln.get("sku_code") or sku_code_map.get(sid, ""))
                        sname = str(ln.get("sku_name") or "")
                        if sid and scode:
                            sku_code_map[sid] = scode
                        po_sku_opts.append(
                            {
                                "sku_id": sid,
                                "sku_code": scode,
                                "sku_name": sname,
                                "uom_code": ln.get("uom_code") or "",
                                "qty_expected": ln.get("qty_ordered"),
                            }
                        )
                    if po_sku_opts:
                        sku_options = po_sku_opts

            for ln in (
                selected_grn.get("lines", []) if isinstance(selected_grn.get("lines"), list) else []
            ):
                if isinstance(ln, dict):
                    sid = str(ln.get("sku_id") or "")
                    if sid and sid not in sku_code_map:
                        sku_code_map[sid] = str(ln.get("sku_code") or sid)

    if "CAT-1" in perms:
        all_pallets = _safe_list(api, "/pallets")
        staged_pallets = [p for p in all_pallets if str(p.get("status") or "").upper() == "STAGED"]
        active_pallet_id = (pallet_id or "").strip()
        if active_pallet_id:
            p_detail = _safe_dict(api, f"/pallets/{active_pallet_id}")
            if isinstance(p_detail, dict) and p_detail.get("version_no") is not None:
                try:
                    putaway_version_no = int(p_detail["version_no"])
                except (TypeError, ValueError):
                    putaway_version_no = 1
            else:
                for p in staged_pallets:
                    if (
                        str(p.get("pallet_id") or "") == active_pallet_id
                        and p.get("version_no") is not None
                    ):
                        try:
                            putaway_version_no = int(p["version_no"])
                        except (TypeError, ValueError):
                            putaway_version_no = 1
                        break
            try:
                raw_suggestions = (
                    api.post("/putaway/suggest", json_data={"pallet_id": active_pallet_id})
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
            "sku_options": sku_options,
            "reason_codes": reason_codes,
            "sku_code_map": sku_code_map,
            "staged_pallets": staged_pallets,
            "putaway_version_no": putaway_version_no,
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
        grn_id = data.get("grn_id", "")
        msg = quote_plus("Đã mở phiếu nhập kho")
        target = f"/inbound?grn_id={grn_id}&msg={msg}" if grn_id else f"/inbound?msg={msg}"
        return RedirectResponse(url=target, status_code=303)
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
def inbound_recount_grn(
    request: Request,
    grn_id: str,
    version_no: int = Form(1),
    grn_line_id: list[str] = Form(default=[]),
    qty_actual: list[str] = Form(default=[]),
    qty_damaged: list[str] = Form(default=[]),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    api = ApiClient(token=get_session_token(request))
    line_ids = [x.strip() for x in grn_line_id if x.strip()]
    qty_actuals = [x.strip() for x in qty_actual]
    qty_damageds = [x.strip() for x in qty_damaged]

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
