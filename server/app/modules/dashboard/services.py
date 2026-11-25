"""ABEST WMS - Services cho Phân hệ Tổng quan (Dashboard).

Dashboard chỉ đọc (A-12): thẻ số task (TK-2.1), tồn kho, đơn trong ngày và cảnh báo đơn giản.
Phạm vi kho: người dùng gắn kho chỉ xem kho của mình (hỏi kho khác trả 404); người dùng không gắn
kho xem kho được chọn, hoặc gộp mọi kho khi không chọn.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from server.app.core.rbac import UserContext, enforce_warehouse_scope
from server.app.modules.dashboard.repositories import DashboardRepository
from server.app.modules.dashboard.schemas import (
    ApprovalSummary,
    DashboardAlert,
    DashboardInventoryResponse,
    DashboardOrdersResponse,
    DashboardScope,
    DashboardTasksResponse,
    ExpiringLot,
    InboundSummary,
    LateOrder,
    LocationUsage,
    LowStockSku,
    OutboundSummary,
    OverdueTask,
    StockQuantities,
)

QTY_PLACES = Decimal("0.001")
OCCUPIED_LOCATION_STATUSES = ("PARTIAL", "FULL")
LOCKED_LOCATION_STATUSES = ("COUNTING_LOCKED", "MAINTENANCE_LOCKED", "DAMAGED_HOLD")
DEFAULT_NEAR_EXPIRY_DAYS = 30


def _qty(value: Any) -> str:
    return str(Decimal(value or 0).quantize(QTY_PLACES))


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator * 100 / denominator, 1)


def _alert(level: str, code: str, message: str, count: int) -> DashboardAlert | None:
    if count <= 0:
        return None
    return DashboardAlert(level=level, code=code, message=message, count=count)  # type: ignore[arg-type]


def _alerts(*items: DashboardAlert | None) -> list[DashboardAlert]:
    order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    return sorted((a for a in items if a is not None), key=lambda a: order[a.level])


def resolve_warehouse(user: UserContext, requested: uuid.UUID | None) -> uuid.UUID | None:
    """Kho được xem: kho của người dùng, hoặc kho chọn khi người dùng không gắn kho."""
    if user.warehouse_id is not None:
        if requested is not None:
            enforce_warehouse_scope(user, requested)
        return user.warehouse_id
    return requested


def _scope(db: Session, warehouse_id: uuid.UUID | None) -> DashboardScope:
    return DashboardScope(
        warehouse_id=warehouse_id,
        business_date=DashboardRepository.today(db),
        generated_at=datetime.now(timezone.utc),
    )


class DashboardService:
    """Service tổng hợp dữ liệu điều hành và cảnh báo kho."""

    @staticmethod
    def get_tasks(
        db: Session, user: UserContext, warehouse_id: uuid.UUID | None = None
    ) -> DashboardTasksResponse:
        wh = resolve_warehouse(user, warehouse_id)
        c = DashboardRepository.task_counts(db, wh)
        by_status: dict[str, int] = c["by_status"]
        open_total = sum(c["open_by_type"].values())
        unassigned = by_status.get("UNASSIGNED", 0)
        alerts = _alerts(
            _alert(
                "CRITICAL",
                "TASK_OVERDUE",
                f"{c['overdue']} task đã quá hạn xử lý (SLA)",
                c["overdue"],
            ),
            _alert(
                "WARNING",
                "TASK_URGENT_OPEN",
                f"{c['urgent_open']} task khẩn chưa hoàn tất",
                c["urgent_open"],
            ),
            _alert("INFO", "TASK_UNASSIGNED", f"{unassigned} task chưa giao", unassigned),
        )
        return DashboardTasksResponse(
            scope=_scope(db, wh),
            total_tasks=sum(by_status.values()),
            open_tasks=open_total,
            unassigned_tasks=unassigned,
            in_progress_tasks=by_status.get("IN_PROGRESS", 0),
            overdue_tasks=c["overdue"],
            urgent_open_tasks=c["urgent_open"],
            completed_today=c["completed_today"],
            on_time_rate_today=_rate(c["completed_today_on_time"], c["completed_today"]),
            by_status=by_status,
            open_by_type=c["open_by_type"],
            open_by_stage=c["open_by_stage"],
            overdue_list=[OverdueTask(**r) for r in DashboardRepository.overdue_tasks(db, wh)],
            alerts=alerts,
        )

    @staticmethod
    def get_inventory(
        db: Session,
        user: UserContext,
        warehouse_id: uuid.UUID | None = None,
        near_expiry_days: int = DEFAULT_NEAR_EXPIRY_DAYS,
    ) -> DashboardInventoryResponse:
        wh = resolve_warehouse(user, warehouse_id)
        totals = DashboardRepository.inventory_totals(db, wh)
        loc = DashboardRepository.location_status_counts(db, wh)
        expiring = DashboardRepository.expiring_lots(db, wh, near_expiry_days)
        low = DashboardRepository.below_min_stock(db, wh)

        loc_total = sum(loc.values())
        occupied = sum(loc.get(s, 0) for s in OCCUPIED_LOCATION_STATUSES)
        locked = sum(loc.get(s, 0) for s in LOCKED_LOCATION_STATUSES)
        on_hand = sum(
            Decimal(totals[k] or 0)
            for k in ("qty_available", "qty_allocated", "qty_counting", "qty_locked")
        )
        alerts = _alerts(
            _alert(
                "CRITICAL",
                "LOT_EXPIRED_IN_STOCK",
                f"{expiring['expired']} lô đã hết hạn còn trong kho",
                expiring["expired"],
            ),
            _alert(
                "WARNING",
                "LOT_NEAR_EXPIRY",
                f"{expiring['near_expiry']} lô hết hạn trong {near_expiry_days} ngày tới",
                expiring["near_expiry"],
            ),
            _alert(
                "WARNING",
                "SKU_BELOW_MIN_STOCK",
                f"{low['count']} SKU dưới mức tồn tối thiểu",
                low["count"],
            ),
            _alert("INFO", "LOCATION_LOCKED", f"{locked} vị trí đang bị khóa", locked),
        )
        return DashboardInventoryResponse(
            scope=_scope(db, wh),
            near_expiry_days=near_expiry_days,
            skus_in_stock=int(totals["skus_in_stock"]),
            pallets_in_stock=int(totals["pallets_in_stock"]),
            quantities=StockQuantities(
                available=_qty(totals["qty_available"]),
                allocated=_qty(totals["qty_allocated"]),
                counting=_qty(totals["qty_counting"]),
                locked=_qty(totals["qty_locked"]),
                damaged=_qty(totals["qty_damaged"]),
                on_hand=_qty(on_hand),
            ),
            locations=LocationUsage(
                total=loc_total,
                occupied=occupied,
                empty=loc.get("EMPTY", 0),
                locked=locked,
                occupancy_rate=_rate(occupied, loc_total),
                by_status=loc,
            ),
            expired_lots=expiring["expired"],
            near_expiry_lots=expiring["near_expiry"],
            expiring_list=[
                ExpiringLot(**{**r, "qty_on_hand": _qty(r["qty_on_hand"])})
                for r in expiring["items"]
            ],
            below_min_stock_skus=low["count"],
            below_min_stock_list=[
                LowStockSku(
                    sku_code=r["sku_code"],
                    sku_name=r["sku_name"],
                    min_stock_level=_qty(r["min_stock_level"]),
                    qty_available=_qty(r["qty_available"]),
                )
                for r in low["items"]
            ],
            alerts=alerts,
        )

    @staticmethod
    def get_orders(
        db: Session, user: UserContext, warehouse_id: uuid.UUID | None = None
    ) -> DashboardOrdersResponse:
        wh = resolve_warehouse(user, warehouse_id)
        inbound = DashboardRepository.inbound_summary(db, wh)
        out = DashboardRepository.outbound_summary(db, wh)
        appr = DashboardRepository.approval_summary(db, wh)
        sync_failed = DashboardRepository.integration_failures(db, wh)

        open_by_status: dict[str, int] = out["open_by_status"]
        pending_by_status: dict[str, int] = appr["pending_by_status"]
        on_hold = open_by_status.get("ON_HOLD", 0)
        alerts = _alerts(
            _alert(
                "CRITICAL",
                "ORDER_LATE",
                f"{out['late']} đơn xuất đã quá giờ cắt xe",
                out["late"],
            ),
            _alert(
                "CRITICAL",
                "APPROVAL_OVERDUE",
                f"{appr['overdue']} hồ sơ duyệt quá hạn SLA",
                appr["overdue"],
            ),
            _alert(
                "WARNING",
                "ORDER_ON_HOLD",
                f"{on_hold} đơn xuất đang tạm dừng (thiếu hàng)",
                on_hold,
            ),
            _alert(
                "WARNING",
                "INTEGRATION_FAILED",
                f"{sync_failed} chứng từ đồng bộ ERP/TMS bị lỗi",
                sync_failed,
            ),
            _alert(
                "WARNING",
                "PO_LATE",
                f"{inbound['pos_late']} PO quá ngày giao dự kiến chưa nhận đủ",
                inbound["pos_late"],
            ),
            _alert(
                "INFO",
                "ERP_CHANGE_PENDING",
                f"{out['erp_change_pending']} đơn có yêu cầu đổi/hủy từ ERP chờ xử lý",
                out["erp_change_pending"],
            ),
        )
        return DashboardOrdersResponse(
            scope=_scope(db, wh),
            inbound=InboundSummary(**inbound),
            outbound=OutboundSummary(
                open_orders=sum(open_by_status.values()),
                open_by_status=open_by_status,
                urgent_open=out["urgent_open"],
                late=out["late"],
                on_hold=on_hold,
                due_today=out["due_today"],
                due_today_shipped=out["due_today_shipped"],
                fulfillment_rate_today=_rate(out["due_today_shipped"], out["due_today"]),
                gi_confirmed_today=out["gi_confirmed_today"],
                erp_change_pending=out["erp_change_pending"],
            ),
            approvals=ApprovalSummary(
                pending_total=sum(pending_by_status.values()),
                pending_by_status=pending_by_status,
                overdue=appr["overdue"],
            ),
            integration_failures=sync_failed,
            late_orders=[LateOrder(**r) for r in DashboardRepository.late_orders(db, wh)],
            alerts=alerts,
        )
