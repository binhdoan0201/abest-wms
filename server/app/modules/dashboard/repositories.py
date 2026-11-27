"""ABEST WMS - Repositories cho Phân hệ Tổng quan (Dashboard).

Theo chuẩn API mục 7.2: truy vấn nhiều bảng hoặc báo cáo (dashboard) đặt trong `repositories.py`.
Dashboard chỉ đọc, không có bảng riêng; mọi truy vấn là SQL tổng hợp trên bảng của module khác
nên không import model của module khác. «Hôm nay» tính theo giờ Việt Nam.

Mọi hàm nhận `warehouse_id`; `None` là gộp mọi kho (chỉ dùng cho người dùng không gắn kho).
"""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

LOCAL_TZ = "Asia/Ho_Chi_Minh"
TODAY_START = f"(date_trunc('day', NOW() AT TIME ZONE '{LOCAL_TZ}') AT TIME ZONE '{LOCAL_TZ}')"
TODAY_DATE = f"(NOW() AT TIME ZONE '{LOCAL_TZ}')::date"

OPEN_TASK_STATUSES = ("UNASSIGNED", "ASSIGNED", "IN_PROGRESS", "PAUSED_OFFLINE")
OPEN_PO_STATUSES = ("PENDING", "RECEIVING", "PARTIAL_RECEIVED")
PENDING_GRN_STATUSES = ("PENDING_D1", "PENDING_D2", "PENDING_D3")
# WMS kết thúc trách nhiệm tại SHIPPED (đặc tả F50, F51); các trạng thái sau đó là của TMS.
SHIPPED_ORDER_STATUSES = (
    "SHIPPED",
    "IN_TRANSIT",
    "DELIVERED",
    "PARTIAL_DELIVERED",
    "DELIVERY_FAILED",
)
CLOSED_ORDER_STATUSES = (*SHIPPED_ORDER_STATUSES, "CANCELLED")
PENDING_APPROVAL_STATUSES = ("PENDING_D1", "PENDING_D2", "PENDING_D3", "NEED_INFO")
ALERT_LIST_LIMIT = 10


def _wh(alias: str) -> str:
    """Điều kiện lọc kho; `:wh` NULL nghĩa là mọi kho."""
    return f"(CAST(:wh AS uuid) IS NULL OR {alias}.warehouse_id = CAST(:wh AS uuid))"


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


