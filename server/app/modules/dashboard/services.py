"""ABEST WMS - Services cho Phân hệ Tổng quan (Dashboard)."""

import uuid

from sqlalchemy.orm import Session

from server.app.modules.dashboard.repositories import DashboardRepository
from server.app.modules.dashboard.schemas import (
    DashboardInventoryResponse,
    DashboardOrdersResponse,
    DashboardTasksResponse,
)


class DashboardService:
    """Service tổng hợp dữ liệu điều hành và KPI kho."""

    @staticmethod
    def get_task_kpi(db: Session, warehouse_id: uuid.UUID | None = None) -> DashboardTasksResponse:
        counts = DashboardRepository.get_task_counts(db, warehouse_id)
        return DashboardTasksResponse(
            total_tasks=sum(counts.values()),
            pending_tasks=counts.get("PENDING", 0),
            in_progress_tasks=counts.get("IN_PROGRESS", 0),
            by_type=counts,
        )

    @staticmethod
    def get_inventory_kpi(
        db: Session, warehouse_id: uuid.UUID | None = None
    ) -> DashboardInventoryResponse:
        summary = DashboardRepository.get_inventory_summary(db, warehouse_id)
        return DashboardInventoryResponse(
            total_skus=summary.get("distinct_skus", 0),
            occupied_locations=summary.get("occupied_locations", 0),
        )

    @staticmethod
    def get_orders_kpi(
        db: Session, warehouse_id: uuid.UUID | None = None
    ) -> DashboardOrdersResponse:
        return DashboardOrdersResponse(
            open_pos=0,
            open_sos=0,
            pending_approvals=0,
        )
