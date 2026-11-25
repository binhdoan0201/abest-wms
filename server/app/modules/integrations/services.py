"""ABEST WMS - Services cho Phân hệ Tích hợp (Integrations), A-07.

Cách truy cập dữ liệu: qua `repositories.py`.

Hai chiều tích hợp, đều ghi `integration_sync_logs`:

1. **ERP -> WMS** (PO, ASN, đơn xuất): kiểm tra dữ liệu, đổi mã ERP sang ID nội bộ qua
   `master_data.find_by_code`, rồi giao cho hàm xử lý mà module sở hữu bảng (`inbound`,
   `outbound`) đăng ký bằng `register_erp_handler`. Chưa có module đăng ký thì dòng nhật ký giữ
   `PENDING` và được xử lý lại khi chạy `process_pending`. Cách này giữ đúng quy tắc 2.3
   (integrations không ghi bảng của module khác) và tránh vòng import.
2. **WMS -> ERP/TMS** (GRN, GI, điều chỉnh tồn, phản hồi đổi/hủy đơn, vận đơn): module nghiệp vụ
   ghi dòng `OUTBOUND` + `PENDING` (`enqueue_to_erp`, hoặc hàm DB, hoặc `approvals`);
   `process_pending` gửi qua cổng ERP/TMS (`server.app.integrations`). Lỗi kỹ thuật được thử lại
   tối đa `MAX_RETRIES` lần; lỗi nghiệp vụ chờ người xử lý (`retry` sau khi sửa, hoặc `resolve`).
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from server.app.core.audit import create_audit_log
from server.app.core.config import get_settings
from server.app.core.exceptions import BusinessError, translate_db_error
from server.app.core.rbac import UserContext
from server.app.integrations.erp_mock import get_erp_gateway
from server.app.integrations.gateways import GatewayResult
from server.app.integrations.tms_mock import get_tms_gateway
from server.app.modules.integrations.models import IntegrationSyncLog
from server.app.modules.integrations.repositories import IntegrationRepository
from server.app.modules.integrations.schemas import (
    ErpAsnPush,
    ErpOrderChangePush,
    ErpOutboundOrderPush,
    ErpPurchaseOrderPush,
    MockFailureConfig,
)
from server.app.modules.master_data import find_by_code

MAX_RETRIES = 5
INBOUND_DOC_TYPES = ("PO", "ASN", "SO")
OPERATOR_ROLES = {"admin", "quanly"}
LIST_FILTERS = ("external_system", "direction", "doc_type", "status")

# Hàm xử lý: (db, dữ liệu đã chuẩn hóa dạng JSON, người thao tác) -> ID chứng từ vừa tạo
ErpHandler = Callable[[Session, dict[str, Any], uuid.UUID], uuid.UUID]
_handlers: dict[str, ErpHandler] = {}


# ----------------------------------------------------------------------------- đăng ký xử lý


def register_erp_handler(doc_type: str, handler: ErpHandler) -> None:
    """Hàm công khai: module sở hữu bảng đăng ký hàm nhận chứng từ ERP.

    - `PO` -> `inbound` (tạo `purchase_orders`, `po_lines`)
    - `ASN` -> `inbound` (tạo `asns`)
    - `SO` -> `outbound` (tạo `outbound_orders`, `outbound_order_lines`)

    `handler(db, data, actor_id)` nhận dict đã chuẩn hóa (UUID, số, ngày giờ ở dạng chuỗi;
    xem `docs/api/integrations.md`), trả ID chứng từ đã tạo. Ném `BusinessError` khi dữ liệu
    không hợp lệ (ví dụ trùng số PO); lỗi này được ghi `FAILED_BUSINESS`, không thử lại tự động.
    Gọi trong `__init__.py` của module để đăng ký khi khởi động.
    """
    if doc_type not in INBOUND_DOC_TYPES:
        raise ValueError(f"doc_type phải là một trong {INBOUND_DOC_TYPES}")
    _handlers[doc_type] = handler


def unregister_erp_handler(doc_type: str) -> None:
    """Gỡ đăng ký (dùng trong kiểm thử)."""
    _handlers.pop(doc_type, None)


# ----------------------------------------------------------------------------- tiện ích


@dataclass
class IngestResult:
    """Kết quả nhận một chứng từ: router dùng `http_status` và `error` để trả phản hồi."""

    log: dict[str, Any]
    http_status: int
    error: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, uuid.UUID | Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    return value


def _serialize_log(log: IntegrationSyncLog, hide_payload: bool = False) -> dict[str, Any]:
    data = {
        "sync_id": log.sync_id,
        "warehouse_id": log.warehouse_id,
        "external_system": log.external_system,
        "direction": log.direction,
        "doc_type": log.doc_type,
        "doc_id": log.doc_id,
        "status": log.status,
        "error_category": log.error_category,
        "error_message": log.error_message,
        "retry_count": log.retry_count,
        "technical_meta": log.technical_meta,
        "business_payload": None if hide_payload else log.business_payload,
        "resolved_by": log.resolved_by,
        "created_at": log.created_at,
        "updated_at": log.updated_at,
    }
    result: dict[str, Any] = _json_safe(data)
    return result


def _set_result(
    log: IntegrationSyncLog,
    status: str,
    category: str = "NONE",
    message: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    log.status = status
    log.error_category = category
    log.error_message = message
    if meta is not None:
        log.technical_meta = _json_safe({**(log.technical_meta or {}), **meta})
    IntegrationRepository.touch(log)


def _require_operator(user: UserContext) -> None:
    if user.role_code not in OPERATOR_ROLES:
        raise BusinessError(
            code="FORBIDDEN",
            message="Chỉ Quản lý kho hoặc Quản trị mới được xử lý hàng đợi tích hợp",
            http_status=403,
        )


def _scope_warehouse(user: UserContext) -> uuid.UUID | None:
    """Admin xem mọi kho; vai trò khác chỉ kho của mình."""
    if user.role_code == "admin":
        return None
    if user.warehouse_id is None:
        raise BusinessError(
            code="FORBIDDEN", message="Tài khoản chưa được gán kho làm việc", http_status=403
        )
    return user.warehouse_id


def _load_log(db: Session, user: UserContext, raw_id: str) -> IntegrationSyncLog:
    try:
        sync_id = uuid.UUID(raw_id)
    except ValueError:
        sync_id = None
    log = IntegrationRepository.get_log(db, sync_id, for_update=True) if sync_id else None
    scope = _scope_warehouse(user)
    if log is None or (scope is not None and log.warehouse_id != scope):
        raise BusinessError(
            code="NOT_FOUND", message="Không tìm thấy nhật ký đồng bộ", http_status=404
        )
    return log


# ----------------------------------------------------------------------------- chuẩn hóa ERP


class _CodeResolver:
    """Đổi mã ERP sang ID, gom mọi mã không tồn tại để báo một lần."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.missing: list[dict[str, str]] = []

    def get(
        self, resource: str, code: str | None, field_name: str, warehouse_id: Any = None
    ) -> str | None:
        if code is None:
            return None
        record = find_by_code(self.db, resource, code, warehouse_id=warehouse_id)
        if record is None:
            self.missing.append({"field": field_name, "code": code})
            return None
        pk = {
            "warehouses": "warehouse_id",
            "suppliers": "supplier_id",
            "customers": "customer_id",
            "skus": "sku_id",
            "locations": "location_id",
        }[resource]
        return str(record[pk])


