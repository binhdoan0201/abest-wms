"""ABEST WMS - Services điều phối nghiệp vụ Phân hệ Xuất kho (Outbound).

Quy tắc kiến trúc:
- Chỉ gọi nghiệp vụ biến động tồn kho của module `inventory` thông qua `__init__`
  (`apply_movement`, `transfer_inventory`).
- Mọi thao tác trong một request nằm chung một database transaction.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from server.app.core.audit import create_audit_log
from server.app.core.exceptions import BusinessError, translate_db_error
from server.app.core.rbac import UserContext, enforce_warehouse_scope
from server.app.modules.integrations import enqueue_to_erp, get_waybill, request_waybill
from server.app.modules.inventory import apply_movement, transfer_inventory
from server.app.modules.outbound.repositories import (
    OutboundRepository,
    _fmt_dt,
    _fmt_num,
)
from server.app.modules.outbound.schemas import (
    AllocateOrderRequest,
    ConfirmGoodsIssueRequest,
    ConfirmPickLineRequest,
    CreateGoodsIssueRequest,
    CreatePackageRequest,
    CreatePickSessionRequest,
    DecideOrderChangeRequest,
    PickLineExceptionRequest,
)
from server.app.modules.tasks import (
    accept_task,
    assign_task,
    complete_task,
    create_task,
)


def _task_req(**kwargs: Any) -> Any:
    return SimpleNamespace(**kwargs)


def _translate_outbound_db_error(exc: Exception) -> BusinessError:
    """Dịch lỗi DB chuyên biệt của Outbound trước khi chuyển về translate_db_error chung."""
    if isinstance(exc, BusinessError):
        return exc
    err = str(exc)
    if "YEU_CAU_KHONG_O_TRANG_THAI_CHO" in err:
        return BusinessError(
            code="INVALID_STATE",
            message="Yêu cầu đổi/hủy đơn không ở trạng thái chờ Quản lý duyệt",
            http_status=409,
        )
    if "THIEU_LY_DO" in err:
        return BusinessError(
            code="OUTBOUND_REJECT_NOTE_REQUIRED",
            message="Từ chối yêu cầu đổi/hủy của ERP bắt buộc ghi lý do",
            http_status=422,
        )
    if "DON_DA_LEN_XE" in err:
        return BusinessError(
            code="OUTBOUND_ALREADY_LOADED",
            message="Không thể chấp nhận hủy đơn vì hàng đã quét lên xe",
            http_status=409,
        )
    if "QUYET_DINH_KHONG_HOP_LE" in err:
        return BusinessError(
            code="VALIDATION_ERROR",
            message="Quyết định chỉ chấp nhận ACCEPT hoặc REJECT",
            http_status=422,
        )
    if "KHONG_DU_QUYEN" in err:
        return BusinessError(
            code="FORBIDDEN",
            message="Chỉ Quản lý kho hoặc Ban giám đốc được chốt yêu cầu đổi/hủy từ ERP",
            http_status=403,
        )
    if "GI_SAI_LOAI" in err:
        return BusinessError(
            code="OUTBOUND_GI_TYPE_MISMATCH",
            message="Loại phiếu xuất kho GI không khớp với loại đơn xuất",
            http_status=409,
        )
    return translate_db_error(exc)


def _require_access(access_type: str | None, allowed: tuple[str, ...]) -> None:
    if access_type is not None and access_type not in allowed:
        raise BusinessError(
            code="FORBIDDEN",
            message=f"Mức quyền '{access_type}' không được phép thao tác",
            http_status=403,
        )


def _to_vn_date(raw_val: date | datetime | str) -> date:
    vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
    if isinstance(raw_val, datetime):
        dt = raw_val if raw_val.tzinfo is not None else raw_val.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(vn_tz).date()
    if isinstance(raw_val, date):
        return raw_val
    return datetime.fromisoformat(str(raw_val)).astimezone(vn_tz).date()


class OutboundService:
    """Service điều phối quy trình xuất kho, cấp phát, soạn hàng, đóng gói và phát hành GI."""

    @staticmethod
    def list_orders(
        db: Session,
        user_ctx: UserContext,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
        access_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        allowed_dg1 = ("PICKED", "PACKING", "READY_TO_SHIP", "WAITING_WAYBILL")
        dg1_only = "DG-1" in user_ctx.permissions and "QL-2.1" not in user_ctx.permissions
        if dg1_only:
            if status and status not in allowed_dg1:
                return [], 0
            if not status:
                items, _ = OutboundRepository.list_orders(
                    db=db,
                    warehouse_id=user_ctx.warehouse_id,
                    status=None,
                    page=1,
                    page_size=100,
                )
                filtered = [row for row in items if str(row.get("status") or "") in allowed_dg1]
                start = (page - 1) * page_size
                return filtered[start : start + page_size], len(filtered)
        return OutboundRepository.list_orders(
            db=db,
            warehouse_id=user_ctx.warehouse_id,
            status=status,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def get_order_detail(
        db: Session,
        user_ctx: UserContext,
        order_id: uuid.UUID,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        order = OutboundRepository.get_order_raw(db, order_id, for_update=True)
        if not order:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy đơn xuất kho",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, order["warehouse_id"])

        lines_raw = OutboundRepository.get_order_lines(db, order_id)
        allocs_raw = OutboundRepository.get_order_allocations(db, order_id)
        packages_raw = OutboundRepository.get_order_packages(db, order_id)

        lines = [
            {
                "order_line_id": str(line["order_line_id"]),
                "sku_id": str(line["sku_id"]),
                "sku_code": line["sku_code"],
                "sku_name": line["sku_name"],
                "base_uom": line["base_uom"],
                "qty_ordered": _fmt_num(line["qty_ordered"]),
                "qty_allocated": _fmt_num(line["qty_allocated"]),
                "qty_picked": _fmt_num(line["qty_picked"]),
                "qty_packed": _fmt_num(line["qty_packed"]),
                "qty_shipped": _fmt_num(line["qty_shipped"]),
                "shortage_resolution": line["shortage_resolution"],
            }
            for line in lines_raw
        ]

        allocations = [
            {
                "allocation_id": str(a["allocation_id"]),
                "order_line_id": str(a["order_line_id"]),
                "balance_id": str(a["balance_id"]),
                "location_id": str(a["location_id"]),
                "sku_id": str(a["sku_id"]),
                "lot_id": str(a["lot_id"]) if a["lot_id"] else None,
                "qty_allocated": _fmt_num(a["qty_allocated"]),
                "qty_picked": _fmt_num(a["qty_picked"]),
                "status": a["status"],
                "version_no": int(a["version_no"]),
            }
            for a in allocs_raw
        ]

        packages = [
            {
                "package_id": str(p["package_id"]),
                "package_barcode": p["package_barcode"],
                "gi_id": str(p["gi_id"]) if p["gi_id"] else None,
                "box_type_id": str(p["box_type_id"]) if p["box_type_id"] else None,
                "weight_kg": _fmt_num(p["weight_kg"]),
                "is_loaded_on_truck": bool(p["is_loaded_on_truck"]),
                "packed_at": _fmt_dt(p["packed_at"]),
            }
            for p in packages_raw
        ]

        return {
            "order_id": str(order["order_id"]),
            "erp_order_number": order["erp_order_number"],
            "order_type": order["order_type"],
            "warehouse_id": str(order["warehouse_id"]),
            "customer_id": str(order["customer_id"]) if order["customer_id"] else None,
            "customer_name": order["customer_name"],
            "supplier_id": str(order["supplier_id"]) if order["supplier_id"] else None,
            "dest_warehouse_id": (
                str(order["dest_warehouse_id"]) if order["dest_warehouse_id"] else None
            ),
            "status": order["status"],
            "is_urgent": bool(order["is_urgent"]),
            "urgent_reason": order["urgent_reason"],
            "cutoff_time": _fmt_dt(order["cutoff_time"]),
            "route_code": order["route_code"],
            "delay_reason": order["delay_reason"],
            "erp_change_pending": bool(order["erp_change_pending"]),
            "version_no": int(order["version_no"]),
            "created_at": _fmt_dt(order["created_at"]),
            "updated_at": _fmt_dt(order["updated_at"]),
            "lines": lines,
            "allocations": allocations,
            "packages": packages,
        }

    @staticmethod
    def allocate_order(
        db: Session,
        user_ctx: UserContext,
        order_id: uuid.UUID,
        req: AllocateOrderRequest,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        _require_access(access_type, ("G",))
        order = OutboundRepository.get_order_raw(db, order_id, for_update=True)
        if not order:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy đơn xuất kho",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, order["warehouse_id"])

        if order["erp_change_pending"]:
            raise BusinessError(
                code="ORDER_FROZEN",
                message=(
                    "Đơn hàng đang bị đóng băng do có yêu cầu đổi/hủy từ ERP "
                    "đang chờ Quản lý chốt"
                ),
                http_status=409,
            )

        if req.version_no is not None and int(order["version_no"]) != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Đơn xuất kho đã được người khác cập nhật",
                http_status=409,
                details={"current_version_no": int(order["version_no"])},
            )

        if order["status"] not in ("NEW", "ON_HOLD"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Không thể cấp phát tồn kho cho đơn đang ở trạng thái {order['status']}",
                http_status=409,
            )

        lines = OutboundRepository.get_order_lines(db, order_id)
        if not lines:
            raise BusinessError(
                code="INVALID_STATE",
                message="Đơn xuất kho không có dòng hàng để cấp phát",
                http_status=409,
            )

        warehouse_id = uuid.UUID(str(order["warehouse_id"]))
        default_rule = OutboundRepository.get_warehouse_picking_rule(db, warehouse_id)
        created_allocs: list[dict[str, Any]] = []
        has_shortage = False

        try:
            for line in lines:
                line_id = uuid.UUID(str(line["order_line_id"]))
                sku_id = uuid.UUID(str(line["sku_id"]))
                qty_ordered = Decimal(str(line["qty_ordered"]))
                already_alloc = Decimal(str(line["qty_allocated"]))
                remaining = qty_ordered - already_alloc
                if remaining <= Decimal("0"):
                    continue

                strategy = (
                    req.strategy.upper()
                    if req.strategy
                    else ("FEFO" if line["is_expiry_tracked"] else default_rule)
                )
                cutoff_raw = order.get("cutoff_time")
                min_expiry = (
                    _to_vn_date(cutoff_raw)
                    if hasattr(cutoff_raw, "date") and cutoff_raw is not None
                    else None
                )
                balances = OutboundRepository.find_allocatable_balances(
                    db=db,
                    warehouse_id=warehouse_id,
                    sku_id=sku_id,
                    strategy=strategy,
                    min_expiry_date=min_expiry,
                )

                allocated_for_line = already_alloc
                for bal in balances:
                    if remaining <= Decimal("0"):
                        break
                    avail = Decimal(str(bal["qty_available"]))
                    if avail <= Decimal("0"):
                        continue

                    take = min(remaining, avail)
                    balance_id = uuid.UUID(str(bal["balance_id"]))
                    location_id = uuid.UUID(str(bal["location_id"]))
                    lot_id = uuid.UUID(str(bal["lot_id"])) if bal["lot_id"] else None
                    pallet_id = uuid.UUID(str(bal["pallet_id"])) if bal["pallet_id"] else None

                    # Chuyển tồn từ AVAILABLE -> ALLOCATED qua module inventory
                    apply_movement(
                        db=db,
                        warehouse_id=warehouse_id,
                        location_id=location_id,
                        sku_id=sku_id,
                        lot_id=lot_id,
                        pallet_id=pallet_id,
                        serial_number=bal["serial_number"],
                        tx_type="ALLOCATE",
                        delta_available=-take,
                        delta_allocated=take,
                        ref_doc_type="SO",
                        ref_doc_id=order_id,
                        performed_by=user_ctx.user_id,
                    )

                    alloc_id = OutboundRepository.upsert_inventory_allocation(
                        db=db,
                        order_line_id=line_id,
                        balance_id=balance_id,
                        lot_id=lot_id,
                        qty_allocated=take,
                    )

                    allocated_for_line += take
                    remaining -= take
                    created_allocs.append(
                        {
                            "allocation_id": str(alloc_id),
                            "order_line_id": str(line_id),
                            "balance_id": str(balance_id),
                            "location_id": str(location_id),
                            "lot_id": str(lot_id) if lot_id else None,
                            "qty_allocated": _fmt_num(take),
                        }
                    )

                if allocated_for_line < qty_ordered:
                    has_shortage = True
                    OutboundRepository.update_order_line_allocated(
                        db=db,
                        order_line_id=line_id,
                        qty_allocated=allocated_for_line,
                        shortage_resolution="WAIT_STOCK",
                    )
                else:
                    OutboundRepository.update_order_line_allocated(
                        db=db,
                        order_line_id=line_id,
                        qty_allocated=allocated_for_line,
                    )

            if not created_allocs and has_shortage:
                raise BusinessError(
                    code="OUTBOUND_INSUFFICIENT_ALLOCATABLE_STOCK",
                    message="Không đủ tồn kho khả dụng trong khu lưu trữ để cấp phát cho đơn",
                    http_status=409,
                )

            new_version = OutboundRepository.bump_order_version(
                db=db,
                order_id=order_id,
                new_status="ON_HOLD" if has_shortage else None,
                delay_reason="SHORTAGE" if has_shortage else None,
            )

            create_audit_log(
                db=db,
                action_code="ALLOCATE_ORDER",
                entity_name="outbound_orders",
                actor_user_id=user_ctx.user_id,
                warehouse_id=warehouse_id,
                entity_id=order_id,
                new_values={
                    "allocations_count": len(created_allocs),
                    "has_shortage": has_shortage,
                },
            )
        except Exception as exc:
            raise _translate_outbound_db_error(exc) from exc

        return {
            "order_id": str(order_id),
            "status": "ON_HOLD" if has_shortage else order["status"],
            "has_shortage": has_shortage,
            "version_no": new_version,
            "allocations": created_allocs,
        }

    @staticmethod
    def create_pick_session(
        db: Session,
        user_ctx: UserContext,
        req: CreatePickSessionRequest,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        _require_access(access_type, ("G",))
        if user_ctx.role_code != "thukho":
            raise BusinessError(
                code="FORBIDDEN",
                message="Chỉ Thủ kho (thukho) được phép khởi tạo phiên soạn hàng",
                http_status=403,
            )

        if not user_ctx.warehouse_id:
            raise BusinessError(
                code="FORBIDDEN",
                message="Tài khoản chưa được gán kho làm việc",
                http_status=403,
            )

        picker_id = req.picker_user_id or user_ctx.user_id
        if req.picker_user_id and not OutboundRepository.validate_picker_user(
            db, req.picker_user_id, user_ctx.warehouse_id
        ):
            raise BusinessError(
                code="OUTBOUND_INVALID_PICKER",
                message="Nhân viên soạn hàng không hợp lệ hoặc không thuộc vai trò nv-soan",
                http_status=422,
            )
        orders_to_pick: list[dict[str, Any]] = []

        for oid in req.order_ids:
            order = OutboundRepository.get_order_raw(db, oid, for_update=True)
            if not order:
                raise BusinessError(
                    code="NOT_FOUND",
                    message=f"Không tìm thấy đơn xuất kho {oid}",
                    http_status=404,
                )
            enforce_warehouse_scope(user_ctx, order["warehouse_id"])
            if order["erp_change_pending"]:
                raise BusinessError(
                    code="ORDER_FROZEN",
                    message=(
                        f"Đơn {order['erp_order_number']} đang bị đóng băng "
                        "chờ Quản lý chốt đổi/hủy"
                    ),
                    http_status=409,
                )
            if order["status"] != "NEW":
                raise BusinessError(
                    code="INVALID_STATE",
                    message=(
                        f"Đơn {order['erp_order_number']} đang ở trạng thái "
                        f"{order['status']}, không thể tạo phiên soạn"
                    ),
                    http_status=409,
                )
            allocs = OutboundRepository.get_order_allocations(db, oid)
            active_allocs = [
                a
                for a in allocs
                if a["status"] == "ACTIVE"
                and Decimal(str(a["qty_allocated"])) > Decimal(str(a["qty_picked"]))
            ]
            if not active_allocs:
                raise BusinessError(
                    code="INVALID_STATE",
                    message=(
                        f"Đơn {order['erp_order_number']} chưa có phân bổ tồn kho "
                        "(ALLOCATED) để soạn"
                    ),
                    http_status=409,
                )
            orders_to_pick.append({"order": order, "allocations": active_allocs})

        try:
            session_row = OutboundRepository.create_pick_session(
                db=db,
                warehouse_id=user_ctx.warehouse_id,
                picker_user_id=picker_id,
                pick_mode=req.pick_mode,
                shift_id=req.shift_id,
            )
            pick_session_id = uuid.UUID(str(session_row["pick_session_id"]))
            created_lines: list[dict[str, Any]] = []

            for item in orders_to_pick:
                oid = uuid.UUID(str(item["order"]["order_id"]))
                for alloc in item["allocations"]:
                    qty_to_pick = Decimal(str(alloc["qty_allocated"])) - Decimal(
                        str(alloc["qty_picked"])
                    )
                    pl_row = OutboundRepository.create_pick_line(
                        db=db,
                        pick_session_id=pick_session_id,
                        order_line_id=uuid.UUID(str(alloc["order_line_id"])),
                        allocation_id=uuid.UUID(str(alloc["allocation_id"])),
                        source_location_id=uuid.UUID(str(alloc["location_id"])),
                        suggested_lot_id=(
                            uuid.UUID(str(alloc["lot_id"])) if alloc["lot_id"] else None
                        ),
                        qty_to_pick=qty_to_pick,
                    )
                    created_lines.append(
                        {
                            "pick_line_id": str(pl_row["pick_line_id"]),
                            "order_line_id": str(pl_row["order_line_id"]),
                            "allocation_id": str(pl_row["allocation_id"]),
                            "source_location_id": str(pl_row["source_location_id"]),
                            "suggested_lot_id": (
                                str(pl_row["suggested_lot_id"])
                                if pl_row["suggested_lot_id"]
                                else None
                            ),
                            "qty_to_pick": _fmt_num(pl_row["qty_to_pick"]),
                            "qty_picked": _fmt_num(pl_row["qty_picked"]),
                            "status": pl_row["status"],
                        }
                    )

                OutboundRepository.bump_order_version(
                    db=db,
                    order_id=oid,
                    new_status="PICKING",
                )

            has_urgent = any(bool(item["order"].get("is_urgent")) for item in orders_to_pick)
            t = create_task(
                db=db,
                warehouse_id=user_ctx.warehouse_id,
                creator_id=user_ctx.user_id,
                req=_task_req(
                    task_type="PICKING",
                    stage="SOAN_HANG",
                    ref_doc_type="PICK_SESSION",
                    ref_doc_id=pick_session_id,
                    zone_id=None,
                    priority="HIGH" if has_urgent else "NORMAL",
                ),
            )
            if req.picker_user_id:
                assign_task(
                    db=db,
                    task_id=t.task_id,
                    assigner_id=user_ctx.user_id,
                    req=_task_req(assigned_to_user_id=req.picker_user_id, version_no=t.version_no),
                    warehouse_id=user_ctx.warehouse_id,
                )
            create_audit_log(
                db=db,
                action_code="CREATE_PICK_SESSION",
                entity_name="pick_sessions",
                actor_user_id=user_ctx.user_id,
                warehouse_id=user_ctx.warehouse_id,
                entity_id=pick_session_id,
                new_values={
                    "order_ids": [str(x) for x in req.order_ids],
                    "picker_user_id": str(picker_id),
                    "pick_mode": req.pick_mode,
                },
            )
        except Exception as exc:
            raise _translate_outbound_db_error(exc) from exc

        return {
            "pick_session_id": str(pick_session_id),
            "warehouse_id": str(session_row["warehouse_id"]),
            "pick_mode": session_row["pick_mode"],
            "picker_user_id": str(session_row["picker_user_id"]),
            "status": session_row["status"],
            "started_at": _fmt_dt(session_row["started_at"]),
            "version_no": int(session_row["version_no"]),
            "lines": created_lines,
        }

    @staticmethod
    def get_pick_session_detail(
        db: Session,
        user_ctx: UserContext,
        pick_session_id: uuid.UUID,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        ps = OutboundRepository.get_pick_session_raw(db, pick_session_id)
        if not ps:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy phiên soạn hàng",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, ps["warehouse_id"])

        lines_raw = OutboundRepository.get_pick_lines(db, pick_session_id)
        lines = [
            {
                "pick_line_id": str(line["pick_line_id"]),
                "order_line_id": str(line["order_line_id"]),
                "order_id": str(line["order_id"]),
                "erp_order_number": line["erp_order_number"],
                "sku_id": str(line["sku_id"]),
                "sku_code": line["sku_code"],
                "sku_name": line["sku_name"],
                "allocation_id": str(line["allocation_id"]) if line["allocation_id"] else None,
                "source_location_id": str(line["source_location_id"]),
                "source_location_code": line["source_location_code"],
                "staged_location_id": (
                    str(line["staged_location_id"]) if line["staged_location_id"] else None
                ),
                "suggested_lot_id": (
                    str(line["suggested_lot_id"]) if line["suggested_lot_id"] else None
                ),
                "actual_lot_id": str(line["actual_lot_id"]) if line["actual_lot_id"] else None,
                "serial_numbers": line["serial_numbers"] or [],
                "target_tote_barcode": line["target_tote_barcode"],
                "qty_to_pick": _fmt_num(line["qty_to_pick"]),
                "qty_picked": _fmt_num(line["qty_picked"]),
                "status": line["status"],
                "exception_reason": line["exception_reason"],
            }
            for line in lines_raw
        ]

        return {
            "pick_session_id": str(ps["pick_session_id"]),
            "warehouse_id": str(ps["warehouse_id"]),
            "pick_mode": ps["pick_mode"],
            "picker_user_id": str(ps["picker_user_id"]),
            "picker_name": ps["picker_name"],
            "status": ps["status"],
            "started_at": _fmt_dt(ps["started_at"]),
            "completed_at": _fmt_dt(ps["completed_at"]),
            "version_no": int(ps["version_no"]),
            "lines": lines,
        }

    @staticmethod
    def confirm_pick_line(
        db: Session,
        user_ctx: UserContext,
        pick_session_id: uuid.UUID,
        pick_line_id: uuid.UUID,
        req: ConfirmPickLineRequest,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        _require_access(access_type, ("X", "X_OWN"))
        ps = OutboundRepository.get_pick_session_raw(db, pick_session_id, for_update=True)
        if not ps:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy phiên soạn hàng",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, ps["warehouse_id"])

        if req.version_no is not None and int(ps["version_no"]) != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Phiên soạn hàng đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": int(ps["version_no"])},
            )

        if ps["status"] not in ("OPEN", "IN_PROGRESS"):
            raise BusinessError(
                code="INVALID_STATE",
                message=(
                    f"Phiên soạn đang ở trạng thái {ps['status']}, " "không thể xác nhận dòng soạn"
                ),
                http_status=409,
            )

        line = OutboundRepository.get_pick_line_detail(db, pick_session_id, pick_line_id)
        if not line:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy dòng soạn hàng trong phiên này",
                http_status=404,
            )

        if line["erp_change_pending"]:
            raise BusinessError(
                code="ORDER_FROZEN",
                message="Đơn hàng đang bị đóng băng do yêu cầu đổi/hủy từ ERP",
                http_status=409,
            )

        if line["status"] != "PENDING":
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Dòng soạn đã ở trạng thái {line['status']}",
                http_status=409,
            )

        qty_to_pick = Decimal(str(line["qty_to_pick"]))
        if req.qty_picked > qty_to_pick:
            raise BusinessError(
                code="OUTBOUND_PICK_QTY_EXCEEDED",
                message="Số lượng thực lấy vượt quá số lượng cần soạn",
                http_status=409,
            )
        if req.qty_picked < qty_to_pick:
            raise BusinessError(
                code="OUTBOUND_PARTIAL_PICK_REQUIRES_EXCEPTION",
                message=(
                    "Số lượng thực lấy nhỏ hơn số lượng cần soạn; "
                    "vui lòng báo ngoại lệ qua /exception"
                ),
                http_status=409,
            )

        warehouse_id = uuid.UUID(str(line["warehouse_id"]))
        source_location_id = uuid.UUID(str(line["source_location_id"]))
        staged_location_id = (
            req.staged_location_id
            or OutboundRepository.get_default_staging_location(db, warehouse_id)
        )
        actual_lot_id = req.actual_lot_id or (
            uuid.UUID(str(line["suggested_lot_id"])) if line["suggested_lot_id"] else None
        )
        actual_pallet_id = uuid.UUID(str(line["pallet_id"])) if line.get("pallet_id") else None
        actual_serial_number = line.get("serial_number")

        try:
            suggested_lot = (
                uuid.UUID(str(line["suggested_lot_id"])) if line["suggested_lot_id"] else None
            )
            if req.actual_lot_id and req.actual_lot_id != suggested_lot and line["allocation_id"]:
                alt_bal = OutboundRepository.find_lot_balance_at_location(
                    db,
                    source_location_id,
                    uuid.UUID(str(line["sku_id"])),
                    req.actual_lot_id,
                    req.qty_picked,
                )
                if not alt_bal:
                    raise BusinessError(
                        code="OUTBOUND_INVALID_ACTUAL_LOT",
                        message="Lô thực tế không đủ tồn khả dụng tại vị trí kệ đang lấy",
                        http_status=409,
                    )
                apply_movement(
                    db=db,
                    warehouse_id=uuid.UUID(str(line["warehouse_id"])),
                    location_id=uuid.UUID(str(line["source_location_id"])),
                    sku_id=uuid.UUID(str(line["sku_id"])),
                    lot_id=(
                        uuid.UUID(str(line["suggested_lot_id"]))
                        if line.get("suggested_lot_id")
                        else None
                    ),
                    pallet_id=uuid.UUID(str(line["pallet_id"])) if line.get("pallet_id") else None,
                    serial_number=line.get("serial_number"),
                    tx_type="DEALLOCATE",
                    delta_available=req.qty_picked,
                    delta_allocated=-req.qty_picked,
                    ref_doc_type="PICK_SESSION",
                    ref_doc_id=pick_session_id,
                    performed_by=user_ctx.user_id,
                )
                apply_movement(
                    db=db,
                    warehouse_id=uuid.UUID(str(line["warehouse_id"])),
                    location_id=source_location_id,
                    sku_id=uuid.UUID(str(line["sku_id"])),
                    lot_id=req.actual_lot_id,
                    pallet_id=(
                        uuid.UUID(str(alt_bal["pallet_id"])) if alt_bal.get("pallet_id") else None
                    ),
                    serial_number=alt_bal.get("serial_number"),
                    tx_type="ALLOCATE",
                    delta_available=-req.qty_picked,
                    delta_allocated=req.qty_picked,
                    ref_doc_type="PICK_SESSION",
                    ref_doc_id=pick_session_id,
                    performed_by=user_ctx.user_id,
                )
                actual_pallet_id = (
                    uuid.UUID(str(alt_bal["pallet_id"])) if alt_bal.get("pallet_id") else None
                )
                actual_serial_number = alt_bal.get("serial_number")
                OutboundRepository.swap_allocation_balance(
                    db,
                    uuid.UUID(str(line["allocation_id"])),
                    uuid.UUID(str(alt_bal["balance_id"])),
                    req.actual_lot_id,
                )
            # Chuyển hàng ALLOCATED từ vị trí kệ sang vị trí STAGING (nếu khác vị trí)
            if staged_location_id and staged_location_id != source_location_id:
                transfer_inventory(
                    db=db,
                    warehouse_id=warehouse_id,
                    from_location_id=source_location_id,
                    to_location_id=staged_location_id,
                    sku_id=uuid.UUID(str(line["sku_id"])),
                    lot_id=actual_lot_id,
                    pallet_id=actual_pallet_id,
                    serial_number=actual_serial_number,
                    qty=req.qty_picked,
                    tx_type="PICK_TO_STAGING",
                    ref_doc_type="PICK_SESSION",
                    ref_doc_id=pick_session_id,
                    performed_by=user_ctx.user_id,
                    bucket="ALLOCATED",
                )

            OutboundRepository.complete_pick_line_db(
                db=db,
                pick_line_id=pick_line_id,
                allocation_id=(
                    uuid.UUID(str(line["allocation_id"])) if line["allocation_id"] else None
                ),
                order_line_id=uuid.UUID(str(line["order_line_id"])),
                actual_lot_id=actual_lot_id,
                qty_picked=req.qty_picked,
                target_tote_barcode=req.target_tote_barcode,
                staged_location_id=staged_location_id or source_location_id,
                serial_numbers=req.serial_numbers,
            )

            ps_updated = OutboundRepository.refresh_pick_session_and_orders_after_pick(
                db=db,
                pick_session_id=pick_session_id,
            )
            lt = OutboundRepository.get_latest_picking_task(db, pick_session_id)
            if lt and str(lt["assigned_to"]) == str(user_ctx.user_id):
                tid = uuid.UUID(str(lt["task_id"]))
                tver = int(lt["version_no"])
                tstatus = str(lt["status"])
                if tstatus == "ASSIGNED":
                    acc_res = accept_task(
                        db=db,
                        task_id=tid,
                        worker_id=user_ctx.user_id,
                        req=_task_req(version_no=tver),
                        warehouse_id=warehouse_id,
                    )
                    tver = acc_res.version_no
                if ps_updated["status"] == "COMPLETED" and tstatus != "COMPLETED":
                    complete_task(
                        db=db,
                        task_id=tid,
                        worker_id=user_ctx.user_id,
                        req=_task_req(version_no=tver, completed_qty=None),
                        warehouse_id=warehouse_id,
                    )

            create_audit_log(
                db=db,
                action_code="CONFIRM_PICK_LINE",
                entity_name="pick_lines",
                actor_user_id=user_ctx.user_id,
                warehouse_id=warehouse_id,
                entity_id=pick_line_id,
                new_values={
                    "pick_session_id": str(pick_session_id),
                    "qty_picked": _fmt_num(req.qty_picked),
                    "staged_location_id": (str(staged_location_id) if staged_location_id else None),
                },
            )
        except Exception as exc:
            raise _translate_outbound_db_error(exc) from exc

        return {
            "pick_line_id": str(pick_line_id),
            "pick_session_id": str(pick_session_id),
            "status": "PICKED",
            "qty_picked": _fmt_num(req.qty_picked),
            "staged_location_id": str(staged_location_id) if staged_location_id else None,
            "session_status": ps_updated["status"],
            "session_version_no": int(ps_updated["version_no"]),
        }

    @staticmethod
    def report_pick_line_exception(
        db: Session,
        user_ctx: UserContext,
        pick_session_id: uuid.UUID,
        pick_line_id: uuid.UUID,
        req: PickLineExceptionRequest,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        _require_access(access_type, ("X", "X_OWN"))
        ps = OutboundRepository.get_pick_session_raw(db, pick_session_id, for_update=True)
        if not ps:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy phiên soạn hàng",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, ps["warehouse_id"])

        line = OutboundRepository.get_pick_line_detail(db, pick_session_id, pick_line_id)
        if not line:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy dòng soạn hàng",
                http_status=404,
            )

        if line["status"] != "PENDING":
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Không thể báo ngoại lệ cho dòng soạn đang ở trạng thái {line['status']}",
                http_status=409,
            )

        if not OutboundRepository.check_reason_code_exists(db, req.exception_reason):
            raise BusinessError(
                code="OUTBOUND_INVALID_REASON_CODE",
                message=(
                    f"Mã lý do ngoại lệ '{req.exception_reason}' "
                    "không tồn tại hoặc đã ngưng hoạt động"
                ),
                http_status=422,
            )

        allowed_types = {"EXCEPTION_SHORT", "EXCEPTION_DAMAGED", "EXCEPTION_WRONG_LOT"}
        exc_type = req.exception_type if req.exception_type in allowed_types else "EXCEPTION_SHORT"

        try:
            qty_to_release = Decimal(str(line["qty_to_pick"]))
            if qty_to_release > Decimal("0"):
                apply_movement(
                    db=db,
                    warehouse_id=uuid.UUID(str(line["warehouse_id"])),
                    location_id=uuid.UUID(str(line["source_location_id"])),
                    sku_id=uuid.UUID(str(line["sku_id"])),
                    lot_id=(
                        uuid.UUID(str(line["suggested_lot_id"]))
                        if line.get("suggested_lot_id")
                        else None
                    ),
                    pallet_id=uuid.UUID(str(line["pallet_id"])) if line.get("pallet_id") else None,
                    serial_number=line.get("serial_number"),
                    tx_type="DEALLOCATE",
                    delta_available=qty_to_release,
                    delta_allocated=-qty_to_release,
                    ref_doc_type="PICK_SESSION",
                    ref_doc_id=pick_session_id,
                    performed_by=user_ctx.user_id,
                )
            OutboundRepository.record_pick_line_exception_db(
                db=db,
                pick_line_id=pick_line_id,
                pick_session_id=pick_session_id,
                order_id=uuid.UUID(str(line["order_id"])),
                exception_type=exc_type,
                exception_reason=req.exception_reason,
                qty_actual=req.qty_actual,
            )

            create_audit_log(
                db=db,
                action_code="PICK_LINE_EXCEPTION",
                entity_name="pick_lines",
                actor_user_id=user_ctx.user_id,
                warehouse_id=uuid.UUID(str(line["warehouse_id"])),
                entity_id=pick_line_id,
                new_values={
                    "exception_type": exc_type,
                    "exception_reason": req.exception_reason,
                    "qty_actual": _fmt_num(req.qty_actual),
                },
            )
        except Exception as exc:
            raise _translate_outbound_db_error(exc) from exc

        return {
            "pick_line_id": str(pick_line_id),
            "pick_session_id": str(pick_session_id),
            "status": exc_type,
            "exception_reason": req.exception_reason,
            "qty_actual": _fmt_num(req.qty_actual),
            "session_status": "ON_HOLD_SHORTAGE",
        }

    @staticmethod
    def create_package(
        db: Session,
        user_ctx: UserContext,
        order_id: uuid.UUID,
        req: CreatePackageRequest,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        _require_access(access_type, ("X",))
        order = OutboundRepository.get_order_raw(db, order_id, for_update=True)
        if not order:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy đơn xuất kho",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, order["warehouse_id"])

        if order["erp_change_pending"]:
            raise BusinessError(
                code="ORDER_FROZEN",
                message="Đơn hàng đang bị đóng băng chờ Quản lý chốt đổi/hủy từ ERP",
                http_status=409,
            )

        if req.version_no is not None and int(order["version_no"]) != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Đơn xuất kho đã được người khác cập nhật",
                http_status=409,
                details={"current_version_no": int(order["version_no"])},
            )

        if order["status"] not in ("PICKED", "PACKING", "READY_TO_SHIP"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Đơn hàng ở trạng thái {order['status']}, chưa sẵn sàng đóng gói",
                http_status=409,
            )

        order_lines = OutboundRepository.get_order_lines(db, order_id)
        lines_by_id = {str(line["order_line_id"]): line for line in order_lines}

        items_payload: list[dict[str, Any]] = []
        if req.items:
            for item in req.items:
                ol = lines_by_id.get(str(item.order_line_id))
                if not ol:
                    raise BusinessError(
                        code="NOT_FOUND",
                        message=f"Không tìm thấy dòng đơn hàng {item.order_line_id}",
                        http_status=404,
                    )
                qty_picked = Decimal(str(ol["qty_picked"]))
                qty_packed = Decimal(str(ol["qty_packed"]))
                if qty_packed + item.qty > qty_picked:
                    raise BusinessError(
                        code="OUTBOUND_EXCEED_PICKED_QTY",
                        message="Số lượng đóng gói vượt quá số lượng đã soạn của dòng đơn",
                        http_status=409,
                    )
                items_payload.append(
                    {
                        "order_line_id": item.order_line_id,
                        "sku_id": item.sku_id,
                        "lot_id": item.lot_id,
                        "qty": item.qty,
                        "serial_numbers": item.serial_numbers,
                    }
                )
        else:
            # Mặc định đóng gói toàn bộ phần đã soạn nhưng chưa đóng gói của đơn
            for ol in order_lines:
                rem = Decimal(str(ol["qty_picked"])) - Decimal(str(ol["qty_packed"]))
                if rem > Decimal("0"):
                    items_payload.append(
                        {
                            "order_line_id": uuid.UUID(str(ol["order_line_id"])),
                            "sku_id": uuid.UUID(str(ol["sku_id"])),
                            "lot_id": None,
                            "qty": rem,
                            "serial_numbers": [],
                        }
                    )

        if not items_payload:
            raise BusinessError(
                code="INVALID_STATE",
                message="Không còn hàng đã soạn nào cần đóng gói cho đơn này",
                http_status=409,
            )

        try:
            pkg = OutboundRepository.create_package_with_lines(
                db=db,
                order_id=order_id,
                pick_session_id=req.pick_session_id,
                box_type_id=req.box_type_id,
                weight_kg=req.weight_kg,
                length_cm=req.length_cm,
                width_cm=req.width_cm,
                height_cm=req.height_cm,
                packed_by=user_ctx.user_id,
                items=items_payload,
            )

            create_audit_log(
                db=db,
                action_code="CREATE_PACKAGE",
                entity_name="packages",
                actor_user_id=user_ctx.user_id,
                warehouse_id=uuid.UUID(str(order["warehouse_id"])),
                entity_id=uuid.UUID(str(pkg["package_id"])),
                new_values={
                    "order_id": str(order_id),
                    "package_barcode": pkg["package_barcode"],
                    "weight_kg": _fmt_num(pkg["weight_kg"]),
                },
            )
        except Exception as exc:
            raise _translate_outbound_db_error(exc) from exc

        return {
            "package_id": str(pkg["package_id"]),
            "package_barcode": pkg["package_barcode"],
            "order_id": str(pkg["order_id"]),
            "box_type_id": str(pkg["box_type_id"]) if pkg["box_type_id"] else None,
            "weight_kg": _fmt_num(pkg["weight_kg"]),
            "packed_at": _fmt_dt(pkg["packed_at"]),
            "order_status": pkg["order_status"],
            "lines": pkg["lines"],
        }

    @staticmethod
    def create_goods_issue(
        db: Session,
        user_ctx: UserContext,
        req: CreateGoodsIssueRequest,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        _require_access(access_type, ("X",))
        order = OutboundRepository.get_order_raw(db, req.order_id, for_update=True)
        if not order:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy đơn xuất kho",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, order["warehouse_id"])

        if order["erp_change_pending"]:
            raise BusinessError(
                code="ORDER_FROZEN",
                message="Đơn hàng đang bị đóng băng chờ Quản lý chốt đổi/hủy từ ERP",
                http_status=409,
            )

        if req.version_no is not None and int(order["version_no"]) != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Đơn xuất kho đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": int(order["version_no"])},
            )

        if order["status"] not in ("PACKING", "WAITING_WAYBILL", "READY_TO_SHIP"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Đơn hàng ở trạng thái {order['status']}, chưa thể lập phiếu xuất kho GI",
                http_status=409,
            )

        packages = OutboundRepository.get_order_packages(db, req.order_id)
        unassigned_pkgs = [p for p in packages if p["gi_id"] is None]
        if not unassigned_pkgs:
            raise BusinessError(
                code="OUTBOUND_NO_PACKAGES",
                message="Đơn hàng chưa có kiện hàng đóng gói nào để lập phiếu xuất kho GI",
                http_status=409,
            )

        order_type = str(order["order_type"])
        gi_type = "SO_SHIPMENT" if order_type == "SO" else order_type

        warehouse_id = uuid.UUID(str(order["warehouse_id"]))
        order_status = str(order["status"])
        try:
            gi = OutboundRepository.create_goods_issue_and_link_packages(
                db=db,
                warehouse_id=warehouse_id,
                order_id=req.order_id,
                gi_type=gi_type,
                vehicle_id=req.vehicle_id,
                tms_waybill_code=req.tms_waybill_code,
            )
            if not req.tms_waybill_code:
                wb = request_waybill(
                    db=db,
                    warehouse_id=warehouse_id,
                    gi_id=uuid.UUID(str(gi["gi_id"])),
                    payload={"gi_number": gi["gi_number"], "order_id": str(req.order_id)},
                )
                gi = OutboundRepository.update_gi_waybill_and_order_status(
                    db=db,
                    gi_id=uuid.UUID(str(gi["gi_id"])),
                    order_id=req.order_id,
                    waybill_code=wb,
                )
                order_status = "READY_TO_SHIP" if wb else "WAITING_WAYBILL"

            create_audit_log(
                db=db,
                action_code="CREATE_GOODS_ISSUE",
                entity_name="goods_issues",
                actor_user_id=user_ctx.user_id,
                warehouse_id=uuid.UUID(str(order["warehouse_id"])),
                entity_id=uuid.UUID(str(gi["gi_id"])),
                new_values={
                    "gi_number": gi["gi_number"],
                    "order_id": str(req.order_id),
                    "total_packages": int(gi["total_packages"]),
                },
            )
        except Exception as exc:
            raise _translate_outbound_db_error(exc) from exc

        return {
            "gi_id": str(gi["gi_id"]),
            "gi_number": gi["gi_number"],
            "gi_type": gi["gi_type"],
            "warehouse_id": str(gi["warehouse_id"]),
            "order_id": str(gi["order_id"]),
            "vehicle_id": str(gi["vehicle_id"]) if gi["vehicle_id"] else None,
            "tms_waybill_code": gi["tms_waybill_code"],
            "total_packages": int(gi["total_packages"]),
            "status": gi["status"],
            "order_status": order_status,
            "version_no": int(gi["version_no"]),
        }

    @staticmethod
    def confirm_goods_issue(
        db: Session,
        user_ctx: UserContext,
        gi_id: uuid.UUID,
        req: ConfirmGoodsIssueRequest,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        _require_access(access_type, ("X",))
        gi = OutboundRepository.get_goods_issue_raw(db, gi_id, for_update=True)
        if not gi:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy phiếu xuất kho GI",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, gi["warehouse_id"])

        if gi["erp_change_pending"]:
            raise BusinessError(
                code="ORDER_FROZEN",
                message="Đơn hàng đang bị đóng băng chờ Quản lý chốt đổi/hủy từ ERP",
                http_status=409,
            )

        if req.version_no is not None and int(gi["version_no"]) != req.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Phiếu xuất kho GI đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": int(gi["version_no"])},
            )

        if gi["status"] not in ("PACKING", "WAITING_WAYBILL", "LOADED"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Phiếu xuất kho đang ở trạng thái {gi['status']}, không thể xác nhận xuất",
                http_status=409,
            )

        sig = req.driver_signature_data or gi["driver_signature_data"]
        if gi["gi_type"] != "SUPPLIER_RETURN" and not sig:
            raise BusinessError(
                code="OUTBOUND_DRIVER_SIGNATURE_REQUIRED",
                message="Bắt buộc có chữ ký xác nhận của tài xế trước khi xuất kho",
                http_status=409,
            )

        waybill_code = gi.get("tms_waybill_code") or get_waybill(db, gi_id)
        if waybill_code and not gi.get("tms_waybill_code"):
            gi = OutboundRepository.update_gi_waybill_and_order_status(
                db=db,
                gi_id=gi_id,
                order_id=uuid.UUID(str(gi["order_id"])),
                waybill_code=waybill_code,
            )
        if gi["gi_type"] in ("SO_SHIPMENT", "INTER_WH_TRANSFER") and not waybill_code:
            raise BusinessError(
                code="OUTBOUND_WAYBILL_REQUIRED",
                message="Bắt buộc có mã vận đơn TMS trước khi xác nhận xuất kho",
                http_status=409,
            )

        warehouse_id = uuid.UUID(str(gi["warehouse_id"]))
        order_id = uuid.UUID(str(gi["order_id"]))
        shippable_items = OutboundRepository.get_shippable_staging_items(db, order_id)

        try:
            # Trừ tồn kho ALLOCATED tại vị trí xuất (STAGING) và ghi sổ cái xuất kho
            for item in shippable_items:
                qty = Decimal(str(item["qty_picked"]))
                if qty <= Decimal("0"):
                    continue
                apply_movement(
                    db=db,
                    warehouse_id=warehouse_id,
                    location_id=uuid.UUID(str(item["ship_location_id"])),
                    sku_id=uuid.UUID(str(item["sku_id"])),
                    lot_id=uuid.UUID(str(item["lot_id"])) if item["lot_id"] else None,
                    pallet_id=uuid.UUID(str(item["pallet_id"])) if item["pallet_id"] else None,
                    serial_number=item["serial_number"],
                    tx_type="SHIP_GI",
                    delta_allocated=-qty,
                    ref_doc_type="GI",
                    ref_doc_id=gi_id,
                    performed_by=user_ctx.user_id,
                )

            wb = gi.get("tms_waybill_code")
            if not wb and gi["gi_type"] == "SO_SHIPMENT":
                wb = get_waybill(db, gi_id) or request_waybill(
                    db=db,
                    warehouse_id=warehouse_id,
                    gi_id=gi_id,
                    payload={"gi_number": gi["gi_number"], "order_id": str(order_id)},
                )
                if wb:
                    OutboundRepository.update_gi_waybill_and_order_status(db, gi_id, order_id, wb)
            final_gi = OutboundRepository.finalize_goods_issue_and_order(
                db=db,
                gi_id=gi_id,
                order_id=order_id,
                confirmed_by=user_ctx.user_id,
                driver_signature_data=req.driver_signature_data,
                handover_photo_urls=req.handover_photo_urls,
            )
            erp_sync_id = enqueue_to_erp(
                db=db,
                warehouse_id=warehouse_id,
                doc_type="GI",
                doc_id=gi_id,
                payload={
                    "gi_id": str(gi_id),
                    "gi_number": final_gi["gi_number"],
                    "order_id": str(order_id),
                    "tms_waybill_code": wb,
                },
            )

            create_audit_log(
                db=db,
                action_code="CONFIRM_GOODS_ISSUE",
                entity_name="goods_issues",
                actor_user_id=user_ctx.user_id,
                warehouse_id=warehouse_id,
                entity_id=gi_id,
                new_values={
                    "gi_number": final_gi["gi_number"],
                    "order_id": str(order_id),
                    "status": "GI_CONFIRMED",
                    "order_status": "SHIPPED",
                },
            )
        except Exception as exc:
            raise _translate_outbound_db_error(exc) from exc

        return {
            "gi_id": str(final_gi["gi_id"]),
            "gi_number": final_gi["gi_number"],
            "order_id": str(order_id),
            "status": final_gi["status"],
            "order_status": "SHIPPED",
            "tms_waybill_code": wb,
            "erp_sync_id": str(erp_sync_id),
            "total_packages": int(final_gi["total_packages"]),
            "confirmed_by": str(final_gi["confirmed_by"]),
            "confirmed_at": _fmt_dt(final_gi["confirmed_at"]),
            "version_no": int(final_gi["version_no"]),
        }

    @staticmethod
    def decide_order_change(
        db: Session,
        user_ctx: UserContext,
        request_id: uuid.UUID,
        req: DecideOrderChangeRequest,
        access_type: str | None = None,
    ) -> dict[str, Any]:
        _require_access(access_type, ("X",))
        if user_ctx.role_code not in ("quanly", "bgd"):
            raise BusinessError(
                code="FORBIDDEN",
                message="Chỉ Quản lý kho được chốt yêu cầu đổi/hủy đơn từ ERP",
                http_status=403,
            )

        change_req = OutboundRepository.get_order_change_request_raw(db, request_id)
        if not change_req:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy yêu cầu đổi/hủy đơn từ ERP",
                http_status=404,
            )
        enforce_warehouse_scope(user_ctx, change_req["warehouse_id"])

        decision = req.decision.strip().upper()
        try:
            OutboundRepository.call_decide_order_change(
                db=db,
                request_id=request_id,
                decision=decision,
                manager_id=user_ctx.user_id,
                note=req.reject_note,
            )

            create_audit_log(
                db=db,
                action_code="ERP_ORDER_CHANGE",
                entity_name="order_change_requests",
                actor_user_id=user_ctx.user_id,
                warehouse_id=uuid.UUID(str(change_req["warehouse_id"])),
                entity_id=request_id,
                new_values={
                    "order_id": str(change_req["order_id"]),
                    "decision": decision,
                    "reject_note": req.reject_note,
                },
            )
        except Exception as exc:
            raise _translate_outbound_db_error(exc) from exc

        updated_req = OutboundRepository.get_order_change_request_raw(db, request_id)
        updated_order = OutboundRepository.get_order_raw(db, uuid.UUID(str(change_req["order_id"])))

        return {
            "request_id": str(request_id),
            "order_id": str(change_req["order_id"]),
            "decision": decision,
            "request_status": updated_req["status"] if updated_req else decision,
            "order_status": updated_order["status"] if updated_order else None,
            "erp_change_pending": (
                bool(updated_order["erp_change_pending"]) if updated_order else False
            ),
        }
