"""ABEST WMS - Module Dữ liệu nguồn (Master Data)."""

from server.app.modules.master_data.routers import router
from server.app.modules.master_data.services import MasterDataService

__all__ = ["MasterDataService", "router"]
