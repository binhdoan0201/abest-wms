"""ABEST WMS - Module Nhập kho (Inbound)."""

from server.app.modules.inbound.erp_handlers import receive_asn, receive_purchase_order
from server.app.modules.inbound.routers import router
from server.app.modules.inbound.services import InboundService
from server.app.modules.integrations import register_erp_handler

register_erp_handler("PO", receive_purchase_order)
register_erp_handler("ASN", receive_asn)

__all__ = ["InboundService", "router"]
