"""ABEST WMS - Repositories cho Phân hệ Tổng quan (Dashboard).

Theo Quy tắc kiến trúc AST Mục 7.2:
Truy vấn nhiều bảng hoặc báo cáo (dashboard) đặt trong `repositories.py`, không viết trong Service.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.app.modules.inventory.models import InventoryBalance
from server.app.modules.tasks.models import Task


class DashboardRepository:
    """Repository thực hiện các truy vấn thống kê đa bảng phục vụ Dashboard."""

    @staticmethod
    def get_task_counts(db: Session, warehouse_id: uuid.UUID | None = None) -> dict[str, Any]:
        """Đếm số lượng nhiệm vụ kho theo trạng thái."""
        query = select(Task.status, func.count(Task.task_id)).group_by(Task.status)
        if warehouse_id:
            query = query.where(Task.warehouse_id == warehouse_id)
        results = db.execute(query).fetchall()
        return {status: count for status, count in results}

    @staticmethod
    def get_inventory_summary(db: Session, warehouse_id: uuid.UUID | None = None) -> dict[str, Any]:
        """Thống kê tổng quan số dư tồn kho."""
        query = select(
            func.count(func.distinct(InventoryBalance.sku_id)),
            func.count(func.distinct(InventoryBalance.location_id)),
            func.coalesce(func.sum(InventoryBalance.qty_available), 0),
        )
        if warehouse_id:
            query = query.where(InventoryBalance.warehouse_id == warehouse_id)
        row = db.execute(query).fetchone()
        if row:
            return {
                "distinct_skus": row[0],
                "occupied_locations": row[1],
                "total_qty_available": float(row[2]),
            }
        return {"distinct_skus": 0, "occupied_locations": 0, "total_qty_available": 0.0}
