"""ABEST WMS - Repository truy vấn và thao tác CSDL cho Phân hệ Xuất kho (Outbound).

Quy tắc kiến trúc:
- Toàn bộ lời gọi hàm DB `fn_*` của phân hệ Outbound nằm tại đây.
- Các truy vấn tổng hợp nhiều bảng được đóng gói tại đây.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def _fmt_num(val: Any) -> str:
    """Định dạng số NUMERIC thành chuỗi 3 chữ số thập phân theo Chuẩn API Mục 2.3."""
    if val is None:
        return "0.000"
    return f"{Decimal(str(val)):.3f}"


def _fmt_dt(val: Any) -> str | None:
    """Định dạng thời gian sang chuỗi ISO 8601."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return str(val.isoformat())
    return str(val)


class OutboundRepository:
    """Repository thao tác dữ liệu Outbound trên PostgreSQL."""

    @staticmethod
    def list_orders(
        db: Session,
        warehouse_id: uuid.UUID | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        where_clauses = ["1=1"]
        params: dict[str, Any] = {
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }

        if warehouse_id is not None:
            where_clauses.append("o.warehouse_id = :warehouse_id")
            params["warehouse_id"] = warehouse_id

        if status:
            where_clauses.append("o.status::TEXT = :status")
            params["status"] = status

        where_sql = " AND ".join(where_clauses)

        count_stmt = text(f"SELECT COUNT(*) FROM outbound_orders o WHERE {where_sql};")
        total = int(db.execute(count_stmt, params).scalar_one())

        list_stmt = text(
            f"""
            SELECT
                o.order_id,
                o.erp_order_number,
                o.order_type,
                o.warehouse_id,
                o.customer_id,
                c.customer_name,
                o.supplier_id,
                o.dest_warehouse_id,
                o.status::TEXT AS status,
                o.is_urgent,
                o.urgent_reason,
                o.cutoff_time,
                o.route_code,
                o.delay_reason,
                o.erp_change_pending,
                o.version_no,
                o.created_at,
                o.updated_at
            FROM outbound_orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            WHERE {where_sql}
            ORDER BY o.is_urgent DESC, o.cutoff_time ASC, o.created_at DESC
            LIMIT :limit OFFSET :offset;
            """
        )

        rows = db.execute(list_stmt, params).mappings().all()
        items: list[dict[str, Any]] = []
        for r in rows:
            items.append(
                {
                    "order_id": str(r["order_id"]),
                    "erp_order_number": r["erp_order_number"],
                    "order_type": r["order_type"],
                    "warehouse_id": str(r["warehouse_id"]),
                    "customer_id": str(r["customer_id"]) if r["customer_id"] else None,
                    "customer_name": r["customer_name"],
                    "supplier_id": str(r["supplier_id"]) if r["supplier_id"] else None,
                    "dest_warehouse_id": (
                        str(r["dest_warehouse_id"]) if r["dest_warehouse_id"] else None
                    ),
                    "status": r["status"],
                    "is_urgent": bool(r["is_urgent"]),
                    "urgent_reason": r["urgent_reason"],
                    "cutoff_time": _fmt_dt(r["cutoff_time"]),
                    "route_code": r["route_code"],
                    "delay_reason": r["delay_reason"],
                    "erp_change_pending": bool(r["erp_change_pending"]),
                    "version_no": int(r["version_no"]),
                    "created_at": _fmt_dt(r["created_at"]),
                    "updated_at": _fmt_dt(r["updated_at"]),
                }
            )
        return items, total

    @staticmethod
    def get_order_raw(
        db: Session, order_id: uuid.UUID, for_update: bool = False
    ) -> dict[str, Any] | None:
        lock_sql = "FOR UPDATE OF o" if for_update else ""
        stmt = text(
            f"""
            SELECT
                o.order_id,
                o.erp_order_number,
                o.order_type,
                o.warehouse_id,
                o.customer_id,
                c.customer_name,
                o.supplier_id,
                o.dest_warehouse_id,
                o.status::TEXT AS status,
                o.is_urgent,
                o.urgent_reason,
                o.cutoff_time,
                o.route_code,
                o.delay_reason,
                o.erp_change_pending,
                o.erp_change_payload,
                o.version_no,
                o.created_at,
                o.updated_at
            FROM outbound_orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_id = :order_id
            {lock_sql};
            """
        )
        row = db.execute(stmt, {"order_id": order_id}).mappings().first()
        if not row:
            return None
        return dict(row)

    @staticmethod
    def get_order_lines(db: Session, order_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = text(
            """
            SELECT
                l.order_line_id,
                l.order_id,
                l.sku_id,
                s.sku_code,
                s.sku_name,
                s.base_uom,
                s.is_expiry_tracked,
                l.qty_ordered,
                l.qty_allocated,
                l.qty_picked,
                l.qty_packed,
                l.qty_shipped,
                l.shortage_resolution
            FROM outbound_order_lines l
            JOIN skus s ON s.sku_id = l.sku_id
            WHERE l.order_id = :order_id
            ORDER BY l.order_line_id ASC;
            """
        )
        rows = db.execute(stmt, {"order_id": order_id}).mappings().all()
        return [dict(r) for r in rows]

    @staticmethod
    def get_order_allocations(db: Session, order_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = text(
            """
            SELECT
                ia.allocation_id,
                ia.order_line_id,
                ia.balance_id,
                ia.lot_id,
                ia.qty_allocated,
                ia.qty_picked,
                ia.status,
                ia.version_no,
                b.location_id,
                b.sku_id,
                b.pallet_id,
                b.serial_number
            FROM inventory_allocations ia
            JOIN outbound_order_lines l ON l.order_line_id = ia.order_line_id
            JOIN inventory_balances b ON b.balance_id = ia.balance_id
            WHERE l.order_id = :order_id
            ORDER BY ia.created_at ASC;
            """
        )
        rows = db.execute(stmt, {"order_id": order_id}).mappings().all()
        return [dict(r) for r in rows]

    @staticmethod
    def get_order_packages(db: Session, order_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = text(
            """
            SELECT
                p.package_id,
                p.package_barcode,
                p.order_id,
                p.pick_session_id,
                p.gi_id,
                p.box_type_id,
                p.weight_kg,
                p.packed_by,
                p.packed_at,
                p.is_loaded_on_truck,
                p.loaded_at
            FROM packages p
            WHERE p.order_id = :order_id
            ORDER BY p.packed_at ASC;
            """
        )
        rows = db.execute(stmt, {"order_id": order_id}).mappings().all()
        return [dict(r) for r in rows]

    @staticmethod
    def get_warehouse_picking_rule(db: Session, warehouse_id: uuid.UUID) -> str:
        stmt = text(
            """
            SELECT picking_rule::TEXT
            FROM warehouse_configs
            WHERE warehouse_id = :warehouse_id;
            """
        )
        rule = db.execute(stmt, {"warehouse_id": warehouse_id}).scalar_one_or_none()
        return str(rule) if rule else "FEFO"

    @staticmethod
    def find_allocatable_balances(
        db: Session,
        warehouse_id: uuid.UUID,
        sku_id: uuid.UUID,
        strategy: str,
    ) -> list[dict[str, Any]]:
        """Tìm các dòng tồn khả dụng tại khu STORAGE theo chiến lược FEFO hoặc FIFO."""
        order_by = (
            "lt.is_priority_dispatch DESC NULLS LAST, "
            "lt.expiry_date ASC NULLS LAST, "
            "lt.received_at ASC NULLS LAST, "
            "b.updated_at ASC"
            if strategy == "FEFO"
            else "lt.is_priority_dispatch DESC NULLS LAST, "
            "lt.received_at ASC NULLS LAST, "
            "b.updated_at ASC"
        )
        stmt = text(
            f"""
            SELECT
                b.balance_id,
                b.warehouse_id,
                b.location_id,
                b.sku_id,
                b.lot_id,
                b.pallet_id,
                b.serial_number,
                b.qty_available,
                b.version_no
            FROM inventory_balances b
            JOIN locations loc ON loc.location_id = b.location_id
            JOIN zones z ON z.zone_id = loc.zone_id
            LEFT JOIN lots lt ON lt.lot_id = b.lot_id
            WHERE b.warehouse_id = :warehouse_id
              AND b.sku_id = :sku_id
              AND b.qty_available > 0
              AND loc.is_active = TRUE
              AND loc.status NOT IN ('COUNTING_LOCKED', 'MAINTENANCE_LOCKED', 'DAMAGED_HOLD')
              AND z.zone_type = 'STORAGE'
              AND (lt.lot_id IS NULL OR lt.expiry_date IS NULL OR lt.expiry_date >= CURRENT_DATE)
            ORDER BY {order_by}
            FOR UPDATE OF b;
            """
        )
        rows = (
            db.execute(
                stmt,
                {"warehouse_id": warehouse_id, "sku_id": sku_id},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    @staticmethod
    def upsert_inventory_allocation(
        db: Session,
        order_line_id: uuid.UUID,
        balance_id: uuid.UUID,
        lot_id: uuid.UUID | None,
        qty_allocated: Decimal,
    ) -> uuid.UUID:
        stmt = text(
            """
            INSERT INTO inventory_allocations (
                order_line_id, balance_id, lot_id, qty_allocated, qty_picked, status
            ) VALUES (
                :order_line_id, :balance_id, :lot_id, :qty_allocated, 0, 'ACTIVE'
            )
            ON CONFLICT (order_line_id, balance_id) DO UPDATE SET
                qty_allocated = inventory_allocations.qty_allocated + EXCLUDED.qty_allocated,
                status = 'ACTIVE',
                version_no = inventory_allocations.version_no + 1,
                updated_at = NOW()
            RETURNING allocation_id;
            """
        )
        alloc_id: uuid.UUID = db.execute(
            stmt,
            {
                "order_line_id": order_line_id,
                "balance_id": balance_id,
                "lot_id": lot_id,
                "qty_allocated": qty_allocated,
            },
        ).scalar_one()
        return alloc_id

    @staticmethod
    def update_order_line_allocated(
        db: Session,
        order_line_id: uuid.UUID,
        qty_allocated: Decimal,
        shortage_resolution: str | None = None,
    ) -> None:
        stmt = text(
            """
            UPDATE outbound_order_lines
            SET qty_allocated = :qty_allocated,
                shortage_resolution = COALESCE(:shortage_resolution, shortage_resolution)
            WHERE order_line_id = :order_line_id;
            """
        )
        db.execute(
            stmt,
            {
                "order_line_id": order_line_id,
                "qty_allocated": qty_allocated,
                "shortage_resolution": shortage_resolution,
            },
        )

    @staticmethod
    def bump_order_version(
        db: Session,
        order_id: uuid.UUID,
        new_status: str | None = None,
        delay_reason: str | None = None,
    ) -> int:
        if new_status is not None:
            stmt = text(
                """
                UPDATE outbound_orders
                SET status = CAST(:new_status AS order_status_type),
                    delay_reason = :delay_reason,
                    version_no = version_no + 1,
                    updated_at = NOW()
                WHERE order_id = :order_id
                RETURNING version_no;
                """
            )
            new_ver: int = db.execute(
                stmt,
                {
                    "order_id": order_id,
                    "new_status": new_status,
                    "delay_reason": delay_reason,
                },
            ).scalar_one()
            return new_ver

        stmt = text(
            """
            UPDATE outbound_orders
            SET delay_reason = :delay_reason,
                version_no = version_no + 1,
                updated_at = NOW()
            WHERE order_id = :order_id
            RETURNING version_no;
            """
        )
        new_ver = db.execute(
            stmt,
            {"order_id": order_id, "delay_reason": delay_reason},
        ).scalar_one()
        return new_ver

    @staticmethod
    def create_pick_session(
        db: Session,
        warehouse_id: uuid.UUID,
        picker_user_id: uuid.UUID,
        pick_mode: str,
        shift_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        stmt = text(
            """
            INSERT INTO pick_sessions (
                warehouse_id, shift_id, pick_mode, picker_user_id, status
            ) VALUES (
                :warehouse_id, :shift_id, CAST(:pick_mode AS pick_mode_type),
                :picker_user_id, 'OPEN'
            )
            RETURNING pick_session_id, warehouse_id, shift_id, pick_mode::TEXT AS pick_mode,
                      picker_user_id, status, started_at, completed_at, version_no, created_at;
            """
        )
        row = (
            db.execute(
                stmt,
                {
                    "warehouse_id": warehouse_id,
                    "shift_id": shift_id,
                    "pick_mode": pick_mode,
                    "picker_user_id": picker_user_id,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    @staticmethod
    def create_pick_line(
        db: Session,
        pick_session_id: uuid.UUID,
        order_line_id: uuid.UUID,
        allocation_id: uuid.UUID,
        source_location_id: uuid.UUID,
        suggested_lot_id: uuid.UUID | None,
        qty_to_pick: Decimal,
    ) -> dict[str, Any]:
        stmt = text(
            """
            INSERT INTO pick_lines (
                pick_session_id, order_line_id, allocation_id,
                source_location_id, suggested_lot_id, qty_to_pick, qty_picked, status
            ) VALUES (
                :pick_session_id, :order_line_id, :allocation_id,
                :source_location_id, :suggested_lot_id, :qty_to_pick, 0, 'PENDING'
            )
            RETURNING pick_line_id, pick_session_id, order_line_id, allocation_id,
                      source_location_id, suggested_lot_id, qty_to_pick, qty_picked, status;
            """
        )
        row = (
            db.execute(
                stmt,
                {
                    "pick_session_id": pick_session_id,
                    "order_line_id": order_line_id,
                    "allocation_id": allocation_id,
                    "source_location_id": source_location_id,
                    "suggested_lot_id": suggested_lot_id,
                    "qty_to_pick": qty_to_pick,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    @staticmethod
    def get_pick_session_raw(
        db: Session, pick_session_id: uuid.UUID, for_update: bool = False
    ) -> dict[str, Any] | None:
        lock_sql = "FOR UPDATE OF ps" if for_update else ""
        stmt = text(
            f"""
            SELECT
                ps.pick_session_id,
                ps.warehouse_id,
                ps.shift_id,
                ps.pick_mode::TEXT AS pick_mode,
                ps.picker_user_id,
                u.full_name AS picker_name,
                ps.status,
                ps.started_at,
                ps.completed_at,
                ps.version_no,
                ps.created_at
            FROM pick_sessions ps
            LEFT JOIN users u ON u.user_id = ps.picker_user_id
            WHERE ps.pick_session_id = :pick_session_id
            {lock_sql};
            """
        )
        row = db.execute(stmt, {"pick_session_id": pick_session_id}).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_pick_lines(db: Session, pick_session_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = text(
            """
            SELECT
                pl.pick_line_id,
                pl.pick_session_id,
                pl.order_line_id,
                ol.order_id,
                o.erp_order_number,
                ol.sku_id,
                s.sku_code,
                s.sku_name,
                pl.allocation_id,
                pl.source_location_id,
                loc.location_code AS source_location_code,
                pl.staged_location_id,
                pl.suggested_lot_id,
                pl.actual_lot_id,
                pl.serial_numbers,
                pl.target_tote_barcode,
                pl.qty_to_pick,
                pl.qty_picked,
                pl.status,
                pl.exception_reason
            FROM pick_lines pl
            JOIN outbound_order_lines ol ON ol.order_line_id = pl.order_line_id
            JOIN outbound_orders o ON o.order_id = ol.order_id
            JOIN skus s ON s.sku_id = ol.sku_id
            JOIN locations loc ON loc.location_id = pl.source_location_id
            WHERE pl.pick_session_id = :pick_session_id
            ORDER BY loc.location_code ASC, pl.pick_line_id ASC;
            """
        )
        rows = db.execute(stmt, {"pick_session_id": pick_session_id}).mappings().all()
        return [dict(r) for r in rows]

    @staticmethod
    def get_pick_line_detail(
        db: Session,
        pick_session_id: uuid.UUID,
        pick_line_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        stmt = text(
            """
            SELECT
                pl.pick_line_id,
                pl.pick_session_id,
                pl.order_line_id,
                pl.allocation_id,
                pl.source_location_id,
                pl.staged_location_id,
                pl.suggested_lot_id,
                pl.actual_lot_id,
                pl.qty_to_pick,
                pl.qty_picked,
                pl.status,
                ol.order_id,
                ol.sku_id,
                ol.qty_ordered,
                ol.qty_allocated,
                ol.qty_picked AS line_qty_picked,
                o.warehouse_id,
                o.status::TEXT AS order_status,
                o.erp_change_pending,
                b.pallet_id,
                b.serial_number
            FROM pick_lines pl
            JOIN outbound_order_lines ol ON ol.order_line_id = pl.order_line_id
            JOIN outbound_orders o ON o.order_id = ol.order_id
            LEFT JOIN inventory_allocations ia ON ia.allocation_id = pl.allocation_id
            LEFT JOIN inventory_balances b ON b.balance_id = ia.balance_id
            WHERE pl.pick_session_id = :pick_session_id
              AND pl.pick_line_id = :pick_line_id
            FOR UPDATE OF pl;
            """
        )
        row = (
            db.execute(
                stmt,
                {"pick_session_id": pick_session_id, "pick_line_id": pick_line_id},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    @staticmethod
    def get_default_staging_location(db: Session, warehouse_id: uuid.UUID) -> uuid.UUID | None:
        stmt = text(
            """
            SELECT l.location_id
            FROM locations l
            JOIN zones z ON z.zone_id = l.zone_id
            WHERE l.warehouse_id = :warehouse_id
              AND z.zone_type = 'STAGING'
              AND l.is_active = TRUE
            ORDER BY l.location_code ASC
            LIMIT 1;
            """
        )
        loc_id: uuid.UUID | None = db.execute(
            stmt, {"warehouse_id": warehouse_id}
        ).scalar_one_or_none()
        return loc_id

    @staticmethod
    def complete_pick_line_db(
        db: Session,
        pick_line_id: uuid.UUID,
        allocation_id: uuid.UUID | None,
        order_line_id: uuid.UUID,
        actual_lot_id: uuid.UUID | None,
        qty_picked: Decimal,
        target_tote_barcode: str | None,
        staged_location_id: uuid.UUID | None,
        serial_numbers: list[str],
    ) -> None:
        db.execute(
            text(
                """
                UPDATE pick_lines
                SET actual_lot_id = :actual_lot_id,
                    qty_picked = :qty_picked,
                    target_tote_barcode = :target_tote_barcode,
                    staged_location_id = :staged_location_id,
                    serial_numbers = :serial_numbers,
                    status = 'PICKED'
                WHERE pick_line_id = :pick_line_id;
                """
            ),
            {
                "pick_line_id": pick_line_id,
                "actual_lot_id": actual_lot_id,
                "qty_picked": qty_picked,
                "target_tote_barcode": target_tote_barcode,
                "staged_location_id": staged_location_id,
                "serial_numbers": serial_numbers if serial_numbers else None,
            },
        )

        if allocation_id is not None:
            db.execute(
                text(
                    """
                    UPDATE inventory_allocations
                    SET qty_picked = qty_picked + :qty_picked,
                        status = CASE
                            WHEN qty_picked + :qty_picked >= qty_allocated THEN 'PICKED'
                            ELSE status
                        END,
                        version_no = version_no + 1,
                        updated_at = NOW()
                    WHERE allocation_id = :allocation_id;
                    """
                ),
                {"allocation_id": allocation_id, "qty_picked": qty_picked},
            )

        db.execute(
            text(
                """
                UPDATE outbound_order_lines
                SET qty_picked = qty_picked + :qty_picked
                WHERE order_line_id = :order_line_id;
                """
            ),
            {"order_line_id": order_line_id, "qty_picked": qty_picked},
        )

    @staticmethod
    def record_pick_line_exception_db(
        db: Session,
        pick_line_id: uuid.UUID,
        pick_session_id: uuid.UUID,
        order_id: uuid.UUID,
        exception_type: str,
        exception_reason: str,
        qty_actual: Decimal,
    ) -> None:
        db.execute(
            text(
                """
                UPDATE pick_lines
                SET status = :exception_type,
                    exception_reason = :exception_reason,
                    qty_picked = :qty_actual
                WHERE pick_line_id = :pick_line_id;
                """
            ),
            {
                "pick_line_id": pick_line_id,
                "exception_type": exception_type,
                "exception_reason": exception_reason,
                "qty_actual": qty_actual,
            },
        )

        db.execute(
            text(
                """
                UPDATE pick_sessions
                SET status = 'ON_HOLD_SHORTAGE',
                    version_no = version_no + 1
                WHERE pick_session_id = :pick_session_id;
                """
            ),
            {"pick_session_id": pick_session_id},
        )

        db.execute(
            text(
                """
                UPDATE outbound_order_lines ool
                SET qty_allocated = GREATEST(0, ool.qty_allocated - ia.qty_allocated)
                FROM pick_lines pl
                JOIN inventory_allocations ia ON ia.allocation_id = pl.allocation_id
                WHERE pl.pick_line_id = :pick_line_id
                  AND ool.order_line_id = ia.order_line_id
                  AND ia.status = 'ACTIVE';
                """
            ),
            {"pick_line_id": pick_line_id},
        )
        db.execute(
            text(
                """
                UPDATE inventory_allocations ia SET status = 'RELEASED'
                FROM pick_lines pl
                WHERE pl.pick_line_id = :pick_line_id AND ia.allocation_id = pl.allocation_id;
                """
            ),
            {"pick_line_id": pick_line_id},
        )
        db.execute(
            text(
                """
                UPDATE outbound_orders
                SET status = CAST('ON_HOLD' AS order_status_type),
                    delay_reason = 'SHORTAGE',
                    version_no = version_no + 1,
                    updated_at = NOW()
                WHERE order_id = :order_id;
                """
            ),
            {"order_id": order_id},
        )

    @staticmethod
    def check_reason_code_exists(db: Session, reason_code: str) -> bool:
        stmt = text(
            "SELECT 1 FROM reason_codes WHERE reason_code = :reason_code AND is_active = TRUE;"
        )
        return db.execute(stmt, {"reason_code": reason_code}).scalar_one_or_none() is not None

    @staticmethod
    def refresh_pick_session_and_orders_after_pick(
        db: Session,
        pick_session_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Cập nhật trạng thái phiên soạn và các đơn hàng liên quan sau khi xác nhận dòng soạn."""
        pending_count = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*) FROM pick_lines
                    WHERE pick_session_id = :pick_session_id AND status = 'PENDING';
                    """
                ),
                {"pick_session_id": pick_session_id},
            ).scalar_one()
        )

        new_ps_status = "COMPLETED" if pending_count == 0 else "IN_PROGRESS"
        ps_row = (
            db.execute(
                text(
                    """
                UPDATE pick_sessions
                SET status = CAST(:status AS VARCHAR),
                    completed_at = CASE
                        WHEN CAST(:status AS VARCHAR) = 'COMPLETED' THEN NOW()
                        ELSE completed_at
                    END,
                    version_no = version_no + 1
                WHERE pick_session_id = :pick_session_id
                RETURNING status, version_no, completed_at;
                """
                ),
                {"pick_session_id": pick_session_id, "status": new_ps_status},
            )
            .mappings()
            .one()
        )

        # Cập nhật trạng thái các đơn thuộc phiên soạn này sang PICKED nếu đã pick đủ
        order_ids = (
            db.execute(
                text(
                    """
                    SELECT DISTINCT ol.order_id
                    FROM pick_lines pl
                    JOIN outbound_order_lines ol ON ol.order_line_id = pl.order_line_id
                    WHERE pl.pick_session_id = :pick_session_id;
                    """
                ),
                {"pick_session_id": pick_session_id},
            )
            .scalars()
            .all()
        )

        for oid in order_ids:
            unpicked = int(
                db.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM outbound_order_lines
                        WHERE order_id = :order_id AND qty_picked < qty_allocated;
                        """
                    ),
                    {"order_id": oid},
                ).scalar_one()
            )
            if unpicked == 0:
                db.execute(
                    text(
                        """
                        UPDATE outbound_orders
                        SET status = 'PICKED',
                            version_no = version_no + 1,
                            updated_at = NOW()
                        WHERE order_id = :order_id AND status = 'PICKING';
                        """
                    ),
                    {"order_id": oid},
                )

        return dict(ps_row)

    @staticmethod
    def create_package_with_lines(
        db: Session,
        order_id: uuid.UUID,
        pick_session_id: uuid.UUID | None,
        box_type_id: uuid.UUID | None,
        weight_kg: Decimal,
        length_cm: Decimal | None,
        width_cm: Decimal | None,
        height_cm: Decimal | None,
        packed_by: uuid.UUID,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        barcode = f"PKG-{uuid.uuid4().hex[:10].upper()}"
        pkg_row = (
            db.execute(
                text(
                    """
                INSERT INTO packages (
                    package_barcode, order_id, pick_session_id, box_type_id,
                    weight_kg, length_cm, width_cm, height_cm, packed_by
                ) VALUES (
                    :package_barcode, :order_id, :pick_session_id, :box_type_id,
                    :weight_kg, :length_cm, :width_cm, :height_cm, :packed_by
                )
                RETURNING package_id, package_barcode, order_id, pick_session_id,
                          gi_id, box_type_id, weight_kg, packed_by, packed_at, is_loaded_on_truck;
                """
                ),
                {
                    "package_barcode": barcode,
                    "order_id": order_id,
                    "pick_session_id": pick_session_id,
                    "box_type_id": box_type_id,
                    "weight_kg": weight_kg,
                    "length_cm": length_cm,
                    "width_cm": width_cm,
                    "height_cm": height_cm,
                    "packed_by": packed_by,
                },
            )
            .mappings()
            .one()
        )

        package_id: uuid.UUID = pkg_row["package_id"]
        created_lines: list[dict[str, Any]] = []

        for item in items:
            line_row = (
                db.execute(
                    text(
                        """
                    INSERT INTO package_lines (
                        package_id, order_line_id, sku_id, lot_id, qty, serial_numbers
                    ) VALUES (
                        :package_id, :order_line_id, :sku_id, :lot_id, :qty, :serial_numbers
                    )
                    RETURNING package_line_id, package_id, order_line_id,
                              sku_id, lot_id, qty, serial_numbers;
                    """
                    ),
                    {
                        "package_id": package_id,
                        "order_line_id": item["order_line_id"],
                        "sku_id": item["sku_id"],
                        "lot_id": item.get("lot_id"),
                        "qty": item["qty"],
                        "serial_numbers": item.get("serial_numbers") or None,
                    },
                )
                .mappings()
                .one()
            )
            created_lines.append(
                {
                    "package_line_id": str(line_row["package_line_id"]),
                    "order_line_id": str(line_row["order_line_id"]),
                    "sku_id": str(line_row["sku_id"]),
                    "lot_id": str(line_row["lot_id"]) if line_row["lot_id"] else None,
                    "qty": _fmt_num(line_row["qty"]),
                    "serial_numbers": line_row["serial_numbers"] or [],
                }
            )

        # Kiểm tra xem đã đóng gói đủ toàn bộ số lượng đã soạn của đơn chưa
        unpacked_count = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*) FROM outbound_order_lines
                    WHERE order_id = :order_id AND qty_packed < qty_picked;
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
        )
        next_order_status = "READY_TO_SHIP" if unpacked_count == 0 else "PACKING"
        db.execute(
            text(
                """
                UPDATE outbound_orders
                SET status = CAST(:next_status AS order_status_type),
                    version_no = version_no + 1,
                    updated_at = NOW()
                WHERE order_id = :order_id
                  AND status IN ('PICKED', 'PACKING', 'READY_TO_SHIP');
                """
            ),
            {"order_id": order_id, "next_status": next_order_status},
        )

        result = dict(pkg_row)
        result["lines"] = created_lines
        result["order_status"] = next_order_status
        return result

    @staticmethod
    def create_goods_issue_and_link_packages(
        db: Session,
        warehouse_id: uuid.UUID,
        order_id: uuid.UUID,
        gi_type: str,
        vehicle_id: uuid.UUID | None,
        tms_waybill_code: str | None,
    ) -> dict[str, Any]:
        gi_number = f"GI-{uuid.uuid4().hex[:10].upper()}"
        gi_row = (
            db.execute(
                text(
                    """
                INSERT INTO goods_issues (
                    gi_number, gi_type, warehouse_id, order_id,
                    vehicle_id, tms_waybill_code, status
                ) VALUES (
                    :gi_number, CAST(:gi_type AS gi_doc_type), :warehouse_id, :order_id,
                    :vehicle_id, :tms_waybill_code, 'LOADED'
                )
                RETURNING gi_id, gi_number, gi_type::TEXT AS gi_type, warehouse_id,
                          order_id, vehicle_id, tms_waybill_code, total_packages,
                          status, version_no;
                """
                ),
                {
                    "gi_number": gi_number,
                    "gi_type": gi_type,
                    "warehouse_id": warehouse_id,
                    "order_id": order_id,
                    "vehicle_id": vehicle_id,
                    "tms_waybill_code": tms_waybill_code,
                },
            )
            .mappings()
            .one()
        )

        gi_id: uuid.UUID = gi_row["gi_id"]

        # Gán gi_id và đánh dấu kiện lên xe (trigger tự cập nhật total_packages)
        db.execute(
            text(
                """
                UPDATE packages
                SET gi_id = :gi_id,
                    is_loaded_on_truck = TRUE,
                    loaded_at = NOW()
                WHERE order_id = :order_id AND gi_id IS NULL;
                """
            ),
            {"gi_id": gi_id, "order_id": order_id},
        )

        refreshed = (
            db.execute(
                text(
                    """
                SELECT gi_id, gi_number, gi_type::TEXT AS gi_type, warehouse_id,
                       order_id, vehicle_id, tms_waybill_code, total_packages,
                       status, version_no
                FROM goods_issues
                WHERE gi_id = :gi_id;
                """
                ),
                {"gi_id": gi_id},
            )
            .mappings()
            .one()
        )
        return dict(refreshed)

    @staticmethod
    def get_goods_issue_raw(
        db: Session, gi_id: uuid.UUID, for_update: bool = False
    ) -> dict[str, Any] | None:
        stmt = text(
            """
            SELECT
                gi.gi_id,
                gi.gi_number,
                gi.gi_type::TEXT AS gi_type,
                gi.warehouse_id,
                gi.order_id,
                gi.vehicle_id,
                gi.tms_waybill_code,
                gi.tms_waybill_status,
                gi.total_packages,
                gi.driver_signature_data,
                gi.driver_signed_at,
                gi.confirmed_by,
                gi.confirmed_at,
                gi.status,
                gi.version_no,
                o.status::TEXT AS order_status,
                o.erp_change_pending
            FROM goods_issues gi
            JOIN outbound_orders o ON o.order_id = gi.order_id
            WHERE gi.gi_id = :gi_id
            FOR UPDATE OF gi;
            """
        )
        row = db.execute(stmt, {"gi_id": gi_id}).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_shippable_staging_items(db: Session, order_id: uuid.UUID) -> list[dict[str, Any]]:
        """Lấy danh sách tồn đã soạn ở vị trí STAGING để trừ tồn kho khi xuất GI."""
        stmt = text(
            """
            SELECT
                pl.pick_line_id,
                pl.order_line_id,
                pl.allocation_id,
                COALESCE(pl.staged_location_id, pl.source_location_id) AS ship_location_id,
                ol.sku_id,
                COALESCE(pl.actual_lot_id, pl.suggested_lot_id) AS lot_id,
                pl.qty_picked,
                b.pallet_id,
                b.serial_number
            FROM pick_lines pl
            JOIN outbound_order_lines ol ON ol.order_line_id = pl.order_line_id
            LEFT JOIN inventory_allocations ia ON ia.allocation_id = pl.allocation_id
            LEFT JOIN inventory_balances b ON b.balance_id = ia.balance_id
            WHERE ol.order_id = :order_id
              AND pl.status = 'PICKED'
              AND pl.qty_picked > 0;
            """
        )
        rows = db.execute(stmt, {"order_id": order_id}).mappings().all()
        return [dict(r) for r in rows]

    @staticmethod
    def finalize_goods_issue_and_order(
        db: Session,
        gi_id: uuid.UUID,
        order_id: uuid.UUID,
        confirmed_by: uuid.UUID,
        driver_signature_data: str | None,
        handover_photo_urls: list[str],
    ) -> dict[str, Any]:
        gi_row = (
            db.execute(
                text(
                    """
                UPDATE goods_issues
                SET driver_signature_data = COALESCE(:driver_signature_data, driver_signature_data),
                    driver_signed_at = COALESCE(driver_signed_at, NOW()),
                    handover_photo_urls = CASE
                        WHEN :has_photos THEN :handover_photo_urls
                        ELSE handover_photo_urls
                    END,
                    confirmed_by = :confirmed_by,
                    confirmed_at = NOW(),
                    status = 'GI_CONFIRMED',
                    version_no = version_no + 1
                WHERE gi_id = :gi_id
                RETURNING gi_id, gi_number, gi_type::TEXT AS gi_type, warehouse_id,
                          order_id, vehicle_id, total_packages, confirmed_by,
                          confirmed_at, status, version_no;
                """
                ),
                {
                    "gi_id": gi_id,
                    "driver_signature_data": driver_signature_data,
                    "has_photos": len(handover_photo_urls) > 0,
                    "handover_photo_urls": handover_photo_urls if handover_photo_urls else None,
                    "confirmed_by": confirmed_by,
                },
            )
            .mappings()
            .one()
        )

        db.execute(
            text(
                """
                UPDATE inventory_allocations ia
                SET status = 'PICKED',
                    updated_at = NOW(),
                    version_no = ia.version_no + 1
                FROM outbound_order_lines ol
                WHERE ia.order_line_id = ol.order_line_id
                  AND ol.order_id = :order_id
                  AND ia.status = 'ACTIVE';
                """
            ),
            {"order_id": order_id},
        )

        db.execute(
            text(
                """
                UPDATE outbound_order_lines
                SET qty_shipped = qty_picked
                WHERE order_id = :order_id;
                """
            ),
            {"order_id": order_id},
        )

        db.execute(
            text(
                """
                UPDATE outbound_orders
                SET status = 'SHIPPED',
                    version_no = version_no + 1,
                    updated_at = NOW()
                WHERE order_id = :order_id;
                """
            ),
            {"order_id": order_id},
        )

        return dict(gi_row)

    @staticmethod
    def get_order_change_request_raw(
        db: Session,
        request_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        stmt = text(
            """
            SELECT
                request_id,
                order_id,
                warehouse_id,
                change_type,
                change_payload,
                order_status_at_receipt::TEXT AS order_status_at_receipt,
                decision_path,
                status,
                reject_reason_code,
                reject_note,
                decided_by,
                decided_at,
                created_at
            FROM order_change_requests
            WHERE request_id = :request_id;
            """
        )
        row = db.execute(stmt, {"request_id": request_id}).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def call_decide_order_change(
        db: Session,
        request_id: uuid.UUID,
        decision: str,
        manager_id: uuid.UUID,
        note: str | None,
    ) -> None:
        """Gọi hàm PostgreSQL fn_decide_order_change (4 tham số theo patch_v4_2_1)."""
        stmt = text(
            """
            SELECT fn_decide_order_change(
                :request_id,
                :decision,
                :manager_id,
                :note
            );
            """
        )
        db.execute(
            stmt,
            {
                "request_id": request_id,
                "decision": decision,
                "manager_id": manager_id,
                "note": note,
            },
        )

    @staticmethod
    def validate_picker_user(
        db: Session, picker_user_id: uuid.UUID, warehouse_id: uuid.UUID
    ) -> bool:
        stmt = text(
            """
            SELECT 1 FROM users u JOIN roles r ON r.role_id = u.primary_role_id
            WHERE u.user_id = :pid AND u.status = 'ACTIVE' AND r.role_code = 'nv-soan'
              AND (u.primary_warehouse_id IS NULL OR u.primary_warehouse_id = :wid);
            """
        )
        return (
            db.execute(stmt, {"pid": picker_user_id, "wid": warehouse_id}).scalar_one_or_none()
            is not None
        )

    @staticmethod
    def find_lot_balance_at_location(
        db: Session,
        location_id: uuid.UUID,
        sku_id: uuid.UUID,
        lot_id: uuid.UUID,
        required_qty: Decimal,
    ) -> dict[str, Any] | None:
        row = (
            db.execute(
                text(
                    """
                    SELECT
                        balance_id,
                        lot_id,
                        location_id,
                        pallet_id,
                        serial_number,
                        qty_available
                    FROM inventory_balances
                    WHERE location_id = :loc AND sku_id = :sku AND lot_id = :lot
                      AND qty_available >= :qty
                    ORDER BY pallet_id NULLS FIRST, serial_number NULLS FIRST
                    LIMIT 1 FOR UPDATE;
                    """
                ),
                {"loc": location_id, "sku": sku_id, "lot": lot_id, "qty": required_qty},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    @staticmethod
    def swap_allocation_balance(
        db: Session, allocation_id: uuid.UUID, new_balance_id: uuid.UUID, new_lot_id: uuid.UUID
    ) -> None:
        db.execute(
            text(
                """
                UPDATE inventory_allocations
                SET balance_id = :nb, lot_id = :nl WHERE allocation_id = :aid;
                """
            ),
            {"aid": allocation_id, "nb": new_balance_id, "nl": new_lot_id},
        )
