"""ABEST WMS - Module Tích hợp (Integrations): ERP mock, TMS mock, nhật ký đồng bộ.

Hàm công khai cho module khác:
- `register_erp_handler(doc_type, handler)`: `inbound` đăng ký PO, ASN; `outbound` đăng ký SO.
- `enqueue_to_erp(db, warehouse_id, doc_type, doc_id, payload)`: xếp chứng từ chờ gửi ERP.
- `request_waybill(db, warehouse_id, gi_id, payload)`, `get_waybill(db, gi_id)`: vận đơn TMS.
"""

from server.app.modules.integrations.routers import router
from server.app.modules.integrations.services import (
    IntegrationService,
    enqueue_to_erp,
    get_waybill,
    register_erp_handler,
    request_waybill,
)

__all__ = [
    "IntegrationService",
    "enqueue_to_erp",
    "get_waybill",
    "register_erp_handler",
    "request_waybill",
    "router",
]
