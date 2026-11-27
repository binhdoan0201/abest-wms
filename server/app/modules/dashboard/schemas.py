"""ABEST WMS - Pydantic Schemas cho Phân hệ Tổng quan (Dashboard).

Số lượng hàng là chuỗi (chuẩn API mục 2); số đếm là số nguyên; tỷ lệ là phần trăm 1 chữ số
thập phân, `null` khi chưa có mẫu số.
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

AlertLevel = Literal["CRITICAL", "WARNING", "INFO"]


class DashboardAlert(BaseModel):
    """Cảnh báo đơn giản hiển thị trên app (A-12)."""

    level: AlertLevel
    code: str
    message: str
    count: int


class DashboardScope(BaseModel):
    warehouse_id: uuid.UUID | None = Field(None, description="null là gộp mọi kho")
    business_date: date
    generated_at: datetime


class OverdueTask(BaseModel):
    task_id: uuid.UUID
    task_type: str
    stage: str
    priority: str
    status: str
    ref_doc_type: str
    ref_doc_id: uuid.UUID
    zone_code: str | None
    assigned_to_name: str | None
    sla_due_at: datetime
    minutes_overdue: int


class DashboardTasksResponse(BaseModel):
    """Thẻ số task (TK-2.1)."""

    scope: DashboardScope
    total_tasks: int
    open_tasks: int
    unassigned_tasks: int
    in_progress_tasks: int
    overdue_tasks: int
    urgent_open_tasks: int
    completed_today: int
    on_time_rate_today: float | None
    by_status: dict[str, int]
    open_by_type: dict[str, int]
    open_by_stage: dict[str, int]
    overdue_list: list[OverdueTask]
    alerts: list[DashboardAlert]


class StockQuantities(BaseModel):
    available: str
    allocated: str
    counting: str
    locked: str
    damaged: str
    on_hand: str


class LocationUsage(BaseModel):
    total: int
    occupied: int
    empty: int
    locked: int
    occupancy_rate: float | None
    by_status: dict[str, int]


class ExpiringLot(BaseModel):
    sku_code: str
    sku_name: str
    lot_number: str
    expiry_date: date
    days_left: int
    qty_on_hand: str


class LowStockSku(BaseModel):
    sku_code: str
    sku_name: str
    min_stock_level: str
    qty_available: str


class DashboardInventoryResponse(BaseModel):
    scope: DashboardScope
    near_expiry_days: int
    skus_in_stock: int
    pallets_in_stock: int
    quantities: StockQuantities
    locations: LocationUsage
    expired_lots: int
    near_expiry_lots: int
    expiring_list: list[ExpiringLot]
    below_min_stock_skus: int
    below_min_stock_list: list[LowStockSku]
    alerts: list[DashboardAlert]


class InboundSummary(BaseModel):
    open_pos: int
    pos_due_today: int
    pos_late: int
    grns_today: int
    grns_closed_today: int
    grns_pending_approval: int


class OutboundSummary(BaseModel):
    open_orders: int
    open_by_status: dict[str, int]
    urgent_open: int
    late: int
    on_hold: int
    due_today: int
    due_today_shipped: int
    fulfillment_rate_today: float | None
    gi_confirmed_today: int
    erp_change_pending: int


class ApprovalSummary(BaseModel):
    pending_total: int
    pending_by_status: dict[str, int]
    overdue: int


class LateOrder(BaseModel):
    order_id: uuid.UUID
    erp_order_number: str
    order_type: str
    status: str
    is_urgent: bool
    cutoff_time: datetime
    minutes_late: int


class DashboardOrdersResponse(BaseModel):
    scope: DashboardScope
    inbound: InboundSummary
    outbound: OutboundSummary
    approvals: ApprovalSummary
    integration_failures: int
    late_orders: list[LateOrder]
    alerts: list[DashboardAlert]
