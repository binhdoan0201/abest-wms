"""ABEST WMS - ERP giả lập (chỉ môi trường dev và demo).

Mặc định nhận mọi chứng từ. Có thể cấu hình cho N lần gọi tiếp theo trả lỗi kỹ thuật hoặc lỗi
nghiệp vụ để demo và kiểm thử cơ chế thử lại (`configure_failures`).
"""

import uuid
from typing import Any

from server.app.integrations.gateways import ErrorCategory, GatewayResult


class MockErpGateway:
    """ERP giả lập: trả mã tham chiếu ERP cho mỗi chứng từ nhận được."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self._fail_category: ErrorCategory = "NONE"
        self._fail_remaining = 0

    def configure_failures(self, category: ErrorCategory, times: int) -> None:
        """Cho `times` lần gọi tiếp theo thất bại với loại lỗi `category` (NONE để tắt)."""
        self._fail_category = category
        self._fail_remaining = times if category != "NONE" else 0

    def send(self, doc_type: str, payload: dict[str, Any]) -> GatewayResult:
        """Nhận chứng từ; thất bại theo cấu hình nếu có."""
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            if self._fail_category == "BUSINESS_ERROR":
                return GatewayResult(
                    ok=False,
                    error_category="BUSINESS_ERROR",
                    message=f"ERP mock từ chối chứng từ {doc_type}",
                )
            return GatewayResult(
                ok=False,
                error_category="TECHNICAL_ERROR",
                message="ERP mock không phản hồi (giả lập hết thời gian chờ)",
            )

        self.sent.append((doc_type, payload))
        return GatewayResult(
            ok=True, response={"erp_ref": f"ERP-{doc_type}-{uuid.uuid4().hex[:8].upper()}"}
        )


_erp_gateway = MockErpGateway()


def get_erp_gateway() -> MockErpGateway:
    """Trả cổng ERP đang dùng (dev: bản giả lập dùng chung toàn tiến trình)."""
    return _erp_gateway
