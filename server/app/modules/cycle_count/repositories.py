"""ABEST WMS - Repositories cho Phân hệ Kiểm kê (Cycle Count)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.app.modules.cycle_count.models import CycleCountLine, CycleCountSheet


class CycleCountRepository:
    """Repository truy vấn các phiếu kiểm kê và dòng kiểm kê."""

    @staticmethod
    def get_sheet_by_id(db: Session, sheet_id: uuid.UUID) -> CycleCountSheet | None:
        return db.scalar(select(CycleCountSheet).where(CycleCountSheet.count_sheet_id == sheet_id))

    @staticmethod
    def list_lines(db: Session, sheet_id: uuid.UUID) -> list[CycleCountLine]:
        return list(
            db.scalars(
                select(CycleCountLine).where(CycleCountLine.count_sheet_id == sheet_id)
            ).all()
        )
