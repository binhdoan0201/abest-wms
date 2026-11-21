"""ABEST WMS - Services cho Phân hệ Xuất kho (Outbound)."""

import uuid

from sqlalchemy.orm import Session

from server.app.core.exceptions import BusinessError
from server.app.modules.outbound.models import OutboundOrder
from server.app.modules.outbound.repositories import OutboundRepository


class OutboundService:
    """Service điều phối quy trình xuất kho, cấp phát, lấy hàng và đóng gói."""

    @staticmethod
    def get_order(db: Session, order_id: uuid.UUID) -> OutboundOrder:
        order = OutboundRepository.get_order_by_id(db, order_id)
        if not order:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy đơn xuất kho", http_status=404
            )
        return order
