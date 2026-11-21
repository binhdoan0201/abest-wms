"""ABEST WMS - Module Nhập kho (Inbound)."""

from server.app.modules.inbound.routers import router
from server.app.modules.inbound.services import InboundService

__all__ = ["InboundService", "router"]
