"""ABEST WMS - Repositories cho Phân hệ Nhập kho (Inbound)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.app.modules.inbound.models import Asn, Grn, PurchaseOrder


class InboundRepository:
    """Repository truy vấn các chứng từ và dữ liệu nhập kho."""

    @staticmethod
    def get_po_by_id(db: Session, po_id: uuid.UUID) -> PurchaseOrder | None:
        return db.scalar(select(PurchaseOrder).where(PurchaseOrder.po_id == po_id))

    @staticmethod
    def get_asn_by_id(db: Session, asn_id: uuid.UUID) -> Asn | None:
        return db.scalar(select(Asn).where(Asn.asn_id == asn_id))

    @staticmethod
    def get_grn_by_id(db: Session, grn_id: uuid.UUID) -> Grn | None:
        return db.scalar(select(Grn).where(Grn.grn_id == grn_id))