def _normalize_po(r: _CodeResolver, req: ErpPurchaseOrderPush) -> dict[str, Any]:
    return {
        "erp_po_number": req.erp_po_number,
        "warehouse_id": r.get("warehouses", req.warehouse_code, "warehouse_code"),
        "supplier_id": r.get("suppliers", req.supplier_code, "supplier_code"),
        "expected_date": _json_safe(req.expected_date),
        "lines": [
            {
                "line_number": line.line_number,
                "sku_id": r.get("skus", line.sku_code, f"lines[{i}].sku_code"),
                "uom_code": line.uom_code,
                "qty_ordered": str(line.qty_ordered),
            }
            for i, line in enumerate(req.lines)
        ],
    }


def _normalize_asn(r: _CodeResolver, req: ErpAsnPush) -> dict[str, Any]:
    warehouse_id = r.get("warehouses", req.warehouse_code, "warehouse_code")
    dock_id = None
    if req.dock_location_code and warehouse_id:
        dock_id = r.get(
            "locations",
            req.dock_location_code,
            "dock_location_code",
            warehouse_id=uuid.UUID(warehouse_id),
        )
    return {
        "erp_asn_number": req.erp_asn_number,
        "warehouse_id": warehouse_id,
        "erp_po_number": req.erp_po_number,
        "supplier_id": r.get("suppliers", req.supplier_code, "supplier_code"),
        "expected_arrival_at": _json_safe(req.expected_arrival_at),
        "expected_pallets": req.expected_pallets,
        "assigned_dock_location_id": dock_id,
    }


