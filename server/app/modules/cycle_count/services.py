"""ABEST WMS - Services cho Phân hệ Kiểm kê (Cycle Count)."""

import uuid

from sqlalchemy.orm import Session

from server.app.core.exceptions import BusinessError
from server.app.modules.cycle_count.models import CycleCountSheet
from server.app.modules.cycle_count.repositories import CycleCountRepository


class CycleCountService:
    """Service điều phối quy trình kiểm kê đếm mù, đếm lại và chốt kết quả."""

    @staticmethod
    def get_sheet(db: Session, sheet_id: uuid.UUID) -> CycleCountSheet:
        sheet = CycleCountRepository.get_sheet_by_id(db, sheet_id)
        if not sheet:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy phiếu kiểm kê", http_status=404
            )
        return sheet
