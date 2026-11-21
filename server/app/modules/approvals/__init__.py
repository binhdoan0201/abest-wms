"""ABEST WMS - Module Phê duyệt (Approvals)."""

from server.app.modules.approvals.routers import router
from server.app.modules.approvals.services import ApprovalsService

__all__ = ["ApprovalsService", "router"]
