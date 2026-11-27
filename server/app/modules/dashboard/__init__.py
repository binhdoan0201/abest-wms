"""ABEST WMS - Module Tổng quan (Dashboard)."""

from server.app.modules.dashboard.routers import router
from server.app.modules.dashboard.services import DashboardService

__all__ = ["DashboardService", "router"]
