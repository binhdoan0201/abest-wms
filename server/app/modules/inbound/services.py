"""ABEST WMS - Services cho Phân hệ Nhập kho (Inbound)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, enforce_warehouse_scope
from server.app.modules.inbound.models import PO_STATUSES, Asn, Grn, POLine, PurchaseOrder
from server.app.modules.inbound.repositories import InboundRepository

MAX_PAGE_SIZE = 100
ASN_STATUSES = ("SCHEDULED", "ARRIVED", "RECEIVING", "COMPLETED", "CANCELLED")
PO_SORT_FIELDS = ("created_at", "expected_date", "erp_po_number")
ASN_SORT_FIELDS = ("created_at", "expected_arrival_at")
HIDE_QTY_ROLE = "nv-nhan"  # đặc tả 5.4.9: nv-nhan không thấy số lượng đặt, đã nhận của PO


def _validation_error(message: str, **details: Any) -> BusinessError:
    return BusinessError(
        code="VALIDATION_ERROR", message=message, http_status=422, details=details
    )


def _fmt_qty(value: Decimal | None) -> str | None:
    """Số lượng trả về dạng chuỗi 3 chữ số thập phân (chuẩn API mục 2)."""
    return None if value is None else f"{value:.3f}"


def _iso(value: date | datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _parse_paging(page: int, page_size: int) -> tuple[int, int]:
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise _validation_error(f"page phải >= 1 và page_size trong khoảng 1 đến {MAX_PAGE_SIZE}")
    return page, page_size


def _parse_sort(sort: str | None, allowed: tuple[str, ...], default: str) -> tuple[str, bool]:
    raw = sort or default
    descending = raw.startswith("-")
    name = raw.lstrip("-")
    if name not in allowed:
        raise _validation_error(f"Không sắp xếp được theo `{name}`", allowed=list(allowed))
    return name, descending


def _require_warehouse(user: UserContext) -> uuid.UUID:
    if user.warehouse_id is None:
        raise BusinessError(
            code="FORBIDDEN",
            message="Tài khoản chưa được gán kho để xem chứng từ nhập kho",
            http_status=403,
        )
    return user.warehouse_id


def _po_dict(po: PurchaseOrder) -> dict[str, Any]:
    return {
        "po_id": str(po.po_id),
        "erp_po_number": po.erp_po_number,
        "warehouse_id": str(po.warehouse_id),
        "supplier_id": str(po.supplier_id),
        "status": po.status,
        "expected_date": _iso(po.expected_date),
        "version_no": po.version_no,
        "created_at": _iso(po.created_at),
    }


def _po_line_dict(line: POLine, hide_qty: bool) -> dict[str, Any]:
    return {
        "po_line_id": str(line.po_line_id),
        "line_number": line.line_number,
        "sku_id": str(line.sku_id),
        "uom_code": line.uom_code,
        "qty_ordered": None if hide_qty else _fmt_qty(line.qty_ordered),
        "qty_received": None if hide_qty else _fmt_qty(line.qty_received),
        "version_no": line.version_no,
    }


def _asn_dict(asn: Asn) -> dict[str, Any]:
    return {
        "asn_id": str(asn.asn_id),
        "erp_asn_number": asn.erp_asn_number,
        "warehouse_id": str(asn.warehouse_id),
        "po_id": str(asn.po_id) if asn.po_id else None,
        "supplier_id": str(asn.supplier_id) if asn.supplier_id else None,
        "assigned_dock_location_id": (
            str(asn.assigned_dock_location_id) if asn.assigned_dock_location_id else None
        ),
        "assigned_zone_id": str(asn.assigned_zone_id) if asn.assigned_zone_id else None,
        "expected_arrival_at": _iso(asn.expected_arrival_at),
        "actual_arrival_at": _iso(asn.actual_arrival_at),
        "expected_pallets": asn.expected_pallets,
        "status": asn.status,
        "source_outbound_order_id": (
            str(asn.source_outbound_order_id) if asn.source_outbound_order_id else None
        ),
        "created_at": _iso(asn.created_at),
    }


class InboundService:
    """Service điều phối nghiệp vụ nhập kho, kiểm đếm và cất hàng."""

    @staticmethod
    def list_purchase_orders(
        db: Session,
        user: UserContext,
        status: str | None,
        supplier_id: uuid.UUID | None,
        sort: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        """Danh sách PO của kho người dùng; lọc `status`, `supplier_id`, có phân trang."""
        warehouse_id = _require_warehouse(user)
        page, page_size = _parse_paging(page, page_size)
        if status is not None and status not in PO_STATUSES:
            raise _validation_error("Giá trị lọc `status` không hợp lệ", allowed=list(PO_STATUSES))
        sort_name, descending = _parse_sort(sort, PO_SORT_FIELDS, "-created_at")
        rows, total = InboundRepository.list_pos(
            db,
            warehouse_id,
            status,
            supplier_id,
            sort_name,
            descending,
            (page - 1) * page_size,
            page_size,
        )
        return [_po_dict(po) for po in rows], total, page, page_size

    @staticmethod
    def get_purchase_order(db: Session, user: UserContext, po_id: uuid.UUID) -> dict[str, Any]:
        """Chi tiết PO kèm dòng; số lượng ẩn với nv-nhan."""
        _require_warehouse(user)
        po = InboundRepository.get_po_by_id(db, po_id)
        if po is None:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy PO", http_status=404)
        enforce_warehouse_scope(user, po.warehouse_id)
        hide_qty = user.role_code == HIDE_QTY_ROLE
        lines = InboundRepository.get_po_lines(db, po_id)
        result = _po_dict(po)
        result["lines"] = [_po_line_dict(line, hide_qty) for line in lines]
        return result

    @staticmethod
    def list_asns(
        db: Session,
        user: UserContext,
        status: str | None,
        po_id: uuid.UUID | None,
        sort: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        """Danh sách ASN của kho người dùng; lọc `status`, `po_id`, có phân trang."""
        warehouse_id = _require_warehouse(user)
        page, page_size = _parse_paging(page, page_size)
        if status is not None and status not in ASN_STATUSES:
            raise _validation_error(
                "Giá trị lọc `status` không hợp lệ", allowed=list(ASN_STATUSES)
            )
        sort_name, descending = _parse_sort(sort, ASN_SORT_FIELDS, "-created_at")
        rows, total = InboundRepository.list_asns(
            db,
            warehouse_id,
            status,
            po_id,
            sort_name,
            descending,
            (page - 1) * page_size,
            page_size,
        )
        return [_asn_dict(asn) for asn in rows], total, page, page_size

    @staticmethod
    def get_grn(db: Session, grn_id: uuid.UUID) -> Grn:
        grn = InboundRepository.get_grn_by_id(db, grn_id)
        if not grn:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy GRN", http_status=404)
        return grn
