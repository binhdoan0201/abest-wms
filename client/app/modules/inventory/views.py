"""Web Controller cho phân hệ Quản lý Tồn kho (Inventory) – tra cứu QL-1.1 đến QL-1.4.

- Tab «Số dư»: lọc theo SKU, vị trí, lô; hiện mã, tên SKU, mã vị trí, số lô, hạn dùng, số ngày
  còn lại và tồn theo 5 trạng thái. Chỉ hiện dòng còn hàng.
- Tab «Lịch sử giao dịch» (thukho, quanly): sổ cái biến động tồn, lọc theo SKU.

API tồn kho trả ID; client tra danh mục (`/skus`, `/locations`, `/lots`) để hiện mã dễ đọc.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu, get_current_user
from client.app.core.formatting import format_qty
from client.app.core.session import get_session_token

router = APIRouter(tags=["Inventory Views"])

HISTORY_ROLES = ("thukho", "quanly")
NEAR_EXPIRY_DAYS = 30
VN_TZ = timezone(timedelta(hours=7))
TX_LABELS = {
    "RECEIVE": "Nhập kho",
    "PUTAWAY": "Cất hàng",
    "ALLOCATE": "Giữ hàng",
    "DEALLOCATE": "Nhả giữ",
    "PICK": "Soạn",
    "PICK_TO_STAGING": "Soạn ra khu tập kết",
    "SHIP_GI": "Xuất kho",
    "RETURN_TO_SHELF": "Trả về kệ",
    "INTERNAL_MOVE": "Chuyển nội bộ",
    "LOCK_COUNT": "Khóa kiểm kê",
    "CYCLE_COUNT": "Điều chỉnh kiểm kê",
    "ADJUSTMENT": "Điều chỉnh",
    "SCRAP": "Hủy hàng",
    "RETURN_IN": "Nhận trả về",
}


def get_templates(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


def _safe_get(api: ApiClient, path: str, params: dict[str, Any] | None = None) -> list[Any]:
    """Danh sách từ API; lỗi quyền hoặc lỗi khác thì trả rỗng (trang vẫn hiển thị)."""
    try:
        data = api.get(path, params=params).get("data")
    except ClientApiError:
        return []
    return data if isinstance(data, list) else []


def _lookups(api: ApiClient) -> dict[str, dict[str, Any]]:
    """Bảng tra ID → bản ghi danh mục để hiện mã, tên."""
    skus = _safe_get(api, "/skus", {"page_size": 100})
    locations = _safe_get(api, "/locations", {"page_size": 100})
    lots = _safe_get(api, "/lots")
    return {
        "skus": {s["sku_id"]: s for s in skus},
        "locations": {loc["location_id"]: loc for loc in locations},
        "lots": {lot["lot_id"]: lot for lot in lots},
    }


def _qty(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except ArithmeticError:
        return Decimal("0")


def _fmt(value: Decimal) -> str:
    return format_qty(value)


def _balance_rows(balances: list[Any], maps: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    today = date.today()
    rows = []
    for b in balances:
        available, allocated = _qty(b.get("qty_available")), _qty(b.get("qty_allocated"))
        counting, locked = _qty(b.get("qty_counting")), _qty(b.get("qty_locked"))
        damaged = _qty(b.get("qty_damaged"))
        on_hand = available + allocated + counting + locked
        if on_hand + damaged <= 0:
            continue
        sku = maps["skus"].get(b.get("sku_id"), {})
        loc = maps["locations"].get(b.get("location_id"), {})
        lot = maps["lots"].get(b.get("lot_id"), {}) if b.get("lot_id") else {}
        expiry = lot.get("expiry_date")
        days_left = (date.fromisoformat(expiry) - today).days if expiry else None
        rows.append(
            {
                "sku_code": sku.get("sku_code") or str(b.get("sku_id"))[:8],
                "sku_name": sku.get("sku_name", ""),
                "base_uom": sku.get("base_uom", ""),
                "location_code": loc.get("location_code") or str(b.get("location_id"))[:8],
                "lot_number": lot.get("lot_number") or ("–" if not b.get("lot_id") else "…"),
                "expiry_date": expiry,
                "days_left": days_left,
                "expired": days_left is not None and days_left < 0,
                "near_expiry": days_left is not None and 0 <= days_left <= NEAR_EXPIRY_DAYS,
                "available": _fmt(available),
                "allocated": _fmt(allocated),
                "counting": _fmt(counting),
                "locked": _fmt(locked),
                "damaged": _fmt(damaged),
                "on_hand": _fmt(on_hand),
                "is_locked": counting > 0 or locked > 0,
            }
        )
    rows.sort(key=lambda r: (r["sku_code"], r["expiry_date"] or "9999", r["location_code"]))
    return rows


def _history_rows(txs: list[Any], maps: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for t in txs:
        sku = maps["skus"].get(t.get("sku_id"), {})
        lot = maps["lots"].get(t.get("lot_id"), {}) if t.get("lot_id") else {}

        def loc_code(loc_id: Any) -> str:
            if not loc_id:
                return "–"
            return str(maps["locations"].get(loc_id, {}).get("location_code") or str(loc_id)[:8])

        performed = t.get("performed_at")
        when = (
            datetime.fromisoformat(performed).astimezone(VN_TZ).strftime("%d/%m %H:%M")
            if performed
            else ""
        )
        qty = _qty(t.get("qty_change"))
        rows.append(
            {
                "when": when,
                "tx_type": t.get("tx_type"),
                "tx_label": TX_LABELS.get(str(t.get("tx_type")), t.get("tx_type")),
                "sku_code": sku.get("sku_code") or str(t.get("sku_id"))[:8],
                "lot_number": lot.get("lot_number") or "–",
                "from_code": loc_code(t.get("from_location_id")),
                "to_code": loc_code(t.get("to_location_id")),
                "qty_change": ("+" if qty > 0 else "") + _fmt(qty),
                "positive": qty > 0,
                "ref_doc_type": t.get("ref_doc_type"),
            }
        )
    return rows


def _filters(raw: dict[str, Any]) -> dict[str, str]:
    return {k: str(raw.get(k) or "") for k in ("sku_id", "location_id", "lot_id")}


def _load(token: str | None, user: dict[str, Any], filters: dict[str, str], tab: str) -> Any:
    api = ApiClient(token=token)
    maps = _lookups(api)
    params = {k: v for k, v in filters.items() if v}
    balances = api.get("/inventory/balances", params=params).get("data", [])
    can_history = user.get("role_code") in HISTORY_ROLES
    history: list[dict[str, Any]] = []
    if can_history and tab == "history":
        tx_params: dict[str, Any] = {"limit": 100}
        if filters["sku_id"]:
            tx_params["sku_id"] = filters["sku_id"]
        history = _history_rows(_safe_get(api, "/inventory/transactions", tx_params), maps)
    lots = list(maps["lots"].values())
    if filters["sku_id"]:
        lots = [lot for lot in lots if lot.get("sku_id") == filters["sku_id"]]
    return {
        "balances": _balance_rows(balances, maps),
        "history": history,
        "can_history": can_history,
        "tab": tab if can_history else "balances",
        "filters": filters,
        "sku_options": sorted(maps["skus"].values(), key=lambda s: s.get("sku_code", "")),
        "location_options": sorted(
            maps["locations"].values(), key=lambda loc: loc.get("location_code", "")
        ),
        "lot_options": sorted(lots, key=lambda lot: lot.get("lot_number", "")),
    }


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Trang tra cứu tồn kho: số dư có lọc, lô và hạn dùng; lịch sử giao dịch."""
    templates = get_templates(request)
    menu = build_user_menu(user)
    filters = _filters(dict(request.query_params))
    tab = request.query_params.get("tab", "balances")
    base = {"request": request, "user": user, "menu": menu, "active_menu": "inventory"}
    try:
        view = _load(get_session_token(request), user, filters, tab)
        return templates.TemplateResponse(
            request=request, name="inventory/index.html", context={**base, **view}
        )
    except ClientApiError as exc:
        if exc.http_status == 403:
            return templates.TemplateResponse(
                request=request,
                name="_base/403.html",
                context={**base, "error_msg": exc.message, "error_code": exc.code},
                status_code=403,
            )
        empty = {
            "balances": [],
            "history": [],
            "can_history": False,
            "tab": "balances",
            "filters": filters,
            "sku_options": [],
            "location_options": [],
            "lot_options": [],
        }
        return templates.TemplateResponse(
            request=request,
            name="inventory/index.html",
            context={**base, **empty, "api_error": {"code": exc.code, "message": exc.message}},
            status_code=exc.http_status,
        )


@router.post("/inventory/refresh", response_class=HTMLResponse)
def inventory_refresh_htmx(
    request: Request,
    sku_id: str = Form(default=""),
    location_id: str = Form(default=""),
    lot_id: str = Form(default=""),
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """HTMX: làm mới bảng số dư theo bộ lọc hiện tại."""
    templates = get_templates(request)
    filters = _filters({"sku_id": sku_id, "location_id": location_id, "lot_id": lot_id})
    try:
        view = _load(get_session_token(request), user, filters, "balances")
    except ClientApiError:
        view = {"balances": []}
    return templates.TemplateResponse(
        request=request,
        name="inventory/_table.html",
        context={"request": request, "balances": view["balances"]},
    )
