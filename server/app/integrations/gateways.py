"""ABEST WMS - Giao diện cổng kết nối hệ thống ngoài (ERP, TMS).

Service chỉ làm việc với giao diện `ErpGateway`, `TmsGateway`. Bản giả lập (`erp_mock.py`,
`tms_mock.py`) và bản thật sau này cùng giao diện, nên đổi bản thật không phải sửa service
(đặc tả mục 10.2, mục 9).
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

ErrorCategory = Literal["NONE", "BUSINESS_ERROR", "TECHNICAL_ERROR"]


@dataclass
class GatewayResult:
    """Kết quả một lần gọi hệ thống ngoài.

    - `BUSINESS_ERROR`: hệ thống ngoài từ chối dữ liệu (sai mã, sai trạng thái); thử lại vô ích
      cho đến khi sửa dữ liệu.
    - `TECHNICAL_ERROR`: lỗi mạng, hết thời gian chờ, hệ thống ngoài bận; được thử lại tự động.
    """

    ok: bool
    error_category: ErrorCategory = "NONE"
    message: str | None = None
    response: dict[str, Any] = field(default_factory=dict)


class ErpGateway(Protocol):
    """Cổng gửi chứng từ từ WMS sang ERP (GRN, GI, điều chỉnh tồn, phản hồi đổi/hủy đơn)."""

    def send(self, doc_type: str, payload: dict[str, Any]) -> GatewayResult:
        """Gửi một chứng từ; trả kết quả, không ném ngoại lệ."""
        ...


class TmsGateway(Protocol):
    """Cổng gọi hệ thống vận tải (TMS) để lấy vận đơn."""

    def request_waybill(self, payload: dict[str, Any]) -> GatewayResult:
        """Yêu cầu vận đơn; khi thành công `response["waybill_number"]` có số vận đơn."""
        ...
