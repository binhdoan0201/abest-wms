"""ABEST WMS - Module Xuất kho (Outbound)."""

from server.app.modules.integrations import register_erp_handler
from server.app.modules.outbound.erp_handlers import receive_outbound_order
from server.app.modules.outbound.routers import router
from server.app.modules.outbound.services import OutboundService

register_erp_handler("SO", receive_outbound_order)

__all__ = ["OutboundService", "receive_outbound_order", "router"]
