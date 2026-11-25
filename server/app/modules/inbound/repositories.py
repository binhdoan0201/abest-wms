"""ABEST WMS - Repositories cho Phân hệ Nhập kho (Inbound)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.app.modules.inbound.models import Asn, Grn, POLine, PurchaseOrder


class InboundRepository:
    """Repository truy vấn các chứng từ và dữ liệu nhập kho."""

    @staticmethod
    def get_po_by_id(db: Session, po_id: uuid.UUID) -> PurchaseOrder | None:
        return db.scalar(select(PurchaseOrder).where(PurchaseOrder.po_id == po_id))

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
    def get_asn_by_id(db: Session, asn_id: uuid.UUID) -> Asn | None:
        return db.scalar(select(Asn).where(Asn.asn_id == asn_id))

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
    def get_grn_by_id(db: Session, grn_id: uuid.UUID) -> Grn | None:
        return db.scalar(select(Grn).where(Grn.grn_id == grn_id))
