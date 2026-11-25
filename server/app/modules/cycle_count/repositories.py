"""ABEST WMS - Repositories cho Phân hệ Kiểm kê (Cycle Count)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from server.app.modules.cycle_count.models import (
    CycleCountAttempt,
    CycleCountLine,
    CycleCountSheet,
)


class CycleCountRepository:
    """Repository truy vấn các phiếu kiểm kê và dòng kiểm kê."""

    @staticmethod
    def get_sheet_by_id(
        db: Session, sheet_id: uuid.UUID, for_update: bool = False
    ) -> CycleCountSheet | None:
        stmt = select(CycleCountSheet).where(CycleCountSheet.count_sheet_id == sheet_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.scalar(stmt)

    @staticmethod
    def list_sheets(
        db: Session,
        warehouse_id: uuid.UUID,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[CycleCountSheet], int]:
        conditions = [CycleCountSheet.warehouse_id == warehouse_id]
        if status is not None:
            conditions.append(CycleCountSheet.status == status)
        total = db.scalar(select(func.count()).select_from(CycleCountSheet).where(*conditions))
        rows = db.scalars(
            select(CycleCountSheet)
            .where(*conditions)
            .order_by(CycleCountSheet.created_at.desc(), CycleCountSheet.count_sheet_id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows), int(total or 0)

    @staticmethod
    def list_lines(db: Session, sheet_id: uuid.UUID) -> list[CycleCountLine]:
        return list(
            db.scalars(
                select(CycleCountLine).where(CycleCountLine.count_sheet_id == sheet_id)
            ).all()
        )

    @staticmethod
    def get_line_by_id(
        db: Session, line_id: uuid.UUID, for_update: bool = False
    ) -> CycleCountLine | None:
        stmt = select(CycleCountLine).where(CycleCountLine.count_line_id == line_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.scalar(stmt)

    @staticmethod
    def get_latest_attempt(db: Session, line_id: uuid.UUID) -> CycleCountAttempt | None:
        return db.scalar(
            select(CycleCountAttempt)
            .where(CycleCountAttempt.count_line_id == line_id)
            .order_by(CycleCountAttempt.attempt_no.desc())
            .limit(1)
        )

    @staticmethod
    def lock_location_for_count(
        db: Session, warehouse_id: uuid.UUID, location_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        loc_row = db.execute(
            text(
                """
                SELECT location_id, status::text
                FROM locations
                WHERE location_id = :loc AND warehouse_id = :wh
                FOR UPDATE;
                """
            ),
            {"loc": location_id, "wh": warehouse_id},
        ).first()
        if not loc_row:
            return [{"error": "NOT_FOUND"}]
        if loc_row[1] == "MAINTENANCE_LOCKED":
            return [{"error": "MAINTENANCE_LOCKED"}]

        db.execute(
            text(
                """
                UPDATE locations
                SET status = 'COUNTING_LOCKED',
                    lock_reason = 'Khóa phục vụ kiểm kê',
                    locked_by = :uid,
                    locked_at = NOW()
                WHERE location_id = :loc;
                """
            ),
            {"loc": location_id, "uid": user_id},
        )

        bals = db.execute(
            text(
                """
                SELECT sku_id, lot_id, pallet_id,
                       (qty_available + qty_allocated + qty_locked) AS sys_qty
                FROM inventory_balances
                WHERE warehouse_id = :wh AND location_id = :loc
                  AND (qty_available + qty_allocated + qty_locked) > 0;
                """
            ),
            {"wh": warehouse_id, "loc": location_id},
        ).fetchall()

        return [
            {
                "sku_id": r[0],
                "lot_id": r[1],
                "pallet_id": r[2],
                "sys_qty": Decimal(str(r[3])),
            }
            for r in bals
        ]

    @staticmethod
    def unlock_sheet_locations(db: Session, sheet_id: uuid.UUID) -> None:
        locs = db.scalars(
            text(
                """
                SELECT DISTINCT ccl.location_id
                FROM cycle_count_lines ccl
                JOIN locations l ON l.location_id = ccl.location_id
                WHERE ccl.count_sheet_id = :sid
                  AND l.status = 'COUNTING_LOCKED'
                  AND NOT EXISTS (
                      SELECT 1 FROM cycle_count_lines o
                      WHERE o.location_id = ccl.location_id
                        AND o.count_sheet_id <> :sid
                        AND o.status NOT IN ('AUTO_APPROVED_Z', 'ADJUSTED', 'REJECTED', 'APPROVED')
                  );
                """
            ),
            {"sid": sheet_id},
        ).all()
        for loc_id in locs:
            db.execute(
                text(
                    """
                    UPDATE locations
                    SET status = 'PARTIAL', lock_reason = NULL, locked_by = NULL, locked_at = NULL
                    WHERE location_id = :loc;
                    """
                ),
                {"loc": loc_id},
            )
            db.execute(text("SELECT fn_refresh_location_status(:loc);"), {"loc": loc_id})
