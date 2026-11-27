"""ABEST WMS - Hàm nhận chứng từ ERP (PO, ASN) cho module Nhập kho (Inbound)."""

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from server.app.core.exceptions import BusinessError
from server.app.modules.inbound.models import Asn, POLine, PurchaseOrder
from server.app.modules.inbound.repositories import InboundRepository
from server.app.modules.master_data import convert_to_base_uom, get_location, get_sku


def _validation_error(message: str) -> BusinessError:
    return BusinessError(code="VALIDATION_ERROR", message=message, http_status=422)


def _to_decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise _validation_error(f"{field} không phải số hợp lệ") from None


def receive_purchase_order(db: Session, data: dict[str, Any], actor_id: uuid.UUID) -> uuid.UUID:
    """Tạo `purchase_orders` và `po_lines` từ dữ liệu PO của ERP."""
    erp_po_number = str(data["erp_po_number"]).strip()
    if InboundRepository.get_po_by_erp_number(db, erp_po_number) is not None:
        raise BusinessError(
            code="INBOUND_PO_DUPLICATE",
            message=f"Số PO {erp_po_number} đã tồn tại",
            http_status=409,
        )

    lines = data.get("lines") or []
    if not lines:
        raise _validation_error("PO phải có ít nhất một dòng")

    expected_raw = data.get("expected_date")
    po = PurchaseOrder(
        erp_po_number=erp_po_number,
        warehouse_id=uuid.UUID(str(data["warehouse_id"])),
        supplier_id=uuid.UUID(str(data["supplier_id"])),
        expected_date=date.fromisoformat(str(expected_raw)) if expected_raw else None,
    )
    db.add(po)
    db.flush()

    for raw in lines:
        sku_id = uuid.UUID(str(raw["sku_id"]))
        uom_code = str(raw["uom_code"]).strip()
        qty = _to_decimal(raw["qty_ordered"], "qty_ordered")
        if qty <= 0:
            raise _validation_error("qty_ordered phải lớn hơn 0")
        get_sku(db, sku_id)
        convert_to_base_uom(db, sku_id, uom_code, qty)
        db.add(
            POLine(
                po_id=po.po_id,
                line_number=int(raw["line_number"]),
                sku_id=sku_id,
                uom_code=uom_code,
                qty_ordered=qty,
            )
        )
    db.flush()
    return po.po_id


def receive_asn(db: Session, data: dict[str, Any], actor_id: uuid.UUID) -> uuid.UUID:
    """Tạo `asns` từ dữ liệu ASN của ERP (tự tra PO theo `erp_po_number`)."""
    erp_asn_number = str(data["erp_asn_number"]).strip()
    if InboundRepository.get_asn_by_erp_number(db, erp_asn_number) is not None:
        raise BusinessError(
            code="INBOUND_ASN_DUPLICATE",
            message=f"Số ASN {erp_asn_number} đã tồn tại",
            http_status=409,
        )

    warehouse_id = uuid.UUID(str(data["warehouse_id"]))
    supplier_id = uuid.UUID(str(data["supplier_id"])) if data.get("supplier_id") else None

    po_id: uuid.UUID | None = None
    erp_po_number = data.get("erp_po_number")
    if erp_po_number:
        po = InboundRepository.get_po_by_erp_number(db, str(erp_po_number).strip())
        if po is None or po.warehouse_id != warehouse_id:
            raise BusinessError(
                code="NOT_FOUND",
                message=f"Không tìm thấy PO {erp_po_number} trong kho nhận",
                http_status=404,
            )
        if supplier_id is not None and supplier_id != po.supplier_id:
            raise BusinessError(
                code="INBOUND_PO_ASN_MISMATCH",
                message="Nhà cung cấp trên ASN không khớp với PO",
                http_status=409,
            )
        po_id = po.po_id
        supplier_id = supplier_id or po.supplier_id

    dock_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    if data.get("assigned_dock_location_id"):
        dock_id = uuid.UUID(str(data["assigned_dock_location_id"]))
        location = get_location(db, dock_id, warehouse_id)
        raw_zone = location.get("zone_id")
        if raw_zone:
            zone_id = uuid.UUID(str(raw_zone))
            zone_type = InboundRepository.get_zone_type(db, zone_id)
            if zone_type != "RECEIVING_DOCK":
                raise BusinessError(
                    code="INBOUND_INVALID_DOCK_ZONE",
                    message="Cửa nhận chỉ định không thuộc khu vực RECEIVING_DOCK",
                    http_status=422,
                )

    pallets = data.get("expected_pallets")
    asn = Asn(
        erp_asn_number=erp_asn_number,
        warehouse_id=warehouse_id,
        po_id=po_id,
        supplier_id=supplier_id,
        assigned_dock_location_id=dock_id,
        assigned_zone_id=zone_id,
        expected_arrival_at=datetime.fromisoformat(str(data["expected_arrival_at"])),
        expected_pallets=int(pallets) if pallets is not None else None,
        status="SCHEDULED",
    )
    db.add(asn)
    db.flush()
    return asn.asn_id
