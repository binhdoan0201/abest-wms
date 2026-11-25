"""ABEST WMS - Services cho Phân hệ Kiểm kê (Cycle Count)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace as CreateTaskRequest
from typing import Any

from sqlalchemy.orm import Session

from server.app.core.audit import create_audit_log
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, enforce_warehouse_scope
from server.app.modules.approvals import create_approval_request
from server.app.modules.cycle_count.models import (
    CycleCountAttempt,
    CycleCountLine,
    CycleCountSheet,
)
from server.app.modules.cycle_count.repositories import CycleCountRepository
from server.app.modules.cycle_count.schemas import CreateCycleCountRequest, RecordCountRequest
from server.app.modules.inventory import apply_movement
from server.app.modules.master_data import get_sku, get_warehouse_config
from server.app.modules.tasks import create_task

VALID_COUNT_TYPES = ("PERIODIC", "RANDOM", "FULL", "SHORTAGE_TRIGGERED", "LOCATION")


def _fmt_qty(val: Decimal | None) -> str | None:
    return None if val is None else f"{val:.3f}"


def _fmt_money(val: Decimal | None) -> str | None:
    return None if val is None else f"{val:.2f}"


def _require_warehouse(user: UserContext) -> uuid.UUID:
    if user.warehouse_id is None:
        raise BusinessError(
            code="FORBIDDEN",
            message="Tài khoản chưa được gán kho làm việc",
            http_status=403,
        )
    return user.warehouse_id


def _sheet_dict(sheet: CycleCountSheet) -> dict[str, Any]:
    return {
        "count_sheet_id": str(sheet.count_sheet_id),
        "sheet_number": sheet.sheet_number,
        "warehouse_id": str(sheet.warehouse_id),
        "count_type": sheet.count_type,
        "created_by": str(sheet.created_by),
        "due_at": sheet.due_at.isoformat(),
        "status": sheet.status,
        "closed_at": sheet.closed_at.isoformat() if sheet.closed_at else None,
        "version_no": sheet.version_no,
        "created_at": sheet.created_at.isoformat(),
    }


def _line_dict(line: CycleCountLine, hide_blind: bool) -> dict[str, Any]:
    is_done = line.status in ("AUTO_APPROVED_Z", "APPROVED", "ADJUSTED", "REJECTED")
    mask = hide_blind and not is_done
    return {
        "count_line_id": str(line.count_line_id),
        "count_sheet_id": str(line.count_sheet_id),
        "location_id": str(line.location_id),
        "sku_id": str(line.sku_id) if line.sku_id else None,
        "lot_id": str(line.lot_id) if line.lot_id else None,
        "pallet_id": str(line.pallet_id) if line.pallet_id else None,
        "system_qty_snapshot": None if mask else _fmt_qty(line.system_qty_snapshot),
        "final_counted_qty": _fmt_qty(line.final_counted_qty),
        "variance_qty": None if mask else _fmt_qty(line.variance_qty),
        "variance_pct": None if mask or line.variance_pct is None else f"{line.variance_pct:.2f}",
        "variance_amount": None if mask else _fmt_money(line.variance_amount),
        "recount_count": line.recount_count,
        "anomaly_type": line.anomaly_type or "NONE",
        "status": line.status,
    }


class CycleCountService:
    """Service điều phối quy trình kiểm kê đếm mù, đếm lại và chốt kết quả."""

    @staticmethod
    def create_sheet(
        db: Session, user: UserContext, req: CreateCycleCountRequest
    ) -> dict[str, Any]:
        warehouse_id = _require_warehouse(user)
        if req.count_type not in VALID_COUNT_TYPES:
            raise BusinessError(
                code="VALIDATION_ERROR",
                message="Loại phiếu kiểm kê không hợp lệ",
                http_status=422,
            )

        db_count_type = "PERIODIC" if req.count_type == "LOCATION" else req.count_type
        now = datetime.now(timezone.utc)
        sheet_num = f"CC-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        sheet = CycleCountSheet(
            sheet_number=sheet_num,
            warehouse_id=warehouse_id,
            count_type=db_count_type,
            created_by=user.user_id,
            due_at=req.due_at,
            status="OPEN",
            version_no=1,
        )
        db.add(sheet)
        db.flush()

        lines: list[CycleCountLine] = []
        for loc_id in dict.fromkeys(req.location_ids):
            snapshots = CycleCountRepository.lock_location_for_count(
                db, warehouse_id, loc_id, user.user_id
            )
            if snapshots and snapshots[0].get("error") == "NOT_FOUND":
                raise BusinessError(
                    code="NOT_FOUND", message=f"Không tìm thấy vị trí {loc_id}", http_status=404
                )
            if snapshots and snapshots[0].get("error") == "MAINTENANCE_LOCKED":
                raise BusinessError(
                    code="INVALID_STATE",
                    message=f"Vị trí {loc_id} đang khóa bảo trì",
                    http_status=409,
                )

            if not snapshots:
                # Vị trí trống vẫn tạo 1 dòng kiểm để nhân viên xác nhận trống hoặc phát hiện hàng lạ  # noqa: E501
                ln = CycleCountLine(
                    count_sheet_id=sheet.count_sheet_id,
                    location_id=loc_id,
                    sku_id=None,
                    lot_id=None,
                    system_qty_snapshot=Decimal("0.000"),
                    status="PENDING",
                )
                db.add(ln)
                lines.append(ln)
            else:
                for snap in snapshots:
                    ln = CycleCountLine(
                        count_sheet_id=sheet.count_sheet_id,
                        location_id=loc_id,
                        sku_id=snap["sku_id"],
                        lot_id=snap["lot_id"],
                        pallet_id=snap["pallet_id"],
                        system_qty_snapshot=snap["sys_qty"],
                        status="PENDING",
                    )
                    db.add(ln)
                    lines.append(ln)

        create_task(
            db=db,
            warehouse_id=warehouse_id,
            creator_id=user.user_id,
            req=CreateTaskRequest(  # type: ignore[arg-type]
                zone_id=None,
                assigned_to=None,
                note=None,
                task_type="CYCLE_COUNT",
                stage="KIEM_KE",
                ref_doc_type="CYCLE_COUNT",
                ref_doc_id=sheet.count_sheet_id,
                priority="NORMAL",
            ),
        )
        db.flush()

        create_audit_log(
            db,
            action_code="CREATE_DOC",
            entity_name="cycle_count_sheets",
            actor_user_id=user.user_id,
            warehouse_id=warehouse_id,
            entity_id=sheet.count_sheet_id,
            new_values={"sheet_number": sheet.sheet_number, "lines_count": len(lines)},
        )
        res = _sheet_dict(sheet)
        res["lines"] = [_line_dict(ln, False) for ln in lines]
        return res

    @staticmethod
    def list_sheets(
        db: Session, user: UserContext, status: str | None, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        warehouse_id = _require_warehouse(user)
        if page < 1 or not 1 <= page_size <= 100:
            raise BusinessError(
                code="VALIDATION_ERROR", message="Tham số phân trang không hợp lệ", http_status=422
            )
        rows, total = CycleCountRepository.list_sheets(
            db, warehouse_id, status, (page - 1) * page_size, page_size
        )
        return [_sheet_dict(s) for s in rows], total, page, page_size

    @staticmethod
    def get_sheet_detail(db: Session, user: UserContext, sheet_id: uuid.UUID) -> dict[str, Any]:
        _require_warehouse(user)
        sheet = CycleCountRepository.get_sheet_by_id(db, sheet_id)
        if sheet is None:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy phiếu kiểm kê", http_status=404
            )
        enforce_warehouse_scope(user, sheet.warehouse_id)
        lines = CycleCountRepository.list_lines(db, sheet_id)
        hide_blind = user.role_code == "nv-kiemke"
        res = _sheet_dict(sheet)
        res["lines"] = [_line_dict(ln, hide_blind) for ln in lines]
        return res

    @staticmethod
    def record_count(
        db: Session,
        user: UserContext,
        sheet_id: uuid.UUID,
        line_id: uuid.UUID,
        req: RecordCountRequest,
        is_recount: bool = False,
    ) -> dict[str, Any]:
        warehouse_id = _require_warehouse(user)
        sheet = CycleCountRepository.get_sheet_by_id(db, sheet_id, for_update=True)
        if sheet is None:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy phiếu kiểm kê", http_status=404
            )
        enforce_warehouse_scope(user, sheet.warehouse_id)
        if sheet.status == "CLOSED":
            raise BusinessError(
                code="INVALID_STATE", message="Phiếu kiểm kê đã đóng", http_status=409
            )

        line = CycleCountRepository.get_line_by_id(db, line_id, for_update=True)
        if line is None or line.count_sheet_id != sheet_id:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy dòng kiểm kê", http_status=404
            )

        if req.blind_counted_qty < 0:
            raise BusinessError(
                code="VALIDATION_ERROR", message="Số lượng đếm không được âm", http_status=422
            )

        cfg = get_warehouse_config(db, warehouse_id)
        last_att = CycleCountRepository.get_latest_attempt(db, line_id)

        if not is_recount:
            if last_att is not None:
                raise BusinessError(
                    code="INVALID_STATE",
                    message="Dòng kiểm kê đã được đếm lần 1, vui lòng dùng API recount",
                    http_status=409,
                )
            attempt_no = 1
        else:
            if last_att is None:
                raise BusinessError(
                    code="INVALID_STATE",
                    message="Dòng kiểm kê chưa có lượt đếm đầu tiên",
                    http_status=409,
                )
            max_recount = int(cfg.get("max_recount_attempts") or 2)
            if line.recount_count >= max_recount:
                raise BusinessError(
                    code="INVALID_STATE",
                    message=f"Đã đạt giới hạn đếm lại tối đa ({max_recount} lần)",
                    http_status=409,
                )
            allow_same = bool(cfg.get("allow_same_counter_recount", False))
            if (
                not allow_same
                and last_att.counter_user_id == user.user_id
                and not (
                    req.same_counter_override_reason and req.same_counter_override_reason.strip()
                )
            ):
                raise BusinessError(
                    code="SAME_COUNTER_FORBIDDEN",
                    message="Người đếm lại bắt buộc phải khác người đếm lần trước",
                    http_status=400,
                )
            attempt_no = last_att.attempt_no + 1
            line.recount_count += 1

        db.add(
            CycleCountAttempt(
                count_line_id=line_id,
                attempt_no=attempt_no,
                counter_user_id=user.user_id,
                blind_counted_qty=req.blind_counted_qty,
                same_counter_override_reason=req.same_counter_override_reason,
            )
        )

        line.final_counted_qty = req.blind_counted_qty
        var_qty = req.blind_counted_qty - line.system_qty_snapshot
        line.variance_qty = var_qty

        unit_cost = Decimal("0")
        if line.sku_id is not None:
            sku = get_sku(db, line.sku_id)
            unit_cost = Decimal(str(sku.get("unit_cost", "0")))
        var_amt = (abs(var_qty) * unit_cost).quantize(Decimal("0.01"))
        line.variance_amount = var_amt

        if line.system_qty_snapshot > 0:
            var_pct = ((abs(var_qty) / line.system_qty_snapshot) * Decimal("100")).quantize(
                Decimal("0.01")
            )
        else:
            var_pct = Decimal("100.00") if var_qty != 0 else Decimal("0.00")
        line.variance_pct = var_pct

        if req.anomaly_type:
            line.anomaly_type = req.anomaly_type
        elif req.blind_counted_qty == 0 and line.system_qty_snapshot > 0:
            line.anomaly_type = "EMPTY_LOCATION"
        else:
            line.anomaly_type = "NONE"

        if sheet.status == "OPEN":
            sheet.status = "COUNTING"
            sheet.version_no += 1

        if var_qty == 0:
            line.status = "AUTO_APPROVED_Z"
        else:
            approval = create_approval_request(
                db=db,
                warehouse_id=warehouse_id,
                object_type="CYCLE_COUNT_DIFF",
                object_id=line.count_line_id,
                proposer_user_id=user.user_id,
                discrepancy_amount=var_amt,
                discrepancy_percent=var_pct,
                force_review=False,
            )
            if approval is None:
                # Tự duyệt trong dung sai Z -> ghi điều chỉnh tồn ngay
                if line.sku_id is not None:
                    apply_movement(
                        db=db,
                        warehouse_id=warehouse_id,
                        location_id=line.location_id,
                        sku_id=line.sku_id,
                        lot_id=line.lot_id,
                        pallet_id=line.pallet_id,
                        serial_number=None,
                        tx_type="CYCLE_COUNT",
                        delta_available=var_qty,
                        ref_doc_type="CYCLE_COUNT",
                        ref_doc_id=sheet.count_sheet_id,
                        performed_by=user.user_id,
                    )
                line.status = "AUTO_APPROVED_Z"
            else:
                sheet.status = "PENDING_APPROVAL"

        db.flush()
        db.refresh(line)
        hide_blind = user.role_code == "nv-kiemke"
        return _line_dict(line, hide_blind)

    @staticmethod
    def close_sheet(db: Session, user: UserContext, sheet_id: uuid.UUID) -> dict[str, Any]:
        warehouse_id = _require_warehouse(user)
        sheet = CycleCountRepository.get_sheet_by_id(db, sheet_id, for_update=True)
        if sheet is None:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy phiếu kiểm kê", http_status=404
            )
        enforce_warehouse_scope(user, sheet.warehouse_id)

        if sheet.status != "CLOSED":
            lines = CycleCountRepository.list_lines(db, sheet_id)
            for ln in lines:
                if ln.status == "APPROVED" and ln.sku_id is not None and ln.variance_qty:
                    apply_movement(
                        db=db,
                        warehouse_id=warehouse_id,
                        location_id=ln.location_id,
                        sku_id=ln.sku_id,
                        lot_id=ln.lot_id,
                        pallet_id=ln.pallet_id,
                        serial_number=None,
                        tx_type="CYCLE_COUNT",
                        delta_available=ln.variance_qty,
                        ref_doc_type="CYCLE_COUNT",
                        ref_doc_id=sheet.count_sheet_id,
                        performed_by=user.user_id,
                    )
                    ln.status = "ADJUSTED"
                elif ln.status == "PENDING":
                    ln.status = "REJECTED"

            CycleCountRepository.unlock_sheet_locations(db, sheet_id)
            sheet.status = "CLOSED"
            sheet.closed_at = datetime.now(timezone.utc)
            sheet.version_no += 1
            db.flush()

        create_audit_log(
            db,
            action_code="CLOSE_DOC",
            entity_name="cycle_count_sheets",
            actor_user_id=user.user_id,
            warehouse_id=warehouse_id,
            entity_id=sheet.count_sheet_id,
            new_values={"status": "CLOSED"},
        )
        return _sheet_dict(sheet)

    @staticmethod
    def get_sheet(db: Session, sheet_id: uuid.UUID) -> CycleCountSheet:
        sheet = CycleCountRepository.get_sheet_by_id(db, sheet_id)
        if not sheet:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy phiếu kiểm kê", http_status=404
            )
        return sheet
