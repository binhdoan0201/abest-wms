"""ABEST WMS - Pydantic Schemas cho Phân hệ Tổng quan (Dashboard)."""

from typing import Any

from pydantic import BaseModel


class DashboardTasksResponse(BaseModel):
    """Số liệu tổng quan nhiệm vụ kho."""

    total_tasks: int = 0
    pending_tasks: int = 0
    in_progress_tasks: int = 0
    completed_today: int = 0
    by_type: dict[str, int] = {}


class DashboardInventoryResponse(BaseModel):
    """Số liệu tổng quan tồn kho."""

    total_skus: int = 0
    total_locations: int = 0
    occupied_locations: int = 0
    occupancy_rate: float = 0.0
    near_expiry_lots: int = 0


class DashboardOrdersResponse(BaseModel):
    """Số liệu tổng quan đơn nhập/xuất."""

    open_pos: int = 0
    open_sos: int = 0
    pending_approvals: int = 0
    fulfillment_rate_today: float = 0.0
    summary_details: dict[str, Any] = {}
