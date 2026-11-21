"""ABEST WMS - Module Xuất kho (Outbound)."""

from server.app.modules.outbound.routers import router
from server.app.modules.outbound.services import OutboundService

__all__ = ["OutboundService", "router"]
