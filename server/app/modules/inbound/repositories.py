"""ABEST WMS - Repositories cho Phân hệ Nhập kho (Inbound)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from server.app.modules.inbound.models import (
    Asn,
    Grn,
    GrnCountAttempt,
    GrnLine,
    POLine,
    PurchaseOrder,
)


class InboundRepository:
    """Repository truy vấn các chứng từ và dữ liệu nhập kho."""

    @staticmethod
    def get_po_by_id(
        db: Session, po_id: uuid.UUID, for_update: bool = False
    ) -> PurchaseOrder | None:
        stmt = select(PurchaseOrder).where(PurchaseOrder.po_id == po_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.scalar(stmt)

    @staticmethod
    def get_po_by_erp_number(db: Session, erp_po_number: str) -> PurchaseOrder | None:
        return db.scalar(select(PurchaseOrder).where(PurchaseOrder.erp_po_number == erp_po_number))

    @staticmethod
    def get_po_lines(db: Session, po_id: uuid.UUID) -> list[POLine]:
        rows = db.scalars(
            select(POLine).where(POLine.po_id == po_id).order_by(POLine.line_number.asc())
        )
        return list(rows)

    @staticmethod
    def list_pos(
        db: Session,
        warehouse_id: uuid.UUID,
        status: str | None,
        supplier_id: uuid.UUID | None,
        sort_name: str,
        descending: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[PurchaseOrder], int]:
        conditions = [PurchaseOrder.warehouse_id == warehouse_id]
        if status is not None:
            conditions.append(PurchaseOrder.status == status)
        if supplier_id is not None:
            conditions.append(PurchaseOrder.supplier_id == supplier_id)
        column = getattr(PurchaseOrder, sort_name)
        order = column.desc() if descending else column.asc()
        total = db.scalar(select(func.count()).select_from(PurchaseOrder).where(*conditions))
        rows = db.scalars(
            select(PurchaseOrder)
            .where(*conditions)
            .order_by(order, PurchaseOrder.po_id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows), int(total or 0)

    @staticmethod
    def get_asn_by_id(db: Session, asn_id: uuid.UUID, for_update: bool = False) -> Asn | None:
        stmt = select(Asn).where(Asn.asn_id == asn_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.scalar(stmt)

    @staticmethod
    def get_asn_by_erp_number(db: Session, erp_asn_number: str) -> Asn | None:
        return db.scalar(select(Asn).where(Asn.erp_asn_number == erp_asn_number))

    @staticmethod
    def list_asns(
        db: Session,
        warehouse_id: uuid.UUID,
        status: str | None,
        po_id: uuid.UUID | None,
        sort_name: str,
        descending: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[Asn], int]:
        conditions = [Asn.warehouse_id == warehouse_id]
        if status is not None:
            conditions.append(Asn.status == status)
        if po_id is not None:
            conditions.append(Asn.po_id == po_id)
        column = getattr(Asn, sort_name)
        order = column.desc() if descending else column.asc()
        total = db.scalar(select(func.count()).select_from(Asn).where(*conditions))
        rows = db.scalars(
            select(Asn).where(*conditions).order_by(order, Asn.asn_id).offset(offset).limit(limit)
        )
        return list(rows), int(total or 0)

    @staticmethod
    def get_grn_by_id(db: Session, grn_id: uuid.UUID, for_update: bool = False) -> Grn | None:
        stmt = select(Grn).where(Grn.grn_id == grn_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.scalar(stmt)

    @staticmethod
    def list_grns(
        db: Session,
        warehouse_id: uuid.UUID,
        status: str | None,
        po_id: uuid.UUID | None,
        received_by: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Grn], int]:
        conditions = [Grn.warehouse_id == warehouse_id]
        if status is not None:
            conditions.append(Grn.status == status)
        if po_id is not None:
            conditions.append(Grn.po_id == po_id)
        if received_by is not None:
            conditions.append(Grn.received_by == received_by)
        total = db.scalar(select(func.count()).select_from(Grn).where(*conditions))
        rows = db.scalars(
            select(Grn)
            .where(*conditions)
            .order_by(Grn.created_at.desc(), Grn.grn_id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows), int(total or 0)

    @staticmethod
    def get_grn_lines(db: Session, grn_id: uuid.UUID) -> list[GrnLine]:
        return list(db.scalars(select(GrnLine).where(GrnLine.grn_id == grn_id)).all())

    @staticmethod
    def get_latest_attempt(db: Session, grn_line_id: uuid.UUID) -> GrnCountAttempt | None:
        return db.scalar(
            select(GrnCountAttempt)
            .where(GrnCountAttempt.grn_line_id == grn_line_id)
            .order_by(GrnCountAttempt.attempt_no.desc())
            .limit(1)
        )

    @staticmethod
    def get_zone_type(db: Session, zone_id: uuid.UUID) -> str | None:
        return db.scalar(  # type: ignore[no-any-return]
            text("SELECT zone_type FROM zones WHERE zone_id = :zid;"), {"zid": zone_id}
        )

    @staticmethod
    def get_category_shelf_life(db: Session, category_id: uuid.UUID) -> tuple[int, str]:
        row = db.execute(
            text(
                "SELECT COALESCE(min_receiving_shelf_life_days, 0), shelf_life_violation_action "
                "FROM item_categories WHERE category_id = :cid;"
            ),
            {"cid": category_id},
        ).first()
        if not row:
            return 0, "WARN"
        return int(row[0]), str(row[1])

    @staticmethod
    def reason_code_exists(db: Session, reason_code: str) -> bool:
        val = db.scalar(
            text("SELECT 1 FROM reason_codes WHERE reason_code = :rc AND is_active = TRUE;"),
            {"rc": reason_code},
        )
        return val is not None

    @staticmethod
    def get_or_create_lot(
        db: Session,
        sku_id: uuid.UUID,
        lot_id: uuid.UUID | None,
        lot_number: str | None,
        manufacture_date: Any,
        expiry_date: Any,
        supplier_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        if lot_id is not None:
            row = db.execute(
                text(
                    "SELECT lot_id, sku_id, lot_number, expiry_date "
                    "FROM lots WHERE lot_id = :lid;"
                ),
                {"lid": lot_id},
            ).first()
            if not row or row[1] != sku_id:
                return {"error": "NOT_FOUND"}
            return {"lot_id": row[0], "lot_number": row[2], "expiry_date": row[3]}

        clean_num = (lot_number or "").strip()
        row = db.execute(
            text(
                "SELECT lot_id, lot_number, expiry_date FROM lots "
                "WHERE sku_id = :sid AND lot_number = :lnum;"
            ),
            {"sid": sku_id, "lnum": clean_num},
        ).first()
        if row:
            if expiry_date is not None and row[2] is not None and row[2] != expiry_date:
                return {"error": "EXPIRY_MISMATCH"}
            return {"lot_id": row[0], "lot_number": row[1], "expiry_date": row[2]}

        new_id = uuid.uuid4()
        db.execute(
            text(
                """
                INSERT INTO lots (
                    lot_id, sku_id, lot_number, manufacture_date, expiry_date, supplier_id
                )
                VALUES (:lid, :sid, :lnum, :mdate, :edate, :sup);
                """
            ),
            {
                "lid": new_id,
                "sid": sku_id,
                "lnum": clean_num,
                "mdate": manufacture_date,
                "edate": expiry_date,
                "sup": supplier_id,
            },
        )
        return {"lot_id": new_id, "lot_number": clean_num, "expiry_date": expiry_date}

    @staticmethod
    def get_first_dock_location(db: Session, warehouse_id: uuid.UUID) -> uuid.UUID | None:
        return db.scalar(  # type: ignore[no-any-return]
            text(
                """
                SELECT l.location_id
                FROM locations l
                JOIN zones z ON z.zone_id = l.zone_id
                WHERE l.warehouse_id = :wh
                  AND z.zone_type = 'RECEIVING_DOCK'
                  AND l.is_active = TRUE
                  AND z.is_active = TRUE
                ORDER BY l.location_code ASC
                LIMIT 1;
                """
            ),
            {"wh": warehouse_id},
        )

    @staticmethod
    def create_pallet(
        db: Session,
        pallet_code: str,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID | None,
        source_grn_id: uuid.UUID,
        status: str,
        created_by: uuid.UUID,
    ) -> uuid.UUID:
        pid = uuid.uuid4()
        db.execute(
            text(
                """
                INSERT INTO pallets (
                    pallet_id, pallet_code, warehouse_id, current_location_id,
                    source_grn_id, status, version_no, created_by
                ) VALUES (
                    :pid, :pcode, :wh, :loc, :grn, CAST(:st AS pallet_status_type), 1, :cby
                );
                """
            ),
            {
                "pid": pid,
                "pcode": pallet_code,
                "wh": warehouse_id,
                "loc": location_id,
                "grn": source_grn_id,
                "st": status,
                "cby": created_by,
            },
        )
        return pid

    @staticmethod
    def update_pallet_status(
        db: Session,
        pallet_id: uuid.UUID,
        status: str,
        location_id: uuid.UUID | None = None,
    ) -> int:
        if location_id is not None:
            ver = db.scalar(
                text(
                    """
                    UPDATE pallets
                    SET status = CAST(:st AS pallet_status_type),
                        current_location_id = :loc,
                        version_no = version_no + 1
                    WHERE pallet_id = :pid
                    RETURNING version_no;
                    """
                ),
                {"pid": pallet_id, "st": status, "loc": location_id},
            )
        else:
            ver = db.scalar(
                text(
                    """
                    UPDATE pallets
                    SET status = CAST(:st AS pallet_status_type),
                        version_no = version_no + 1
                    WHERE pallet_id = :pid
                    RETURNING version_no;
                    """
                ),
                {"pid": pallet_id, "st": status},
            )
        return int(ver or 1)

    @staticmethod
    def get_open_approval_for_grn(db: Session, grn_id: uuid.UUID) -> tuple[uuid.UUID, str] | None:
        row = db.execute(
            text(
                """
                SELECT approval_id, status::text
                FROM approval_requests
                WHERE object_type = 'GRN_DISCREPANCY'
                  AND object_id = :oid
                  AND status IN ('PENDING_D1', 'PENDING_D2', 'PENDING_D3', 'NEED_INFO', 'EXPIRED')
                ORDER BY created_at DESC
                LIMIT 1;
                """
            ),
            {"oid": grn_id},
        ).first()
        if not row:
            return None
        return row[0], str(row[1])

    @staticmethod
    def has_recount_request_history(db: Session, approval_id: uuid.UUID) -> bool:
        val = db.scalar(
            text(
                """
                SELECT 1 FROM approval_histories
                WHERE approval_id = :aid AND action = 'REQUEST_RECOUNT'
                LIMIT 1;
                """
            ),
            {"aid": approval_id},
        )
        return val is not None

    @staticmethod
    def get_pallet_row(db: Session, pallet_id: uuid.UUID) -> dict[str, Any] | None:
        row = db.execute(
            text(
                """
                SELECT pallet_id, pallet_code, warehouse_id, current_location_id,
                       source_grn_id, status::text, version_no
                FROM pallets
                WHERE pallet_id = :pid;
                """
            ),
            {"pid": pallet_id},
        ).first()
        if not row:
            return None
        return {
            "pallet_id": row[0],
            "pallet_code": row[1],
            "warehouse_id": row[2],
            "current_location_id": row[3],
            "source_grn_id": row[4],
            "status": row[5],
            "version_no": row[6],
        }

    @staticmethod
    def get_pallet_balances(db: Session, pallet_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = db.execute(
            text(
                """
                SELECT ib.balance_id, ib.location_id, ib.sku_id, ib.lot_id,
                       ib.serial_number, ib.qty_available, s.storage_requirement
                FROM inventory_balances ib
                JOIN skus s ON s.sku_id = ib.sku_id
                WHERE ib.pallet_id = :pid AND ib.qty_available > 0;
                """
            ),
            {"pid": pallet_id},
        ).fetchall()
        return [
            {
                "balance_id": r[0],
                "location_id": r[1],
                "sku_id": r[2],
                "lot_id": r[3],
                "serial_number": r[4],
                "qty_available": Decimal(str(r[5])),
                "storage_requirement": r[6] or "NORMAL",
            }
            for r in rows
        ]

    @staticmethod
    def suggest_locations_for_pallet(
        db: Session,
        warehouse_id: uuid.UUID,
        exclude_location_id: uuid.UUID | None,
        zone_type: str,
        sku_ids: list[uuid.UUID],
    ) -> list[dict[str, Any]]:
        rows = db.execute(
            text(
                """
                SELECT l.location_id, l.location_code, l.barcode, l.zone_id,
                       z.zone_code, l.status::text, l.current_capacity_pct,
                       EXISTS (
                           SELECT 1 FROM inventory_balances ib
                           WHERE ib.location_id = l.location_id
                             AND ib.sku_id = ANY(:sku_ids)
                             AND ib.qty_available > 0
                       ) AS has_same_sku
                FROM locations l
                JOIN zones z ON z.zone_id = l.zone_id
                WHERE l.warehouse_id = :wh
                  AND z.zone_type = :ztype
                  AND l.is_active = TRUE
                  AND z.is_active = TRUE
                  AND l.status IN ('EMPTY', 'PARTIAL')
                  AND (:excl_loc IS NULL OR l.location_id <> :excl_loc)
                ORDER BY has_same_sku DESC, l.current_capacity_pct DESC, l.location_code ASC
                LIMIT 5;
                """
            ),
            {
                "wh": warehouse_id,
                "ztype": zone_type,
                "sku_ids": sku_ids or [uuid.UUID("00000000-0000-0000-0000-000000000000")],
                "excl_loc": exclude_location_id,
            },
        ).fetchall()
        return [
            {
                "location_id": str(r[0]),
                "location_code": r[1],
                "barcode": r[2],
                "zone_id": str(r[3]),
                "zone_code": r[4],
                "status": r[5],
                "current_capacity_pct": f"{Decimal(str(r[6])):.2f}",
                "same_sku_consolidation": bool(r[7]),
            }
            for r in rows
        ]

    @staticmethod
    def get_pallet_balances_at_location(
        db: Session, pallet_id: uuid.UUID, location_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = db.execute(
            text(
                """
                SELECT ib.balance_id, ib.location_id, ib.sku_id, ib.lot_id,
                       ib.serial_number, ib.qty_available, s.storage_requirement
                FROM inventory_balances ib
                JOIN skus s ON s.sku_id = ib.sku_id
                WHERE ib.pallet_id = :pid
                  AND ib.location_id = :loc_id
                  AND ib.qty_available > 0;
                """
            ),
            {"pid": pallet_id, "loc_id": location_id},
        ).fetchall()
        return [
            {
                "balance_id": r[0],
                "location_id": r[1],
                "sku_id": r[2],
                "lot_id": r[3],
                "serial_number": r[4],
                "qty_available": Decimal(str(r[5])),
                "storage_requirement": r[6],
            }
            for r in rows
        ]

    @staticmethod
    def get_open_putaway_task(db: Session, pallet_id: uuid.UUID) -> dict[str, Any] | None:
        row = db.execute(
            text(
                """
                SELECT task_id, status::text, assigned_to, version_no
                FROM tasks
                WHERE ref_doc_type = 'PALLET'
                  AND ref_doc_id = :pid
                  AND task_type = 'PUTAWAY'
                  AND status NOT IN ('COMPLETED', 'CANCELLED')
                ORDER BY created_at DESC
                LIMIT 1;
                """
            ),
            {"pid": pallet_id},
        ).first()
        if not row:
            return None
        return {
            "task_id": row[0],
            "status": row[1],
            "assigned_to": row[2],
            "version_no": int(row[3]),
        }
