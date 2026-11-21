"""ABEST WMS - Services cho Phân hệ Nhập kho (Inbound)."""

import uuid

from sqlalchemy.orm import Session

from server.app.core.exceptions import BusinessError
from server.app.modules.inbound.models import Grn
from server.app.modules.inbound.repositories import InboundRepository


class InboundService:
    """Service điều phối nghiệp vụ nhập kho, kiểm đếm và cất hàng."""

    @staticmethod
    def get_grn(db: Session, grn_id: uuid.UUID) -> Grn:
        grn = InboundRepository.get_grn_by_id(db, grn_id)
        if not grn:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy GRN", http_status=404)
        return grn
