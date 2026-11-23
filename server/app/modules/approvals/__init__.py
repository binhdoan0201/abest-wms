"""ABEST WMS - Module Phê duyệt (Approvals).

Export các hàm công khai để module khác (inbound, cycle_count) gọi tạo yêu cầu duyệt
và đề xuất điều chỉnh tồn kho.
"""

from server.app.modules.approvals.services import (
    create_approval_request,
    propose_stock_adjustment,
)

__all__ = [
    "create_approval_request",
    "propose_stock_adjustment",
]
