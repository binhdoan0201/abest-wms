"""ABEST WMS - Services cho Phân hệ Nhập kho (Inbound)."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from server.app.core.audit import create_audit_log
from server.app.core.exceptions import BusinessError, translate_db_error
from server.app.core.rbac import UserContext, enforce_warehouse_scope
from server.app.modules.approvals import (
    create_approval_request,
    mark_object_approval_executed,
    supersede_approval_for_recount,
)
from server.app.modules.inbound.models import (
    PO_STATUSES,
    Asn,
    Grn,
    GrnCountAttempt,
    GrnLine,
    POLine,
    PurchaseOrder,
)
from server.app.modules.inbound.repositories import InboundRepository
from server.app.modules.inbound.schemas import (
    CompleteGrnRequest,
    CreateGrnRequest,
    GrnLineCountRequest,
    PutawayConfirmRequest,
    PutawaySuggestRequest,
    RecountGrnRequest,
    SubmitGrnRequest,
)
from server.app.modules.integrations import enqueue_to_erp
from server.app.modules.inventory import apply_movement, transfer_inventory
from server.app.modules.master_data import (
    convert_to_base_uom,
    get_location,
    get_sku,
    get_warehouse_config,
)
from server.app.modules.tasks import accept_task, assign_task, complete_task, create_task

MAX_PAGE_SIZE = 100
ASN_STATUSES = ("SCHEDULED", "ARRIVED", "RECEIVING", "COMPLETED", "CANCELLED")
GRN_STATUSES = (
    "DRAFT",
    "COUNTING",
    "PENDING_D1",
    "PENDING_D2",
    "PENDING_D3",
    "APPROVED",
    "REJECTED",
    "CLOSED",
)
PO_SORT_FIELDS = ("created_at", "expected_date", "erp_po_number")
ASN_SORT_FIELDS = ("created_at", "expected_arrival_at")
HIDE_QTY_ROLE = "nv-nhan"


def _task_req(**kwargs: Any) -> Any:
    return SimpleNamespace(**kwargs)


def _validation_error(message: str, **details: Any) -> BusinessError:
    return BusinessError(code="VALIDATION_ERROR", message=message, http_status=422, details=details)


def _fmt_qty(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.3f}"


def _fmt_money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


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
            message="Tài khoản chưa được gán kho để thao tác chứng từ nhập kho",
            http_status=403,
        )
    return user.warehouse_id


def _require_write_access(access_type: str) -> None:
    if access_type not in ("X", "X_OWN"):
        raise BusinessError(
            code="FORBIDDEN",
            message="Vai trò hiện tại chỉ có quyền xem, không được phép ghi chứng từ nhập kho",
            http_status=403,
        )


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


def _grn_dict(grn: Grn, hide_blind: bool) -> dict[str, Any]:
    return {
        "grn_id": str(grn.grn_id),
        "grn_number": grn.grn_number,
        "warehouse_id": str(grn.warehouse_id),
        "po_id": str(grn.po_id) if grn.po_id else None,
        "asn_id": str(grn.asn_id) if grn.asn_id else None,
        "is_blind_receipt": grn.is_blind_receipt,
        "received_by": str(grn.received_by),
        "started_at": _iso(grn.started_at),
        "status": grn.status,
        "has_discrepancy": None if hide_blind else grn.has_discrepancy,
        "total_discrepancy_amount": (
            None if hide_blind else _fmt_money(grn.total_discrepancy_amount)
        ),
        "recount_count": grn.recount_count,
        "version_no": grn.version_no,
        "closed_at": _iso(grn.closed_at),
        "created_at": _iso(grn.created_at),
    }


def _grn_line_dict(line: GrnLine, hide_blind: bool) -> dict[str, Any]:
    return {
        "grn_line_id": str(line.grn_line_id),
        "grn_id": str(line.grn_id),
        "po_line_id": str(line.po_line_id) if line.po_line_id else None,
        "sku_id": str(line.sku_id),
        "lot_id": str(line.lot_id) if line.lot_id else None,
        "pallet_id": str(line.pallet_id) if line.pallet_id else None,
        "damaged_pallet_id": str(line.damaged_pallet_id) if line.damaged_pallet_id else None,
        "uom_code": line.uom_code,
        "qty_expected": None if hide_blind else _fmt_qty(line.qty_expected),
        "qty_actual": _fmt_qty(line.qty_actual),
        "qty_damaged": _fmt_qty(line.qty_damaged),
        "qty_variance": None if hide_blind else _fmt_qty(line.qty_variance),
        "variance_amount": None if hide_blind else _fmt_money(line.variance_amount),
        "serial_numbers": line.serial_numbers or [],
        "is_quarantined": line.is_quarantined,
        "reason_code": line.reason_code,
        "damage_photo_urls": line.damage_photo_urls or [],
        "notes": line.notes,
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
        warehouse_id = _require_warehouse(user)
        page, page_size = _parse_paging(page, page_size)
        if status is not None and status not in ASN_STATUSES:
            raise _validation_error("Giá trị lọc `status` không hợp lệ", allowed=list(ASN_STATUSES))
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

    # ------------------------------------------------------------------ B-04: GRN
    @staticmethod
    def create_grn(
        db: Session,
        user: UserContext,
        access_type: str,
        req: CreateGrnRequest,
    ) -> dict[str, Any]:
        _require_write_access(access_type)
        warehouse_id = _require_warehouse(user)
        cfg = get_warehouse_config(db, warehouse_id)

        po: PurchaseOrder | None = None
        asn: Asn | None = None

        if req.asn_id is not None:
            asn = InboundRepository.get_asn_by_id(db, req.asn_id, for_update=True)
            if asn is None:
                raise BusinessError(code="NOT_FOUND", message="Không tìm thấy ASN", http_status=404)
            enforce_warehouse_scope(user, asn.warehouse_id)
            if asn.status in ("COMPLETED", "CANCELLED"):
                raise BusinessError(
                    code="INBOUND_ASN_CLOSED",
                    message=f"ASN đang ở trạng thái {asn.status}, không thể mở phiếu nhận",
                    http_status=409,
                )
            if req.po_id is not None and asn.po_id is not None and req.po_id != asn.po_id:
                raise BusinessError(
                    code="INBOUND_PO_ASN_MISMATCH",
                    message="PO và ASN không khớp nhau",
                    http_status=409,
                )
            effective_po_id = req.po_id or asn.po_id
        else:
            effective_po_id = req.po_id

        if effective_po_id is not None:
            po = InboundRepository.get_po_by_id(db, effective_po_id, for_update=True)
            if po is None:
                raise BusinessError(code="NOT_FOUND", message="Không tìm thấy PO", http_status=404)
            enforce_warehouse_scope(user, po.warehouse_id)
            if po.status in ("CLOSED", "CANCELLED", "FULLY_RECEIVED"):
                raise BusinessError(
                    code="INBOUND_PO_CLOSED",
                    message=f"PO đang ở trạng thái {po.status}, không thể mở phiếu nhận",
                    http_status=409,
                )
        elif asn is None:
            # Nhận không PO và không ASN
            if cfg.get("blind_receipt_policy") == "REJECT":
                raise BusinessError(
                    code="INBOUND_NO_PO_NOT_ALLOWED",
                    message="Kho cấu hình từ chối nhận hàng không có PO/ASN",
                    http_status=409,
                )

        now = datetime.now(timezone.utc)
        grn_number = f"GRN-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        is_blind = True if req.is_blind_receipt is None else req.is_blind_receipt

        grn = Grn(
            grn_number=grn_number,
            warehouse_id=warehouse_id,
            po_id=po.po_id if po else None,
            asn_id=asn.asn_id if asn else None,
            is_blind_receipt=is_blind,
            received_by=user.user_id,
            started_at=now,
            status="COUNTING",
            version_no=1,
        )
        db.add(grn)
        if po is not None and po.status == "PENDING":
            po.status = "RECEIVING"
            po.version_no += 1
        if asn is not None and asn.status in ("SCHEDULED", "ARRIVED"):
            asn.status = "RECEIVING"
            if asn.actual_arrival_at is None:
                asn.actual_arrival_at = now
        db.flush()

        create_audit_log(
            db,
            action_code="CREATE_DOC",
            entity_name="grns",
            actor_user_id=user.user_id,
            warehouse_id=warehouse_id,
            entity_id=grn.grn_id,
            new_values={"grn_number": grn.grn_number, "status": grn.status},
        )
        hide_blind = grn.is_blind_receipt and user.role_code == HIDE_QTY_ROLE
        res = _grn_dict(grn, hide_blind)
        res["lines"] = []
        return res

    @staticmethod
    def list_grns(
        db: Session,
        user: UserContext,
        status: str | None,
        po_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        warehouse_id = _require_warehouse(user)
        page, page_size = _parse_paging(page, page_size)
        if status is not None and status not in GRN_STATUSES:
            raise _validation_error("Giá trị lọc `status` không hợp lệ", allowed=list(GRN_STATUSES))

        owner_filter = user.user_id if user.role_code == HIDE_QTY_ROLE else None
        rows, total = InboundRepository.list_grns(
            db, warehouse_id, status, po_id, owner_filter, (page - 1) * page_size, page_size
        )
        recountable_ids = InboundRepository.list_recountable_grn_ids(db, [g.grn_id for g in rows])
        items: list[dict[str, Any]] = []
        for g in rows:
            item = _grn_dict(g, g.is_blind_receipt and user.role_code == HIDE_QTY_ROLE)
            item["can_recount"] = g.grn_id in recountable_ids
            items.append(item)
        return items, total, page, page_size

    @staticmethod
    def get_grn_detail(db: Session, user: UserContext, grn_id: uuid.UUID) -> dict[str, Any]:
        _require_warehouse(user)
        grn = InboundRepository.get_grn_by_id(db, grn_id)
        if grn is None:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy GRN", http_status=404)
        enforce_warehouse_scope(user, grn.warehouse_id)
        can_recount_view = grn.status.startswith("PENDING_D") or grn.recount_count > 0
        if (
            user.role_code == HIDE_QTY_ROLE
            and grn.received_by != user.user_id
            and not can_recount_view
        ):
            raise BusinessError(
                code="FORBIDDEN",
                message="Nhân viên nhận hàng chỉ được xem phiếu của chính mình",
                http_status=403,
            )
        can_recount = grn_id in InboundRepository.list_recountable_grn_ids(db, [grn_id])
        hide_blind = grn.is_blind_receipt and user.role_code == HIDE_QTY_ROLE
        lines = InboundRepository.get_grn_lines(db, grn_id)
        res = _grn_dict(grn, hide_blind)
        res["can_recount"] = can_recount
        res["lines"] = [_grn_line_dict(ln, hide_blind) for ln in lines]
        return res

    @staticmethod
    def add_grn_line(
        db: Session,
        user: UserContext,
        access_type: str,
        grn_id: uuid.UUID,
        req: GrnLineCountRequest,
    ) -> dict[str, Any]:
        _require_write_access(access_type)
        _require_warehouse(user)
        grn = InboundRepository.get_grn_by_id(db, grn_id, for_update=True)
        if grn is None:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy GRN", http_status=404)
        enforce_warehouse_scope(user, grn.warehouse_id)
        can_recount_view = grn.status.startswith("PENDING_D") or grn.recount_count > 0
        if (
            user.role_code == HIDE_QTY_ROLE
            and grn.received_by != user.user_id
            and not can_recount_view
        ):
            raise BusinessError(
                code="FORBIDDEN",
                message="Bạn chỉ được thao tác trên phiếu GRN của chính mình",
                http_status=403,
            )
        if grn.status != "COUNTING":
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Phiếu GRN đang ở trạng thái {grn.status}, không thể thêm dòng đếm",
                http_status=409,
            )
        if grn.version_no != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Phiên bản phiếu GRN đã thay đổi",
                http_status=409,
                details={"current_version_no": grn.version_no},
            )

        if req.qty_actual <= 0 or req.qty_damaged < 0 or req.qty_damaged > req.qty_actual:
            raise _validation_error("Số lượng đếm phải > 0 và 0 <= qty_damaged <= qty_actual")

        if req.qty_damaged > 0:
            if not req.reason_code or not InboundRepository.reason_code_exists(db, req.reason_code):
                raise BusinessError(
                    code="INBOUND_REASON_REQUIRED",
                    message="Hàng hư hỏng bắt buộc chọn mã lý do hợp lệ",
                    http_status=422,
                )

        sku = get_sku(db, req.sku_id)
        base_actual = convert_to_base_uom(db, req.sku_id, req.uom_code.strip(), req.qty_actual)
        base_damaged = convert_to_base_uom(db, req.sku_id, req.uom_code.strip(), req.qty_damaged)

        # Kiểm tra Serial
        serials = req.serial_numbers or []
        if sku.get("is_serial_tracked"):
            if req.qty_damaged > 0:
                raise BusinessError(
                    code="INBOUND_SERIAL_MISMATCH",
                    message="SKU quản lý serial chưa hỗ trợ ghi nhận hàng hư trên cùng dòng",
                    http_status=422,
                )
            if len(serials) != int(base_actual) or len(set(serials)) != len(serials):
                raise BusinessError(
                    code="INBOUND_SERIAL_MISMATCH",
                    message="Danh sách serial phải khớp chính xác số lượng thực nhận và không trùng",  # noqa: E501
                    http_status=422,
                )
        elif serials:
            raise BusinessError(
                code="INBOUND_SERIAL_MISMATCH",
                message="SKU không bật quản lý serial",
                http_status=422,
            )

        # Kiểm tra Lô & Hạn sử dụng
        lot_id: uuid.UUID | None = None
        if sku.get("is_lot_tracked"):
            if req.lot_id is None and not (req.lot_number and req.lot_number.strip()):
                raise BusinessError(
                    code="INBOUND_LOT_REQUIRED",
                    message="SKU bắt buộc quản lý lô, vui lòng nhập lot_id hoặc lot_number",
                    http_status=422,
                )
            if sku.get("is_expiry_tracked") and req.lot_id is None and req.expiry_date is None:
                raise BusinessError(
                    code="INBOUND_EXPIRY_REQUIRED",
                    message="SKU bắt buộc quản lý hạn dùng, vui lòng nhập expiry_date",
                    http_status=422,
                )
            supplier_id: uuid.UUID | None = None
            if grn.po_id:
                po_obj = InboundRepository.get_po_by_id(db, grn.po_id)
                supplier_id = po_obj.supplier_id if po_obj else None
            lot_res = InboundRepository.get_or_create_lot(
                db,
                req.sku_id,
                req.lot_id,
                req.lot_number,
                req.manufacture_date,
                req.expiry_date,
                supplier_id,
            )
            if lot_res.get("error") == "NOT_FOUND":
                raise BusinessError(
                    code="NOT_FOUND", message="Không tìm thấy lô hàng", http_status=404
                )
            if lot_res.get("error") == "EXPIRY_MISMATCH":
                raise BusinessError(
                    code="INBOUND_LOT_EXPIRY_MISMATCH",
                    message="Số lô đã tồn tại với hạn sử dụng khác",
                    http_status=409,
                )
            lot_id = lot_res["lot_id"]
            exp_date: date | None = lot_res.get("expiry_date")
            if exp_date is not None and sku.get("category_id"):
                min_days, action = InboundRepository.get_category_shelf_life(db, sku["category_id"])
                rem_days = (exp_date - date.today()).days
                if rem_days < min_days and action == "BLOCK":
                    raise BusinessError(
                        code="INBOUND_SHELF_LIFE_VIOLATION",
                        message=f"Hạn sử dụng còn lại ({rem_days} ngày) thấp hơn mức tối thiểu ({min_days} ngày)",  # noqa: E501
                        http_status=409,
                    )

        # Ghép dòng PO
        matched_po_line_id: uuid.UUID | None = None
        if grn.po_id is not None:
            po_lines = InboundRepository.get_po_lines(db, grn.po_id)
            if req.po_line_id is not None:
                target = next((pl for pl in po_lines if pl.po_line_id == req.po_line_id), None)
                if target is None or target.sku_id != req.sku_id:
                    raise BusinessError(
                        code="INBOUND_SKU_NOT_IN_PO",
                        message="Dòng PO không tồn tại hoặc không khớp SKU",
                        http_status=409,
                    )
                if target.uom_code != req.uom_code.strip():
                    raise BusinessError(
                        code="INBOUND_UOM_MISMATCH",
                        message="Đơn vị tính không khớp với dòng PO",
                        http_status=409,
                    )
                matched_po_line_id = target.po_line_id
            else:
                target = next(
                    (
                        pl
                        for pl in po_lines
                        if pl.sku_id == req.sku_id and pl.uom_code == req.uom_code.strip()
                    ),
                    None,
                )
                if target is not None:
                    matched_po_line_id = target.po_line_id

        line = GrnLine(
            grn_id=grn.grn_id,
            po_line_id=matched_po_line_id,
            sku_id=req.sku_id,
            lot_id=lot_id,
            uom_code=sku["base_uom"],
            qty_expected=Decimal("0.000"),
            qty_actual=base_actual,
            qty_damaged=base_damaged,
            serial_numbers=serials if serials else None,
            reason_code=req.reason_code,
            damage_photo_urls=req.damage_photo_urls if req.damage_photo_urls else None,
            notes=req.notes,
        )
        db.add(line)
        db.flush()

        db.add(
            GrnCountAttempt(
                grn_line_id=line.grn_line_id,
                attempt_no=1,
                counter_user_id=user.user_id,
                blind_counted_qty=base_actual,
            )
        )
        grn.version_no += 1
        db.flush()
        db.refresh(line)

        hide_blind = grn.is_blind_receipt and user.role_code == HIDE_QTY_ROLE
        res = _grn_line_dict(line, hide_blind)
        res["grn_version_no"] = grn.version_no
        return res

    # ------------------------------------------------------------------ B-05: Submit & Recount
    @staticmethod
    def _evaluate_and_route_grn(
        db: Session,
        grn: Grn,
        lines: list[GrnLine],
        actor_id: uuid.UUID,
        is_recount: bool = False,
    ) -> dict[str, Any]:
        cfg = get_warehouse_config(db, grn.warehouse_id)
        over_tol_pct = Decimal(str(cfg.get("over_receipt_tolerance_pct", "0")))
        po_lines_map: dict[uuid.UUID, POLine] = {}
        if grn.po_id is not None:
            for pl in InboundRepository.get_po_lines(db, grn.po_id):
                po_lines_map[pl.po_line_id] = pl

        # Gom nhóm theo po_line_id để kiểm tra nhận dư và tính lệch
        grouped_by_po_line: dict[uuid.UUID, list[GrnLine]] = {}
        unmatched_lines: list[GrnLine] = []
        for ln in lines:
            if ln.po_line_id and ln.po_line_id in po_lines_map:
                grouped_by_po_line.setdefault(ln.po_line_id, []).append(ln)
            else:
                unmatched_lines.append(ln)

        total_discrepancy_amount = Decimal("0.00")
        total_expected_amount = Decimal("0.00")
        force_review = grn.po_id is None  # Không có PO (chỉ ASN hoặc blind receipt) luôn buộc duyệt
        has_any_discrepancy = False

        # Kiểm tra các dòng khớp PO
        for po_line_id, grp in grouped_by_po_line.items():
            pl = po_lines_map[po_line_id]
            sku = get_sku(db, pl.sku_id)
            unit_cost = Decimal(str(sku.get("unit_cost", "0")))
            expected_base = convert_to_base_uom(
                db, pl.sku_id, pl.uom_code, max(Decimal("0"), pl.qty_ordered - pl.qty_received)
            )
            ordered_base = convert_to_base_uom(db, pl.sku_id, pl.uom_code, pl.qty_ordered)
            received_base = convert_to_base_uom(db, pl.sku_id, pl.uom_code, pl.qty_received)

            sum_actual = sum((x.qty_actual for x in grp), Decimal("0"))
            sum_damaged = sum((x.qty_damaged for x in grp), Decimal("0"))
            sum_good = sum_actual - sum_damaged

            # Kiểm tra nhận dư vượt dung sai PO
            max_allowed = ordered_base * (Decimal("1") + over_tol_pct / Decimal("100"))
            if received_base + sum_good > max_allowed:
                raise BusinessError(
                    code="INBOUND_OVER_RECEIPT",
                    message="Số lượng nhận đạt vượt quá dung sai cho phép của đơn mua hàng",
                    http_status=409,
                )

            var_qty = abs(sum_actual - expected_base) + sum_damaged
            var_amt = (var_qty * unit_cost).quantize(Decimal("0.01"))
            total_discrepancy_amount += var_amt
            total_expected_amount += (expected_base * unit_cost).quantize(Decimal("0.01"))

            line_has_issue = (sum_actual != expected_base) or (sum_damaged > 0)
            if sum_damaged > 0:
                force_review = True
            if line_has_issue:
                has_any_discrepancy = True

            # Gán qty_expected lên dòng đầu tiên của nhóm để lưu vết
            for idx, ln in enumerate(grp):
                ln.qty_expected = expected_base if idx == 0 else Decimal("0.000")
                ln.variance_amount = var_amt if idx == 0 else Decimal("0.00")
                ln.is_quarantined = line_has_issue

        # Kiểm tra các dòng ngoài PO
        for ln in unmatched_lines:
            sku = get_sku(db, ln.sku_id)
            unit_cost = Decimal(str(sku.get("unit_cost", "0")))
            var_amt = ((ln.qty_actual + ln.qty_damaged) * unit_cost).quantize(Decimal("0.01"))
            ln.qty_expected = Decimal("0.000")
            ln.variance_amount = var_amt
            ln.is_quarantined = True
            total_discrepancy_amount += var_amt
            has_any_discrepancy = True
            force_review = True

        # Kiểm tra thiếu dòng PO chưa được đếm
        for po_line_id, pl in po_lines_map.items():
            if po_line_id not in grouped_by_po_line:
                expected_base = convert_to_base_uom(
                    db, pl.sku_id, pl.uom_code, max(Decimal("0"), pl.qty_ordered - pl.qty_received)
                )
                if expected_base > 0:
                    sku = get_sku(db, pl.sku_id)
                    unit_cost = Decimal(str(sku.get("unit_cost", "0")))
                    var_amt = (expected_base * unit_cost).quantize(Decimal("0.01"))
                    total_discrepancy_amount += var_amt
                    total_expected_amount += var_amt
                    has_any_discrepancy = True

        # Kiểm tra cảnh báo hạn dùng (WARN)
        for ln in lines:
            if ln.lot_id is not None:
                sku = get_sku(db, ln.sku_id)
                if sku.get("category_id"):
                    min_days, action = InboundRepository.get_category_shelf_life(
                        db, sku["category_id"]
                    )
                    if min_days > 0 and action == "WARN":
                        # Đánh dấu buộc duyệt nếu có dòng cận date
                        exp = db.scalar(
                            __import__("sqlalchemy").text(
                                "SELECT expiry_date FROM lots WHERE lot_id = :lid;"
                            ),
                            {"lid": ln.lot_id},
                        )
                        if exp is not None and (exp - date.today()).days < min_days:
                            force_review = True
                            ln.is_quarantined = True

        grn.has_discrepancy = has_any_discrepancy or force_review
        grn.total_discrepancy_amount = total_discrepancy_amount

        disc_pct = Decimal("0.00")
        if total_expected_amount > 0:
            disc_pct = (
                (total_discrepancy_amount / total_expected_amount) * Decimal("100")
            ).quantize(Decimal("0.01"))
        elif total_discrepancy_amount > 0:
            disc_pct = Decimal("100.00")

        approval = None
        if grn.has_discrepancy:
            approval = create_approval_request(
                db=db,
                warehouse_id=grn.warehouse_id,
                object_type="GRN_DISCREPANCY",
                object_id=grn.grn_id,
                proposer_user_id=actor_id,
                discrepancy_amount=total_discrepancy_amount,
                discrepancy_percent=disc_pct,
                force_review=force_review,
            )

        dock_loc = None
        if grn.asn_id:
            asn_obj = InboundRepository.get_asn_by_id(db, grn.asn_id)
            dock_loc = asn_obj.assigned_dock_location_id if asn_obj else None
        if dock_loc is None:
            dock_loc = InboundRepository.get_first_dock_location(db, grn.warehouse_id)

        for ln in lines:
            if ln.qty_damaged <= 0 and ln.damaged_pallet_id is not None:
                ln.damaged_pallet_id = None
        db.flush()
        InboundRepository.cleanup_empty_damaged_pallets(db, grn.grn_id)

        if approval is None:
            # Tự động duyệt
            for ln in lines:
                ln.is_quarantined = False
            grn.status = "APPROVED"
            grn.version_no += 1
            db.flush()
            return {
                "grn_id": str(grn.grn_id),
                "status": grn.status,
                "outcome": "AUTO_APPROVED",
                "tier": None,
                "approval_id": None,
                "recount_count": grn.recount_count,
                "version_no": grn.version_no,
            }

        # Gán pallet QUARANTINE_HOLD / DAMAGED_HOLD khi chờ duyệt
        good_pallet_id: uuid.UUID | None = None
        dmg_pallet_id: uuid.UUID | None = None
        for ln in lines:
            good_qty = ln.qty_actual - ln.qty_damaged
            if good_qty > 0 and ln.pallet_id is None:
                if good_pallet_id is None:
                    good_pallet_id = InboundRepository.create_pallet(
                        db,
                        f"{grn.grn_number}-P01",
                        grn.warehouse_id,
                        dock_loc,
                        grn.grn_id,
                        "QUARANTINE_HOLD",
                        actor_id,
                    )
                ln.pallet_id = good_pallet_id
            if ln.qty_damaged > 0 and ln.damaged_pallet_id is None:
                if dmg_pallet_id is None:
                    dmg_code = f"{grn.grn_number}-DMG"
                    existing_dmg_id = InboundRepository.get_pallet_by_code(db, dmg_code)
                    if existing_dmg_id is not None:
                        dmg_pallet_id = InboundRepository.reactivate_pallet_for_grn(
                            db,
                            existing_dmg_id,
                            dock_loc,
                            grn.grn_id,
                            "DAMAGED_HOLD",
                        )
                    else:
                        dmg_pallet_id = InboundRepository.create_pallet(
                            db,
                            dmg_code,
                            grn.warehouse_id,
                            dock_loc,
                            grn.grn_id,
                            "DAMAGED_HOLD",
                            actor_id,
                        )
                ln.damaged_pallet_id = dmg_pallet_id

        db.flush()
        db.refresh(grn)
        return {
            "grn_id": str(grn.grn_id),
            "status": grn.status,
            "outcome": "PENDING_APPROVAL",
            "tier": str(approval.current_tier),
            "approval_id": str(approval.approval_id),
            "recount_count": grn.recount_count,
            "version_no": grn.version_no,
        }

    @staticmethod
    def submit_grn(
        db: Session,
        user: UserContext,
        access_type: str,
        grn_id: uuid.UUID,
        req: SubmitGrnRequest,
    ) -> dict[str, Any]:
        _require_write_access(access_type)
        _require_warehouse(user)
        grn = InboundRepository.get_grn_by_id(db, grn_id, for_update=True)
        if grn is None:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy GRN", http_status=404)
        enforce_warehouse_scope(user, grn.warehouse_id)
        can_recount_view = grn.status.startswith("PENDING_D") or grn.recount_count > 0
        if (
            user.role_code == HIDE_QTY_ROLE
            and grn.received_by != user.user_id
            and not can_recount_view
        ):
            raise BusinessError(
                code="FORBIDDEN",
                message="Bạn chỉ được nộp phiếu GRN của chính mình",
                http_status=403,
            )
        if grn.status != "COUNTING":
            raise BusinessError(
                code="INVALID_STATE",
                message=f"GRN đang ở trạng thái {grn.status}, không thể nộp",
                http_status=409,
            )
        if grn.version_no != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Phiên bản phiếu GRN đã thay đổi",
                http_status=409,
                details={"current_version_no": grn.version_no},
            )

        lines = InboundRepository.get_grn_lines(db, grn_id)
        if not lines:
            raise BusinessError(
                code="INBOUND_GRN_EMPTY",
                message="Phiếu GRN chưa có dòng kiểm đếm nào",
                http_status=409,
            )

        try:
            result = InboundService._evaluate_and_route_grn(db, grn, lines, user.user_id)
        except (IntegrityError, DBAPIError) as exc:
            raise translate_db_error(exc) from exc

        create_audit_log(
            db,
            action_code="SUBMIT_DOC",
            entity_name="grns",
            actor_user_id=user.user_id,
            warehouse_id=grn.warehouse_id,
            entity_id=grn.grn_id,
            new_values={"status": result["status"], "outcome": result["outcome"]},
        )
        return result

    @staticmethod
    def recount_grn(
        db: Session,
        user: UserContext,
        access_type: str,
        grn_id: uuid.UUID,
        req: RecountGrnRequest,
    ) -> dict[str, Any]:
        _require_write_access(access_type)
        warehouse_id = _require_warehouse(user)
        grn = InboundRepository.get_grn_by_id(db, grn_id, for_update=True)
        if grn is None:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy GRN", http_status=404)
        enforce_warehouse_scope(user, grn.warehouse_id)

        if grn.version_no != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Phiên bản phiếu GRN đã thay đổi",
                http_status=409,
                details={"current_version_no": grn.version_no},
            )

        if grn_id not in InboundRepository.list_recountable_grn_ids(db, [grn_id]):
            raise BusinessError(
                code="INVALID_STATE",
                message="GRN chỉ được đếm lại khi người duyệt yêu cầu đếm lại (NEED_INFO)",
                http_status=409,
            )

        cfg = get_warehouse_config(db, warehouse_id)
        max_recount = int(cfg.get("max_recount_attempts") or 2)
        if grn.recount_count >= max_recount:
            raise BusinessError(
                code="INBOUND_RECOUNT_LIMIT",
                message=f"Đã đạt giới hạn số lần đếm lại tối đa ({max_recount})",
                http_status=409,
            )

        lines = InboundRepository.get_grn_lines(db, grn_id)
        line_map = {ln.grn_line_id: ln for ln in lines}
        allow_same = bool(cfg.get("allow_same_counter_recount", False))

        # Kiểm tra người đếm gần nhất
        for ln in lines:
            last_att = InboundRepository.get_latest_attempt(db, ln.grn_line_id)
            if last_att and not allow_same and last_att.counter_user_id == user.user_id:
                raise BusinessError(
                    code="INBOUND_RECOUNT_SAME_COUNTER",
                    message="Cấu hình kho yêu cầu người đếm lại phải khác người đếm gần nhất",
                    http_status=409,
                )

        next_attempt = grn.recount_count + 2
        for item in req.lines:
            target_ln = line_map.get(item.grn_line_id)
            if target_ln is None:
                raise BusinessError(
                    code="NOT_FOUND",
                    message=f"Không tìm thấy dòng GRN {item.grn_line_id}",
                    http_status=404,
                )
            if item.qty_actual < 0 or item.qty_damaged < 0 or item.qty_damaged > item.qty_actual:
                raise _validation_error("Số lượng đếm lại không hợp lệ")
            target_ln.qty_actual = item.qty_actual
            target_ln.qty_damaged = item.qty_damaged
            db.add(
                GrnCountAttempt(
                    grn_line_id=target_ln.grn_line_id,
                    attempt_no=next_attempt,
                    counter_user_id=user.user_id,
                    blind_counted_qty=item.qty_actual,
                )
            )

        open_app = InboundRepository.get_open_approval_for_grn(db, grn_id)
        if open_app is None:
            raise BusinessError(
                code="APPROVAL_NOT_FOUND",
                message="Không tìm thấy hồ sơ phê duyệt đang mở cho phiếu nhập kho",
                http_status=409,
            )
        grn.recount_count += 1
        supersede_approval_for_recount(
            db=db,
            approval_id=open_app[0],
            warehouse_id=warehouse_id,
            actor_user_id=user.user_id,
            note=f"Thay thế hồ sơ duyệt sau lần đếm lại thứ {grn.recount_count}",
        )

        result = InboundService._evaluate_and_route_grn(
            db, grn, lines, user.user_id, is_recount=True
        )
        create_audit_log(
            db,
            action_code="RECOUNT_DOC",
            entity_name="grns",
            actor_user_id=user.user_id,
            warehouse_id=warehouse_id,
            entity_id=grn.grn_id,
            new_values={"recount_count": grn.recount_count, "status": result["status"]},
        )
        return result

    # ------------------------------------------------------------------ B-06: Complete GRN
    @staticmethod
    def complete_grn(
        db: Session,
        user: UserContext,
        access_type: str,
        grn_id: uuid.UUID,
        req: CompleteGrnRequest,
    ) -> dict[str, Any]:
        _require_write_access(access_type)
        warehouse_id = _require_warehouse(user)
        grn = InboundRepository.get_grn_by_id(db, grn_id, for_update=True)
        if grn is None:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy GRN", http_status=404)
        enforce_warehouse_scope(user, grn.warehouse_id)

        if grn.version_no != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Phiên bản phiếu GRN đã thay đổi",
                http_status=409,
                details={"current_version_no": grn.version_no},
            )
        if grn.status != "APPROVED":
            raise BusinessError(
                code="INBOUND_GRN_NOT_APPROVED",
                message=f"GRN đang ở trạng thái {grn.status}, chỉ phiếu APPROVED mới được hoàn tất",
                http_status=409,
            )

        dock_loc: uuid.UUID | None = None
        asn_obj: Asn | None = None
        if grn.asn_id:
            asn_obj = InboundRepository.get_asn_by_id(db, grn.asn_id, for_update=True)
            if asn_obj:
                dock_loc = asn_obj.assigned_dock_location_id
        if dock_loc is None:
            dock_loc = InboundRepository.get_first_dock_location(db, warehouse_id)
        if dock_loc is None:
            raise BusinessError(
                code="INBOUND_NO_DOCK_LOCATION",
                message="Kho chưa cấu hình vị trí cửa nhận hàng (RECEIVING_DOCK)",
                http_status=409,
            )

        lines = InboundRepository.get_grn_lines(db, grn_id)
        good_pallet_id: uuid.UUID | None = None
        dmg_pallet_id: uuid.UUID | None = None
        good_pallet_ids: set[uuid.UUID] = set()

        for ln in lines:
            good_qty = ln.qty_actual - ln.qty_damaged
            if good_qty > 0:
                if ln.pallet_id is None:
                    if good_pallet_id is None:
                        good_pallet_id = InboundRepository.create_pallet(
                            db,
                            f"{grn.grn_number}-P01",
                            warehouse_id,
                            dock_loc,
                            grn.grn_id,
                            "STAGED",
                            user.user_id,
                        )
                    ln.pallet_id = good_pallet_id
                good_pallet_ids.add(ln.pallet_id)

                if ln.serial_numbers:
                    for sn in ln.serial_numbers:
                        apply_movement(
                            db=db,
                            warehouse_id=warehouse_id,
                            location_id=dock_loc,
                            sku_id=ln.sku_id,
                            lot_id=ln.lot_id,
                            pallet_id=ln.pallet_id,
                            serial_number=sn,
                            tx_type="RECEIVE",
                            delta_available=Decimal("1.000"),
                            ref_doc_type="GRN",
                            ref_doc_id=grn.grn_id,
                            performed_by=user.user_id,
                        )
                else:
                    apply_movement(
                        db=db,
                        warehouse_id=warehouse_id,
                        location_id=dock_loc,
                        sku_id=ln.sku_id,
                        lot_id=ln.lot_id,
                        pallet_id=ln.pallet_id,
                        serial_number=None,
                        tx_type="RECEIVE",
                        delta_available=good_qty,
                        ref_doc_type="GRN",
                        ref_doc_id=grn.grn_id,
                        performed_by=user.user_id,
                    )

            if ln.qty_damaged > 0:
                if ln.damaged_pallet_id is None:
                    if dmg_pallet_id is None:
                        dmg_code = f"{grn.grn_number}-DMG"
                        existing_dmg_id = InboundRepository.get_pallet_by_code(db, dmg_code)
                        if existing_dmg_id is not None:
                            dmg_pallet_id = InboundRepository.reactivate_pallet_for_grn(
                                db,
                                existing_dmg_id,
                                dock_loc,
                                grn.grn_id,
                                "DAMAGED_HOLD",
                            )
                        else:
                            dmg_pallet_id = InboundRepository.create_pallet(
                                db,
                                dmg_code,
                                warehouse_id,
                                dock_loc,
                                grn.grn_id,
                                "DAMAGED_HOLD",
                                user.user_id,
                            )
                    ln.damaged_pallet_id = dmg_pallet_id
                apply_movement(
                    db=db,
                    warehouse_id=warehouse_id,
                    location_id=dock_loc,
                    sku_id=ln.sku_id,
                    lot_id=ln.lot_id,
                    pallet_id=ln.damaged_pallet_id,
                    serial_number=None,
                    tx_type="RECEIVE",
                    delta_damaged=ln.qty_damaged,
                    ref_doc_type="GRN",
                    ref_doc_id=grn.grn_id,
                    performed_by=user.user_id,
                )

        pallets_out: list[dict[str, Any]] = []
        for pid in sorted(good_pallet_ids, key=str):
            new_ver = InboundRepository.update_pallet_status(db, pid, "STAGED", dock_loc)
            p_row = InboundRepository.get_pallet_row(db, pid)
            if p_row:
                pallets_out.append(
                    {
                        "pallet_id": str(pid),
                        "pallet_code": p_row["pallet_code"],
                        "label_barcode": p_row["pallet_code"],
                        "status": "STAGED",
                        "current_location_id": str(dock_loc),
                        "version_no": new_ver,
                    }
                )
            create_task(
                db=db,
                warehouse_id=warehouse_id,
                creator_id=user.user_id,
                req=_task_req(  # type: ignore[arg-type]
                    zone_id=None,
                    assigned_to=None,
                    note=None,
                    task_type="PUTAWAY",
                    stage="CAT_HANG",
                    ref_doc_type="PALLET",
                    ref_doc_id=pid,
                    priority="NORMAL",
                ),
            )

        grn.status = "CLOSED"
        grn.closed_at = datetime.now(timezone.utc)
        grn.version_no += 1
        if asn_obj is not None and asn_obj.status != "COMPLETED":
            asn_obj.status = "COMPLETED"

        mark_object_approval_executed(
            db=db,
            warehouse_id=warehouse_id,
            object_type="GRN_DISCREPANCY",
            object_id=grn.grn_id,
            actor_user_id=user.user_id,
            note="Hoàn tất nhập kho GRN sau phê duyệt chênh lệch",
        )

        enqueue_to_erp(
            db=db,
            warehouse_id=warehouse_id,
            doc_type="GRN",
            doc_id=grn.grn_id,
            payload={
                "grn_id": str(grn.grn_id),
                "grn_number": grn.grn_number,
                "po_id": str(grn.po_id) if grn.po_id else None,
                "closed_at": grn.closed_at.isoformat(),
            },
        )
        db.flush()

        create_audit_log(
            db,
            action_code="COMPLETE_DOC",
            entity_name="grns",
            actor_user_id=user.user_id,
            warehouse_id=warehouse_id,
            entity_id=grn.grn_id,
            new_values={"status": "CLOSED", "pallets": [p["pallet_code"] for p in pallets_out]},
        )
        return {
            "grn_id": str(grn.grn_id),
            "status": grn.status,
            "version_no": grn.version_no,
            "pallets": pallets_out,
        }

    # ------------------------------------------------------------------ B-07: Putaway
    @staticmethod
    def suggest_putaway(
        db: Session, user: UserContext, req: PutawaySuggestRequest
    ) -> dict[str, Any]:
        warehouse_id = _require_warehouse(user)
        pallet = InboundRepository.get_pallet_row(db, req.pallet_id)
        if pallet is None:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy pallet", http_status=404)
        enforce_warehouse_scope(user, pallet["warehouse_id"])

        balances = InboundRepository.get_pallet_balances(db, req.pallet_id)
        if not balances:
            raise BusinessError(
                code="INBOUND_PALLET_EMPTY",
                message="Pallet không có hàng hóa khả dụng để cất",
                http_status=409,
            )

        reqs = {b["storage_requirement"] for b in balances}
        if "HAZMAT" in reqs:
            target_zone_type = "HAZMAT"
        elif "COLD" in reqs:
            target_zone_type = "COLD"
        else:
            target_zone_type = "STORAGE"

        sku_ids = list({b["sku_id"] for b in balances})
        suggestions = InboundRepository.suggest_locations_for_pallet(
            db, warehouse_id, pallet["current_location_id"], target_zone_type, sku_ids
        )
        return {
            "pallet_id": str(req.pallet_id),
            "target_zone_type": target_zone_type,
            "suggestions": suggestions,
        }

    @staticmethod
    def confirm_putaway(
        db: Session,
        user: UserContext,
        pallet_id: uuid.UUID,
        req: PutawayConfirmRequest,
    ) -> dict[str, Any]:
        warehouse_id = _require_warehouse(user)
        pallet = InboundRepository.get_pallet_row(db, pallet_id)
        if pallet is None:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy pallet", http_status=404)
        enforce_warehouse_scope(user, pallet["warehouse_id"])

        if pallet["version_no"] != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Phiên bản pallet đã thay đổi",
                http_status=409,
                details={"current_version_no": pallet["version_no"]},
            )
        if pallet["status"] not in ("STAGED", "PUTAWAY_IN_PROGRESS"):
            raise BusinessError(
                code="INBOUND_PALLET_NOT_PUTAWAYABLE",
                message=f"Pallet đang ở trạng thái {pallet['status']}, không thể thực hiện cất hàng",  # noqa: E501
                http_status=409,
            )
        if req.scanned_pallet_code and req.scanned_pallet_code.strip() != pallet["pallet_code"]:
            raise BusinessError(
                code="INBOUND_WRONG_PALLET",
                message="Mã vạch pallet quét được không khớp",
                http_status=409,
            )

        target_loc = get_location(db, req.location_id, warehouse_id)
        if (
            req.scanned_location_barcode
            and req.scanned_location_barcode.strip() != target_loc["barcode"]
        ):
            raise BusinessError(
                code="INBOUND_WRONG_LOCATION",
                message="Mã vạch vị trí đích không khớp",
                http_status=409,
            )
        if pallet["current_location_id"] == req.location_id:
            raise BusinessError(
                code="INBOUND_WRONG_LOCATION",
                message="Vị trí đích trùng với vị trí hiện tại của pallet",
                http_status=409,
            )
        if target_loc["status"] in ("MAINTENANCE_LOCKED", "COUNTING_LOCKED"):
            raise BusinessError(
                code="INBOUND_LOCATION_LOCKED",
                message="Vị trí đích đang bị khóa",
                http_status=409,
            )
        if target_loc["status"] == "FULL" or not target_loc.get("is_active", True):
            raise BusinessError(
                code="INBOUND_LOCATION_FULL",
                message="Vị trí đích đã đầy hoặc ngừng hoạt động",
                http_status=409,
            )

        balances = InboundRepository.get_pallet_balances(db, pallet_id)
        if not balances:
            raise BusinessError(
                code="INBOUND_PALLET_EMPTY",
                message="Pallet không còn hàng để cất",
                http_status=409,
            )

        reqs = {b["storage_requirement"] for b in balances}
        expected_zone = "HAZMAT" if "HAZMAT" in reqs else ("COLD" if "COLD" in reqs else "STORAGE")
        actual_zone = InboundRepository.get_zone_type(db, target_loc["zone_id"])
        if actual_zone != expected_zone:
            raise BusinessError(
                code="INBOUND_LOCATION_ZONE_MISMATCH",
                message=f"Khu vực đích ({actual_zone}) không phù hợp điều kiện bảo quản ({expected_zone})",  # noqa: E501
                http_status=409,
            )

        from_loc = pallet["current_location_id"]
        if req.lines:
            for item in req.lines:
                matched = next(
                    (
                        b
                        for b in balances
                        if b["sku_id"] == item.sku_id
                        and b["lot_id"] == item.lot_id
                        and b["serial_number"] == item.serial_number
                    ),
                    None,
                )
                if matched is None or item.qty <= 0 or item.qty > matched["qty_available"]:
                    raise BusinessError(
                        code="INBOUND_PUTAWAY_QTY_EXCEEDS",
                        message="Số lượng cất vượt quá tồn khả dụng trên pallet",
                        http_status=409,
                    )
                transfer_inventory(
                    db=db,
                    warehouse_id=warehouse_id,
                    from_location_id=from_loc,
                    to_location_id=req.location_id,
                    sku_id=item.sku_id,
                    lot_id=item.lot_id,
                    pallet_id=pallet_id,
                    serial_number=item.serial_number,
                    qty=item.qty,
                    tx_type="PUTAWAY",
                    ref_doc_type="PALLET",
                    ref_doc_id=pallet_id,
                    performed_by=user.user_id,
                    bucket="AVAILABLE",
                )
        else:
            for b in balances:
                transfer_inventory(
                    db=db,
                    warehouse_id=warehouse_id,
                    from_location_id=from_loc,
                    to_location_id=req.location_id,
                    sku_id=b["sku_id"],
                    lot_id=b["lot_id"],
                    pallet_id=pallet_id,
                    serial_number=b["serial_number"],
                    qty=b["qty_available"],
                    tx_type="PUTAWAY",
                    ref_doc_type="PALLET",
                    ref_doc_id=pallet_id,
                    performed_by=user.user_id,
                    bucket="AVAILABLE",
                )

        total_moved_qty = (
            sum((item.qty for item in req.lines), Decimal("0"))
            if req.lines
            else sum((b["qty_available"] for b in balances), Decimal("0"))
        )
        remaining_at_source = InboundRepository.get_pallet_balances_at_location(
            db, pallet_id, from_loc
        )
        if not remaining_at_source:
            new_status = "STORED"
            new_loc = req.location_id
            putaway_task = InboundRepository.get_open_putaway_task(db, pallet_id)
            if putaway_task is not None:
                tid = putaway_task["task_id"]
                tver = putaway_task["version_no"]
                tstatus = putaway_task["status"]
                if tstatus == "UNASSIGNED":
                    assigned = assign_task(
                        db=db,
                        task_id=tid,
                        assigner_id=user.user_id,
                        req=_task_req(assigned_to_user_id=user.user_id, version_no=tver),
                        warehouse_id=warehouse_id,
                    )
                    tver = assigned.version_no
                    tstatus = assigned.status
                if tstatus == "ASSIGNED" and str(
                    putaway_task["assigned_to"] or user.user_id
                ) == str(user.user_id):
                    accepted = accept_task(
                        db=db,
                        task_id=tid,
                        worker_id=user.user_id,
                        req=_task_req(version_no=tver),
                        warehouse_id=warehouse_id,
                    )
                    tver = accepted.version_no
                    tstatus = accepted.status
                if tstatus == "IN_PROGRESS":
                    complete_task(
                        db=db,
                        task_id=tid,
                        worker_id=user.user_id,
                        req=_task_req(version_no=tver, completed_qty=total_moved_qty),
                        warehouse_id=warehouse_id,
                    )
        else:
            new_status = "PUTAWAY_IN_PROGRESS"
            new_loc = from_loc

        new_ver = InboundRepository.update_pallet_status(db, pallet_id, new_status, new_loc)
        db.flush()

        create_audit_log(
            db,
            action_code="INVENTORY_MOVEMENT",
            entity_name="pallets",
            actor_user_id=user.user_id,
            warehouse_id=warehouse_id,
            entity_id=pallet_id,
            new_values={"status": new_status, "location_id": str(new_loc)},
        )
        return {
            "pallet_id": str(pallet_id),
            "pallet_code": pallet["pallet_code"],
            "status": new_status,
            "current_location_id": str(new_loc),
            "version_no": new_ver,
        }

    @staticmethod
    def get_grn(db: Session, grn_id: uuid.UUID) -> Grn:
        grn = InboundRepository.get_grn_by_id(db, grn_id)
        if not grn:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy GRN", http_status=404)
        return grn