def _normalize_order(r: _CodeResolver, req: ErpOutboundOrderPush) -> dict[str, Any]:
    return {
        "erp_order_number": req.erp_order_number,
        "order_type": req.order_type,
        "warehouse_id": r.get("warehouses", req.warehouse_code, "warehouse_code"),
        "customer_id": r.get("customers", req.customer_code, "customer_code"),
        "dest_warehouse_id": r.get("warehouses", req.dest_warehouse_code, "dest_warehouse_code"),
        "supplier_id": r.get("suppliers", req.supplier_code, "supplier_code"),
        "cutoff_time": _json_safe(req.cutoff_time),
        "is_urgent": req.is_urgent,
        "urgent_reason": req.urgent_reason,
        "route_code": req.route_code,
        "lines": [
            {
                "line_number": line.line_number,
                "sku_id": r.get("skus", line.sku_code, f"lines[{i}].sku_code"),
                "qty_ordered": str(line.qty_ordered),
            }
            for i, line in enumerate(req.lines)
        ],
    }


_NORMALIZERS: dict[str, Callable[[_CodeResolver, Any], dict[str, Any]]] = {
    "PO": _normalize_po,
    "ASN": _normalize_asn,
    "SO": _normalize_order,
}


# ----------------------------------------------------------------------------- xử lý một dòng


def _dispatch_inbound(db: Session, log: IntegrationSyncLog, actor_id: uuid.UUID) -> None:
    """Giao chứng từ ERP cho module đã đăng ký; lỗi của module không làm mất nhật ký."""
    handler = _handlers.get(log.doc_type)
    if handler is None:
        _set_result(
            log,
            "PENDING",
            message=f"Chưa có module đăng ký xử lý chứng từ {log.doc_type}; sẽ xử lý lại sau",
        )
        return

    normalized = (log.business_payload or {}).get("normalized", {})
    try:
        with db.begin_nested():
            doc_id = handler(db, normalized, actor_id)
    except BusinessError as exc:
        _set_result(
            log,
            "FAILED_BUSINESS",
            "BUSINESS_ERROR",
            f"{exc.code}: {exc.message}",
            {"error_code": exc.code, "error_details": exc.details},
        )
        return
    except Exception as exc:  # noqa: BLE001 - mọi lỗi kỹ thuật đều ghi nhận để thử lại
        log.retry_count += 1
        _set_result(log, "FAILED_TECHNICAL", "TECHNICAL_ERROR", str(exc)[:500])
        return

    log.doc_id = doc_id
    _set_result(log, "SUCCESS")


def _dispatch_outbound(log: IntegrationSyncLog) -> None:
    """Gửi một chứng từ sang ERP hoặc TMS qua cổng giả lập."""
    payload = log.business_payload or {}
    result: GatewayResult
    if log.external_system == "ERP":
        result = get_erp_gateway().send(log.doc_type, payload)
    elif log.external_system == "TMS":
        result = get_tms_gateway().request_waybill(payload)
    else:
        _set_result(
            log,
            "FAILED_BUSINESS",
            "BUSINESS_ERROR",
            f"Chưa hỗ trợ hệ thống ngoài `{log.external_system}`",
        )
        return

    if result.ok:
        _set_result(log, "SUCCESS", meta={"response": result.response})
    elif result.error_category == "BUSINESS_ERROR":
        _set_result(log, "FAILED_BUSINESS", "BUSINESS_ERROR", result.message)
    else:
        log.retry_count += 1
        _set_result(log, "FAILED_TECHNICAL", "TECHNICAL_ERROR", result.message)


def _dispatch(db: Session, log: IntegrationSyncLog, actor_id: uuid.UUID) -> None:
    if log.direction == "INBOUND":
        _dispatch_inbound(db, log, actor_id)
    else:
        _dispatch_outbound(log)


