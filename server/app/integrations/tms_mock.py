"""ABEST WMS - TMS giả lập (chỉ môi trường dev và demo).

Cấp số vận đơn cho phiếu xuất. Có thể cấu hình lỗi giống `erp_mock` để thử đơn chờ vận đơn
(`WAITING_WAYBILL`) và cơ chế thử lại.
"""

import random
from typing import Any

from server.app.integrations.gateways import ErrorCategory, GatewayResult


class MockTmsGateway:
    """TMS giả lập: trả số vận đơn dạng `TMS` + 10 chữ số."""

    def __init__(self) -> None:
        self._fail_category: ErrorCategory = "NONE"
        self._fail_remaining = 0

    def configure_failures(self, category: ErrorCategory, times: int) -> None:
        """Cho `times` lần gọi tiếp theo thất bại với loại lỗi `category` (NONE để tắt)."""
        self._fail_category = category
        self._fail_remaining = times if category != "NONE" else 0

    def request_waybill(self, payload: dict[str, Any]) -> GatewayResult:
        """Cấp vận đơn; thất bại theo cấu hình nếu có."""
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            return GatewayResult(
                ok=False,
                error_category=self._fail_category,
                message="TMS mock không cấp được vận đơn",
            )
        waybill = f"TMS{random.randint(0, 9_999_999_999):010d}"  # noqa: S311 - số giả lập
        return GatewayResult(ok=True, response={"waybill_number": waybill})


_tms_gateway = MockTmsGateway()


def get_tms_gateway() -> MockTmsGateway:
    """Trả cổng TMS đang dùng (dev: bản giả lập dùng chung toàn tiến trình)."""
    return _tms_gateway
