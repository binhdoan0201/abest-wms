"""Định dạng số cho giao diện theo kiểu Việt Nam.

API trả số lượng dạng chuỗi thập phân 3 chữ số (`"180.000"`). Hiện nguyên chuỗi đó, người Việt đọc
thành 180 nghìn, nên mọi số lượng, số tiền trên trang đi qua các filter ở đây:

- `qty`: `180.000` → `180`, `1234.5` → `1.234,5`
- `qty_input`: giá trị điền sẵn vào ô nhập, vẫn gửi lại được cho API: `8.000` → `8`, `2.500` → `2.5`
- `vnd`: `450000.00` → `450.000 ₫`
- `vn_datetime`: `2026-11-28T05:40:26Z` → `28/11/2026 12:40` (giờ Việt Nam)
- `vi_label`: mã trạng thái, loại hồ sơ, cấp duyệt → nhãn tiếng Việt
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi.templating import Jinja2Templates


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _vi_number(number: Decimal, max_decimals: int) -> str:
    text = f"{number:,.{max_decimals}f}"
    if max_decimals:
        text = text.rstrip("0").rstrip(".")
    # Đổi kiểu Anh (1,234.5) sang kiểu Việt (1.234,5)
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def format_qty(value: Any) -> str:
    """Số lượng: bỏ phần thập phân thừa, phân cách nghìn bằng dấu chấm."""
    number = _to_decimal(value)
    if number is None:
        return "" if value is None else str(value)
    return _vi_number(number, 3)


def format_qty_input(value: Any) -> str:
    """Giá trị cho ô nhập: bỏ số 0 thừa, giữ dấu chấm thập phân để API đọc được."""
    number = _to_decimal(value)
    if number is None:
        return "" if value is None else str(value)
    text = f"{number:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def format_vnd(value: Any) -> str:
    """Số tiền VND làm tròn đồng: `450.000 ₫`."""
    number = _to_decimal(value)
    if number is None:
        return "" if value is None else str(value)
    return f"{_vi_number(number, 0)} ₫"


VN_TZ = timezone(timedelta(hours=7))


def format_vn_datetime(value: Any) -> str:
    """Thời điểm ISO (thường là UTC) → `dd/mm/yyyy HH:mm` giờ Việt Nam."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M")


VI_LABELS: dict[str, str] = {
    # Loại hồ sơ duyệt
    "GRN_DISCREPANCY": "Chênh lệch nhận hàng",
    "CYCLE_COUNT_DIFF": "Chênh lệch kiểm kê",
    "STOCK_ADJUSTMENT": "Điều chỉnh tồn",
    "STOCK_SCRAP": "Hủy hàng hỏng",
    "OVERTIME_REQUEST": "Đề xuất tăng ca",
    # Cấp duyệt
    "D1_THUKHO": "D1 · Thủ kho",
    "D2_QUANLY": "D2 · Quản lý",
    "D3_BGD": "D3 · Ban giám đốc",
    "AUTO_TOLERANCE_Z": "Tự duyệt (trong dung sai)",
    # Trạng thái hồ sơ
    "PENDING_D1": "Chờ thủ kho",
    "PENDING_D2": "Chờ quản lý",
    "PENDING_D3": "Chờ BGĐ",
    "NEED_INFO": "Chờ đếm lại / bổ sung",
    "APPROVED": "Đã duyệt",
    "REJECTED": "Từ chối",
    "EXPIRED": "Quá hạn",
    "SUPERSEDED": "Đã thay bằng lần đếm lại",
    # Trạng thái thực thi
    "WAITING_EXECUTION": "Chờ thực thi",
    "EXECUTED": "Đã thực thi",
    "EXECUTION_FAILED": "Thực thi lỗi",
    "NOT_APPLICABLE": "Không áp dụng",
    "PENDING": "Chờ",
    # Thao tác trong lịch sử
    "SUBMITTED": "Gửi duyệt",
    "APPROVE": "Phê duyệt",
    "REJECT": "Từ chối",
    "ESCALATE_NEXT_TIER": "Chuyển cấp trên",
    "REQUEST_RECOUNT": "Yêu cầu đếm lại",
    "RETURN_FOR_INFO": "Yêu cầu bổ sung",
    "RESUBMIT_INFO": "Gửi bổ sung",
    "SUPERSEDED_BY_RECOUNT": "Thay bằng lần đếm lại",
    "AUTO_ESCALATE_SLA": "Tự chuyển cấp (quá SLA)",
    "AUTO_APPROVED_Z": "Tự duyệt (trong dung sai)",
    # Trạng thái GRN & PO
    "DRAFT": "Nháp",
    "COUNTING": "Đang kiểm đếm",
    "DISCREPANCY": "Có chênh lệch",
    "RECOUNTING": "Đang đếm lại",
    "CLOSED": "Đã đóng",
    "SYNCED_ERP": "Đã đồng bộ ERP",
    "RECEIVING": "Đang nhận hàng",
    "PARTIAL_RECEIVED": "Nhận một phần",
    "FULLY_RECEIVED": "Đã nhận đủ",
    "CANCELLED": "Đã hủy",
    # Nhãn theo ngữ cảnh (context:code)
    "PO:PENDING": "Chờ nhận hàng",
    "PO:CLOSED": "Đã đóng",
    "GRN:CLOSED": "Đã hoàn tất",
    "CC:CLOSED": "Đã đóng",
    "CC:OPEN": "Đang mở",
    "CC:PENDING": "Chờ đếm",
    # Trạng thái kiểm kê (Cycle Count)
    "IN_PROGRESS": "Đang kiểm kê",
    "PENDING_APPROVAL": "Chờ phê duyệt",
    "RECOUNT_REQUIRED": "Yêu cầu đếm lại",
    "ADJUSTED": "Đã điều chỉnh tồn",
}


def vi_label(value: Any, context: str | None = None) -> str:
    """Nhãn tiếng Việt cho mã; ưu tiên context:code rồi mới tra mã chung."""
    if value is None:
        return ""
    code = str(value)
    if context:
        scoped = VI_LABELS.get(f"{context}:{code}")
        if scoped is not None:
            return scoped
    return VI_LABELS.get(code, code)


def register_filters(templates: Jinja2Templates) -> None:
    templates.env.filters["qty"] = format_qty
    templates.env.filters["qty_input"] = format_qty_input
    templates.env.filters["vnd"] = format_vnd
    templates.env.filters["vn_datetime"] = format_vn_datetime
    templates.env.filters["vi_label"] = vi_label