# ----------------------------------------------------------------------------- nghiệp vụ chính


class IntegrationService:
    """Service điều phối nhận và gửi dữ liệu với ERP, TMS."""

    @staticmethod
    def ingest_from_erp(
        db: Session,
        user: UserContext,
        doc_type: str,
        req: ErpPurchaseOrderPush | ErpAsnPush | ErpOutboundOrderPush,
    ) -> IngestResult:
        """Nhận PO, ASN hoặc đơn xuất từ ERP mock (chuẩn API 4.4)."""
        resolver = _CodeResolver(db)
        normalized = _NORMALIZERS[doc_type](resolver, req)
        warehouse_id = normalized.get("warehouse_id")
        log = IntegrationRepository.create_log(
            db,
            external_system="ERP",
            direction="INBOUND",
            doc_type=doc_type,
            warehouse_id=uuid.UUID(warehouse_id) if warehouse_id else None,
            business_payload={"erp": req.model_dump(mode="json"), "normalized": normalized},
        )

        if resolver.missing:
            _set_result(
                log,
                "FAILED_BUSINESS",
                "BUSINESS_ERROR",
                "Mã ERP không tồn tại trong danh mục WMS",
                {"missing_codes": resolver.missing},
            )
            return IngestResult(
                log=_serialize_log(log),
                http_status=422,
                error={
                    "code": "INTEGRATION_UNKNOWN_CODE",
                    "message": "Mã ERP không tồn tại trong danh mục WMS",
                    "details": {"sync_id": str(log.sync_id), "missing": resolver.missing},
                },
            )

        _dispatch_inbound(db, log, user.user_id)
        return _ingest_result(log)

    @staticmethod
    def receive_order_change(
        db: Session, user: UserContext, order_id: str, req: ErpOrderChangePush
    ) -> IngestResult:
        """ERP đổi hoặc hủy đơn xuất: gọi `fn_receive_erp_order_change`, ghi nhật ký."""
        try:
            order_uuid = uuid.UUID(order_id)
        except ValueError:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy đơn xuất", http_status=404
            ) from None

        payload = {**req.payload, "reason": req.reason}
        log = IntegrationRepository.create_log(
            db,
            external_system="ERP",
            direction="INBOUND",
            doc_type="SO",
            doc_id=order_uuid,
            business_payload={"change_type": req.change_type, "payload": payload},
            technical_meta={"kind": "ORDER_CHANGE"},
        )
        try:
            with db.begin_nested():
                decision = IntegrationRepository.receive_erp_order_change(
                    db, order_uuid, req.change_type, payload, user.user_id
                )
        except DBAPIError as exc:
            error = _order_change_error(exc)
            _set_result(log, "FAILED_BUSINESS", "BUSINESS_ERROR", error["message"])
            error["details"] = {"sync_id": str(log.sync_id)}
            return IngestResult(
                log=_serialize_log(log), http_status=error.pop("http_status"), error=error
            )

        log.warehouse_id = decision["warehouse_id"]
        _set_result(log, "SUCCESS", meta={"decision": decision})
        return IngestResult(
            log=_serialize_log(log), http_status=200, extra={"decision": _json_safe(decision)}
        )

    @staticmethod
    def list_logs(
        db: Session, user: UserContext, params: dict[str, str]
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        """Nhật ký đồng bộ; admin không xem được dữ liệu nghiệp vụ (`business_payload`)."""
        try:
            page = int(params.get("page", "1"))
            page_size = int(params.get("page_size", "20"))
        except ValueError:
            raise _validation("page và page_size phải là số nguyên") from None
        if page < 1 or not 1 <= page_size <= 100:
            raise _validation("page phải >= 1 và page_size trong khoảng 1 đến 100")

        conditions: list[ColumnElement[bool]] = []
        scope = _scope_warehouse(user)
        if scope is not None:
            conditions.append(IntegrationSyncLog.warehouse_id == scope)
        for name, value in params.items():
            if name in ("page", "page_size"):
                continue
            if name not in LIST_FILTERS:
                raise _validation(f"Không lọc được theo `{name}`", allowed=list(LIST_FILTERS))
            conditions.append(getattr(IntegrationSyncLog, name) == value.strip())

        logs, total = IntegrationRepository.list_logs(db, conditions, page, page_size)
        hide = user.role_code == "admin"
        return [_serialize_log(log, hide_payload=hide) for log in logs], total, page, page_size

    @staticmethod
    def process_pending(db: Session, user: UserContext, limit: int = 50) -> dict[str, int]:
        """Chạy hàng đợi: gửi chứng từ chờ, thử lại lỗi kỹ thuật, nhận lại chứng từ ERP chờ xử lý.

        Demo bấm tay (giống leo thang SLA); sau này gọi định kỳ bằng scheduler.
        """
        _require_operator(user)
        logs = IntegrationRepository.lock_processable(
            db,
            inbound_doc_types=sorted(_handlers),
            max_retries=MAX_RETRIES,
            limit=limit,
            warehouse_id=_scope_warehouse(user),
        )
        counts = {"processed": 0, "SUCCESS": 0, "FAILED_BUSINESS": 0, "FAILED_TECHNICAL": 0}
        for log in logs:
            _dispatch(db, log, user.user_id)
            counts["processed"] += 1
            if log.status in counts:
                counts[log.status] += 1
        db.flush()
        create_audit_log(
            db,
            action_code="INTEGRATION_PROCESS",
            entity_name="integration_sync_logs",
            actor_user_id=user.user_id,
            warehouse_id=user.warehouse_id,
            new_values=counts,
        )
        return counts

    @staticmethod
    def retry_log(db: Session, user: UserContext, sync_id: str) -> dict[str, Any]:
        """Thử lại một dòng lỗi hoặc đang chờ (ví dụ sau khi đã bổ sung danh mục)."""
        _require_operator(user)
        log = _load_log(db, user, sync_id)
        if log.status not in ("PENDING", "FAILED_TECHNICAL", "FAILED_BUSINESS"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Không thử lại được nhật ký ở trạng thái {log.status}",
                http_status=409,
            )
        old_status = log.status
        _dispatch(db, log, user.user_id)
        db.flush()
        create_audit_log(
            db,
            action_code="INTEGRATION_RETRY",
            entity_name="integration_sync_logs",
            actor_user_id=user.user_id,
            warehouse_id=log.warehouse_id,
            entity_id=log.sync_id,
            old_values={"status": old_status},
            new_values={"status": log.status},
        )
        return _serialize_log(log, hide_payload=user.role_code == "admin")

    @staticmethod
    def resolve_log(db: Session, user: UserContext, sync_id: str) -> dict[str, Any]:
        """Đánh dấu đã xử lý tay một dòng lỗi (không gửi lại)."""
        _require_operator(user)
        log = _load_log(db, user, sync_id)
        if log.status not in ("FAILED_TECHNICAL", "FAILED_BUSINESS"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Chỉ đánh dấu đã xử lý cho nhật ký lỗi (hiện: {log.status})",
                http_status=409,
            )
        old_status = log.status
        log.resolved_by = user.user_id
        _set_result(log, "RESOLVED", log.error_category, log.error_message)
        db.flush()
        create_audit_log(
            db,
            action_code="INTEGRATION_RESOLVE",
            entity_name="integration_sync_logs",
            actor_user_id=user.user_id,
            warehouse_id=log.warehouse_id,
            entity_id=log.sync_id,
            old_values={"status": old_status},
            new_values={"status": "RESOLVED"},
        )
        return _serialize_log(log, hide_payload=user.role_code == "admin")

    @staticmethod
    def configure_mock(user: UserContext, cfg: MockFailureConfig) -> dict[str, Any]:
        """Cấu hình lỗi giả lập cho ERP/TMS mock (chỉ ngoài môi trường production)."""
        if get_settings().ENV == "production":
            raise BusinessError(
                code="FORBIDDEN", message="Không dùng mock ở môi trường production", http_status=403
            )
        gateway = get_erp_gateway() if cfg.system == "ERP" else get_tms_gateway()
        gateway.configure_failures(cfg.error_category, cfg.times)
        return cfg.model_dump()


def _ingest_result(log: IntegrationSyncLog) -> IngestResult:
    data = _serialize_log(log)
    if log.status == "SUCCESS":
        return IngestResult(log=data, http_status=201)
    if log.status == "PENDING":
        return IngestResult(log=data, http_status=202)
    meta = log.technical_meta or {}
    if log.status == "FAILED_BUSINESS":
        return IngestResult(
            log=data,
            http_status=422,
            error={
                "code": meta.get("error_code", "INTEGRATION_REJECTED"),
                "message": log.error_message or "Chứng từ ERP bị từ chối",
                "details": {"sync_id": str(log.sync_id), **(meta.get("error_details") or {})},
            },
        )
    return IngestResult(
        log=data,
        http_status=503,
        error={
            "code": "INTEGRATION_TEMPORARY_ERROR",
            "message": "Lỗi tạm thời khi xử lý chứng từ, hệ thống sẽ thử lại",
            "details": {"sync_id": str(log.sync_id)},
        },
    )


def _order_change_error(exc: DBAPIError) -> dict[str, Any]:
    text_error = str(exc.orig)
    if "DON_KHONG_TON_TAI" in text_error:
        return {"code": "NOT_FOUND", "message": "Không tìm thấy đơn xuất", "http_status": 404}
    if "DA_CO_YEU_CAU_DANG_CHO" in text_error:
        return {
            "code": "INTEGRATION_CHANGE_PENDING",
            "message": "Đơn đã có yêu cầu đổi/hủy đang chờ Quản lý quyết định",
            "http_status": 409,
        }
    translated = translate_db_error(exc)
    return {
        "code": translated.code,
        "message": translated.message,
        "http_status": translated.http_status,
    }


def _validation(message: str, **details: Any) -> BusinessError:
    return BusinessError(code="VALIDATION_ERROR", message=message, http_status=422, details=details)


# ----------------------------------------------------------------------------- hàm công khai


def enqueue_to_erp(
    db: Session,
    warehouse_id: uuid.UUID,
    doc_type: str,
    doc_id: uuid.UUID | None,
    payload: dict[str, Any],
) -> uuid.UUID:
    """Hàm công khai: xếp một chứng từ chờ gửi ERP (GRN, GI, ADJUSTMENT, SCRAP...).

    Ghi trong cùng transaction với nghiệp vụ, nên chứng từ chỉ được gửi khi nghiệp vụ đã commit.
    Trả `sync_id`; việc gửi và thử lại do `process_pending` đảm nhận.
    """
    log = IntegrationRepository.create_log(
        db,
        external_system="ERP",
        direction="OUTBOUND",
        doc_type=doc_type,
        doc_id=doc_id,
        warehouse_id=warehouse_id,
        business_payload=_json_safe(payload),
    )
    return log.sync_id


def request_waybill(
    db: Session, warehouse_id: uuid.UUID, gi_id: uuid.UUID, payload: dict[str, Any]
) -> str | None:
    """Hàm công khai: xin vận đơn TMS cho phiếu xuất, gọi ngay.

    Trả số vận đơn; nếu TMS lỗi thì trả None (đơn để `WAITING_WAYBILL`), dòng nhật ký được thử
    lại bằng `process_pending` và lấy kết quả sau bằng `get_waybill`.
    """
    log = IntegrationRepository.create_log(
        db,
        external_system="TMS",
        direction="OUTBOUND",
        doc_type="WAYBILL",
        doc_id=gi_id,
        warehouse_id=warehouse_id,
        business_payload=_json_safe(payload),
    )
    _dispatch_outbound(log)
    db.flush()
    return _waybill_of(log)


def get_waybill(db: Session, gi_id: uuid.UUID) -> str | None:
    """Hàm công khai: số vận đơn đã cấp thành công cho phiếu xuất, hoặc None."""
    logs, _ = IntegrationRepository.list_logs(
        db,
        [
            IntegrationSyncLog.external_system == "TMS",
            IntegrationSyncLog.doc_type == "WAYBILL",
            IntegrationSyncLog.doc_id == gi_id,
            IntegrationSyncLog.status == "SUCCESS",
        ],
        page=1,
        page_size=1,
    )
    return _waybill_of(logs[0]) if logs else None


def _waybill_of(log: IntegrationSyncLog) -> str | None:
    if log.status != "SUCCESS":
        return None
    response = (log.technical_meta or {}).get("response") or {}
    waybill = response.get("waybill_number")
    return str(waybill) if waybill else None