def _rows(db: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


def _one(db: Session, sql: str, params: dict[str, Any]) -> dict[str, Any]:
    return dict(db.execute(text(sql), params).mappings().one())


def _group(db: Session, sql: str, params: dict[str, Any]) -> dict[str, int]:
    return {str(k): int(v) for k, v in db.execute(text(sql), params).all()}


class DashboardRepository:
    """Truy vấn thống kê đa bảng phục vụ Dashboard (chỉ đọc)."""

    # ------------------------------------------------------------------ Task
    @staticmethod
    def task_counts(db: Session, warehouse_id: uuid.UUID | None) -> dict[str, Any]:
        p = {"wh": warehouse_id}
        open_in = _in(OPEN_TASK_STATUSES)
        by_status = _group(
            db,
            f"SELECT t.status::text, COUNT(*) FROM tasks t WHERE {_wh('t')} GROUP BY 1",
            p,
        )
        open_by_type = _group(
            db,
            f"SELECT t.task_type::text, COUNT(*) FROM tasks t "
            f"WHERE {_wh('t')} AND t.status::text IN {open_in} GROUP BY 1",
            p,
        )
        open_by_stage = _group(
            db,
            f"SELECT t.stage::text, COUNT(*) FROM tasks t "
            f"WHERE {_wh('t')} AND t.status::text IN {open_in} GROUP BY 1",
            p,
        )
        summary = _one(
            db,
            f"""
            SELECT
              COUNT(*) FILTER (WHERE t.status::text IN {open_in}
                               AND t.sla_due_at < NOW()) AS overdue,
              COUNT(*) FILTER (WHERE t.status::text IN {open_in}
                               AND t.priority = 'URGENT') AS urgent_open,
              COUNT(*) FILTER (WHERE t.status = 'COMPLETED'
                               AND t.completed_at >= {TODAY_START}) AS completed_today,
              COUNT(*) FILTER (WHERE t.status = 'COMPLETED'
                               AND t.completed_at >= {TODAY_START}
                               AND (t.sla_due_at IS NULL
                                    OR t.completed_at <= t.sla_due_at)) AS completed_today_on_time
            FROM tasks t WHERE {_wh('t')}
            """,
            p,
        )
        return {
            "by_status": by_status,
            "open_by_type": open_by_type,
            "open_by_stage": open_by_stage,
            **{k: int(v) for k, v in summary.items()},
        }

    @staticmethod
    def overdue_tasks(db: Session, warehouse_id: uuid.UUID | None) -> list[dict[str, Any]]:
        return _rows(
            db,
            f"""
            SELECT t.task_id, t.task_type::text AS task_type, t.stage::text AS stage,
                   t.priority::text AS priority, t.status::text AS status,
                   t.ref_doc_type, t.ref_doc_id, z.zone_code, u.full_name AS assigned_to_name,
                   t.sla_due_at,
                   FLOOR(EXTRACT(EPOCH FROM (NOW() - t.sla_due_at)) / 60)::int AS minutes_overdue
            FROM tasks t
            LEFT JOIN zones z ON z.zone_id = t.zone_id
            LEFT JOIN users u ON u.user_id = t.assigned_to
            WHERE {_wh('t')} AND t.status::text IN {_in(OPEN_TASK_STATUSES)}
              AND t.sla_due_at < NOW()
            ORDER BY t.sla_due_at
            LIMIT {ALERT_LIST_LIMIT}
            """,
            {"wh": warehouse_id},
        )

    # ------------------------------------------------------------- Tồn kho
    @staticmethod
    def inventory_totals(db: Session, warehouse_id: uuid.UUID | None) -> dict[str, Any]:
        return _one(
            db,
            f"""
            SELECT
              COUNT(DISTINCT b.sku_id) FILTER (
                WHERE b.qty_available + b.qty_allocated + b.qty_counting
                      + b.qty_locked + b.qty_damaged > 0) AS skus_in_stock,
              COUNT(DISTINCT b.pallet_id) FILTER (
                WHERE b.qty_available + b.qty_allocated + b.qty_counting
                      + b.qty_locked + b.qty_damaged > 0) AS pallets_in_stock,
              COALESCE(SUM(b.qty_available), 0) AS qty_available,
              COALESCE(SUM(b.qty_allocated), 0) AS qty_allocated,
              COALESCE(SUM(b.qty_counting), 0) AS qty_counting,
              COALESCE(SUM(b.qty_locked), 0) AS qty_locked,
              COALESCE(SUM(b.qty_damaged), 0) AS qty_damaged
            FROM inventory_balances b WHERE {_wh('b')}
            """,
            {"wh": warehouse_id},
        )

    @staticmethod
    def location_status_counts(db: Session, warehouse_id: uuid.UUID | None) -> dict[str, int]:
        return _group(
            db,
            f"SELECT l.status::text, COUNT(*) FROM locations l "
            f"WHERE {_wh('l')} AND l.is_active GROUP BY 1",
            {"wh": warehouse_id},
        )

    @staticmethod
    def expiring_lots(
        db: Session, warehouse_id: uuid.UUID | None, near_expiry_days: int
    ) -> dict[str, Any]:
        """Lô còn tồn đã hết hạn hoặc sắp hết hạn trong `near_expiry_days` ngày."""
        base = f"""
            SELECT s.sku_code, s.sku_name, lt.lot_number, lt.expiry_date,
                   (lt.expiry_date - {TODAY_DATE})::int AS days_left,
                   SUM(b.qty_available + b.qty_allocated + b.qty_counting + b.qty_locked)
                     AS qty_on_hand
            FROM inventory_balances b
            JOIN lots lt ON lt.lot_id = b.lot_id
            JOIN skus s ON s.sku_id = b.sku_id
            WHERE {_wh('b')} AND lt.expiry_date IS NOT NULL
            GROUP BY s.sku_code, s.sku_name, lt.lot_number, lt.expiry_date
            HAVING SUM(b.qty_available + b.qty_allocated + b.qty_counting + b.qty_locked) > 0
        """
        p = {"wh": warehouse_id, "n": near_expiry_days}
        counts = _one(
            db,
            f"""
            SELECT COUNT(*) FILTER (WHERE x.days_left < 0) AS expired,
                   COUNT(*) FILTER (WHERE x.days_left BETWEEN 0 AND :n) AS near_expiry
            FROM ({base}) x
            """,
            p,
        )
        items = _rows(
            db,
            f"SELECT * FROM ({base}) x WHERE x.days_left <= :n "
            f"ORDER BY x.expiry_date, x.sku_code LIMIT {ALERT_LIST_LIMIT}",
            p,
        )
        return {
            "expired": int(counts["expired"]),
            "near_expiry": int(counts["near_expiry"]),
            "items": items,
        }

    @staticmethod
    def below_min_stock(db: Session, warehouse_id: uuid.UUID | None) -> dict[str, Any]:
        base = f"""
            SELECT s.sku_code, s.sku_name, s.min_stock_level,
                   COALESCE(SUM(b.qty_available), 0) AS qty_available
            FROM skus s
            LEFT JOIN inventory_balances b ON b.sku_id = s.sku_id AND {_wh('b')}
            WHERE s.is_active AND s.min_stock_level > 0
            GROUP BY s.sku_code, s.sku_name, s.min_stock_level
            HAVING COALESCE(SUM(b.qty_available), 0) < s.min_stock_level
        """
        p = {"wh": warehouse_id}
        total = db.execute(text(f"SELECT COUNT(*) FROM ({base}) x"), p).scalar_one()
        items = _rows(db, f"{base} ORDER BY s.sku_code LIMIT {ALERT_LIST_LIMIT}", p)
        return {"count": int(total), "items": items}

    # ------------------------------------------------------------- Đơn hàng
    @staticmethod
    def inbound_summary(db: Session, warehouse_id: uuid.UUID | None) -> dict[str, Any]:
        p = {"wh": warehouse_id}
        po = _one(
            db,
            f"""
            SELECT COUNT(*) FILTER (WHERE po.status::text IN {_in(OPEN_PO_STATUSES)}) AS open_pos,
                   COUNT(*) FILTER (WHERE po.status::text IN {_in(OPEN_PO_STATUSES)}
                                    AND po.expected_date = {TODAY_DATE}) AS pos_due_today,
                   COUNT(*) FILTER (WHERE po.status::text IN {_in(OPEN_PO_STATUSES)}
                                    AND po.expected_date < {TODAY_DATE}) AS pos_late
            FROM purchase_orders po WHERE {_wh('po')}
            """,
            p,
        )
        grn = _one(
            db,
            f"""
            SELECT COUNT(*) FILTER (WHERE g.created_at >= {TODAY_START}) AS grns_today,
                   COUNT(*) FILTER (WHERE g.status::text IN {_in(PENDING_GRN_STATUSES)})
                     AS grns_pending_approval,
                   COUNT(*) FILTER (WHERE g.closed_at >= {TODAY_START}) AS grns_closed_today
            FROM grns g WHERE {_wh('g')}
            """,
            p,
        )
        return {k: int(v) for k, v in {**po, **grn}.items()}

    @staticmethod
    def outbound_summary(db: Session, warehouse_id: uuid.UUID | None) -> dict[str, Any]:
        p = {"wh": warehouse_id}
        closed_in = _in(CLOSED_ORDER_STATUSES)
        shipped_in = _in(SHIPPED_ORDER_STATUSES)
        open_by_status = _group(
            db,
            f"SELECT o.status::text, COUNT(*) FROM outbound_orders o "
            f"WHERE {_wh('o')} AND o.status::text NOT IN {closed_in} GROUP BY 1",
            p,
        )
        summary = _one(
            db,
            f"""
            SELECT
              COUNT(*) FILTER (WHERE o.status::text NOT IN {closed_in}
                               AND o.is_urgent) AS urgent_open,
              COUNT(*) FILTER (WHERE o.status::text NOT IN {closed_in}
                               AND o.cutoff_time < NOW()) AS late,
              COUNT(*) FILTER (WHERE (o.cutoff_time AT TIME ZONE '{LOCAL_TZ}')::date
                                     = {TODAY_DATE}
                               AND o.status <> 'CANCELLED') AS due_today,
              COUNT(*) FILTER (WHERE (o.cutoff_time AT TIME ZONE '{LOCAL_TZ}')::date
                                     = {TODAY_DATE}
                               AND o.status::text IN {shipped_in}) AS due_today_shipped,
              COUNT(*) FILTER (WHERE o.erp_change_pending) AS erp_change_pending
            FROM outbound_orders o WHERE {_wh('o')}
            """,
            p,
        )
        shipped_today = db.execute(
            text(
                f"SELECT COUNT(*) FROM goods_issues gi WHERE {_wh('gi')} "
                f"AND gi.status = 'GI_CONFIRMED' AND gi.confirmed_at >= {TODAY_START}"
            ),
            p,
        ).scalar_one()
        return {
            "open_by_status": open_by_status,
            "gi_confirmed_today": int(shipped_today),
            **{k: int(v) for k, v in summary.items()},
        }

    @staticmethod
    def late_orders(db: Session, warehouse_id: uuid.UUID | None) -> list[dict[str, Any]]:
        return _rows(
            db,
            f"""
            SELECT o.order_id, o.erp_order_number, o.order_type, o.status::text AS status,
                   o.is_urgent, o.cutoff_time,
                   FLOOR(EXTRACT(EPOCH FROM (NOW() - o.cutoff_time)) / 60)::int AS minutes_late
            FROM outbound_orders o
            WHERE {_wh('o')} AND o.status::text NOT IN {_in(CLOSED_ORDER_STATUSES)}
              AND o.cutoff_time < NOW()
            ORDER BY o.is_urgent DESC, o.cutoff_time
            LIMIT {ALERT_LIST_LIMIT}
            """,
            {"wh": warehouse_id},
        )

    @staticmethod
    def approval_summary(db: Session, warehouse_id: uuid.UUID | None) -> dict[str, Any]:
        p = {"wh": warehouse_id}
        pending_in = _in(PENDING_APPROVAL_STATUSES)
        by_status = _group(
            db,
            f"SELECT a.status::text, COUNT(*) FROM approval_requests a "
            f"WHERE {_wh('a')} AND a.status::text IN {pending_in} GROUP BY 1",
            p,
        )
        overdue = db.execute(
            text(
                f"SELECT COUNT(*) FROM approval_requests a WHERE {_wh('a')} "
                f"AND a.status::text IN {pending_in} AND a.sla_due_at < NOW()"
            ),
            p,
        ).scalar_one()
        return {"pending_by_status": by_status, "overdue": int(overdue)}

    @staticmethod
    def integration_failures(db: Session, warehouse_id: uuid.UUID | None) -> int:
        value = db.execute(
            text(
                f"SELECT COUNT(*) FROM integration_sync_logs s WHERE {_wh('s')} "
                "AND s.status IN ('FAILED_BUSINESS', 'FAILED_TECHNICAL')"
            ),
            {"wh": warehouse_id},
        ).scalar_one()
        return int(value)

    @staticmethod
    def today(db: Session) -> date:
        value = db.execute(text(f"SELECT {TODAY_DATE}")).scalar_one()
        assert isinstance(value, date)
        return value
