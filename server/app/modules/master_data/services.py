"""ABEST WMS - Services cho Phân hệ Dữ liệu nguồn (Master Data).

Cách truy cập dữ liệu: qua `repositories.py` (truy vấn chung cho 10 danh mục).

Mỗi danh mục được mô tả bằng một `ResourceSpec` (khóa, phạm vi kho, cột tìm kiếm, cột lọc,
có `is_active` hay không). Năm thao tác chuẩn (danh sách, chi tiết, tạo, sửa, ngừng sử dụng)
dùng chung một cài đặt theo hợp đồng `docs/api/master_data.md`.
"""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import ColumnElement, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute, Session

from server.app.core.audit import create_audit_log
from server.app.core.exceptions import BusinessError, translate_db_error
from server.app.core.rbac import UserContext
from server.app.modules.inventory import has_stock
from server.app.modules.master_data.models import (
    BoxType,
    Customer,
    ItemCategory,
    Location,
    ReasonCode,
    Sku,
    SkuBarcode,
    Supplier,
    Warehouse,
    Zone,
)
from server.app.modules.master_data.repositories import MasterDataRepository
from server.app.modules.master_data.schemas import WarehouseConfigUpdate
from server.app.shared.enums import LocationStatusType

MAX_PAGE_SIZE = 100
LIST_RESERVED_PARAMS = {"page", "page_size", "sort", "q"}

# ----------------------------------------------------------------------------- bộ đọc tham số lọc


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False
    raise ValueError("phải là true hoặc false")


def _parse_uuid(raw: str) -> uuid.UUID:
    return uuid.UUID(raw.strip())


def _parse_text(raw: str) -> str:
    return raw.strip()


def _parse_choice(*choices: str) -> Callable[[str], str]:
    def parser(raw: str) -> str:
        value = raw.strip()
        if value not in choices:
            raise ValueError(f"chỉ nhận {', '.join(choices)}")
        return value

    return parser


ZONE_TYPES = (
    "STORAGE",
    "RECEIVING_DOCK",
    "PACKING",
    "DAMAGED",
    "QUARANTINE",
    "STAGING",
    "COLD",
    "HAZMAT",
)
REASON_CATEGORIES = (
    "DAMAGED",
    "DISCREPANCY",
    "TASK_REJECT",
    "ORDER_CANCEL",
    "SCRAP",
    "OVERRIDE",
    "PACKING_EXCEPTION",
)


@dataclass(frozen=True)
class ResourceSpec:
    """Mô tả một danh mục: bảng, khóa, phạm vi kho và cách lọc, tìm kiếm."""

    name: str
    label: str
    model: type[Any]
    pk: str
    pk_is_uuid: bool
    scope: str  # "global" | "warehouse" | "warehouses"
    code_column: str
    search: tuple[str, ...]
    filters: dict[str, Callable[[str], Any]] = field(default_factory=dict)
    has_is_active: bool = True


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    spec.name: spec
    for spec in (
        ResourceSpec(
            name="warehouses",
            label="kho",
            model=Warehouse,
            pk="warehouse_id",
            pk_is_uuid=True,
            scope="warehouses",
            code_column="erp_warehouse_code",
            search=("erp_warehouse_code", "warehouse_name"),
            filters={"is_active": _parse_bool},
        ),
        ResourceSpec(
            name="zones",
            label="khu vực",
            model=Zone,
            pk="zone_id",
            pk_is_uuid=True,
            scope="warehouse",
            code_column="zone_code",
            search=("zone_code", "zone_name"),
            filters={"zone_type": _parse_choice(*ZONE_TYPES), "is_active": _parse_bool},
        ),
        ResourceSpec(
            name="locations",
            label="vị trí",
            model=Location,
            pk="location_id",
            pk_is_uuid=True,
            scope="warehouse",
            code_column="location_code",
            search=("location_code", "barcode"),
            filters={
                "zone_id": _parse_uuid,
                "status": _parse_choice(*[s.value for s in LocationStatusType]),
                "is_active": _parse_bool,
            },
        ),
        ResourceSpec(
            name="item-categories",
            label="nhóm hàng",
            model=ItemCategory,
            pk="category_id",
            pk_is_uuid=True,
            scope="global",
            code_column="category_code",
            search=("category_code", "category_name"),
            filters={"shelf_life_violation_action": _parse_choice("WARN", "BLOCK")},
            has_is_active=False,
        ),
        ResourceSpec(
            name="skus",
            label="SKU",
            model=Sku,
            pk="sku_id",
            pk_is_uuid=True,
            scope="global",
            code_column="sku_code",
            search=("sku_code", "sku_name"),
            filters={
                "category_id": _parse_uuid,
                "storage_requirement": _parse_choice("NORMAL", "COLD", "HAZMAT"),
                "is_active": _parse_bool,
            },
        ),
        ResourceSpec(
            name="sku-barcodes",
            label="mã vạch SKU",
            model=SkuBarcode,
            pk="barcode_id",
            pk_is_uuid=True,
            scope="global",
            code_column="barcode",
            search=("barcode",),
            filters={"sku_id": _parse_uuid, "uom_code": _parse_text},
            has_is_active=False,
        ),
        ResourceSpec(
            name="suppliers",
            label="nhà cung cấp",
            model=Supplier,
            pk="supplier_id",
            pk_is_uuid=True,
            scope="global",
            code_column="erp_supplier_code",
            search=("erp_supplier_code", "supplier_name"),
            filters={"is_active": _parse_bool},
        ),
        ResourceSpec(
            name="customers",
            label="khách hàng",
            model=Customer,
            pk="customer_id",
            pk_is_uuid=True,
            scope="global",
            code_column="erp_customer_code",
            search=("erp_customer_code", "customer_name"),
            filters={"is_active": _parse_bool},
        ),
        ResourceSpec(
            name="reason-codes",
            label="mã lý do",
            model=ReasonCode,
            pk="reason_code",
            pk_is_uuid=False,
            scope="global",
            code_column="reason_code",
            search=("reason_code", "description"),
            filters={
                "reason_category": _parse_choice(*REASON_CATEGORIES),
                "is_active": _parse_bool,
            },
        ),
        ResourceSpec(
            name="box-types",
            label="loại thùng",
            model=BoxType,
            pk="box_type_id",
            pk_is_uuid=True,
            scope="global",
            code_column="box_code",
            search=("box_code", "box_name"),
            has_is_active=False,
        ),
    )
}

# ----------------------------------------------------------------------------- tiện ích chung


def _validation_error(message: str, **details: Any) -> BusinessError:
    return BusinessError(code="VALIDATION_ERROR", message=message, http_status=422, details=details)


def _not_found(label: str) -> BusinessError:
    return BusinessError(code="NOT_FOUND", message=f"Không tìm thấy {label}", http_status=404)


def _json_value(value: Any) -> Any:
    """Đổi giá trị cột sang kiểu JSON theo chuẩn API (NUMERIC, UUID dạng chuỗi)."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal | uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_value(v) for v in value]
    return value


def _serialize(obj: Any) -> dict[str, Any]:
    """Đọc mọi cột của bản ghi ORM thành dict JSON."""
    return {
        attr.key: _json_value(getattr(obj, attr.key)) for attr in inspect(obj).mapper.column_attrs
    }


def _raw_dict(obj: Any) -> dict[str, Any]:
    """Đọc mọi cột của bản ghi ORM, giữ nguyên kiểu Python (cho hàm công khai)."""
    result: dict[str, Any] = {}
    for attr in inspect(obj).mapper.column_attrs:
        value = getattr(obj, attr.key)
        result[attr.key] = value.value if isinstance(value, Enum) else value
    return result


def _column(spec: ResourceSpec, name: str) -> InstrumentedAttribute[Any]:
    column: InstrumentedAttribute[Any] = getattr(spec.model, name)
    return column


_UNIQUE_DETAIL = re.compile(r"Key \(([^)]+)\)=")


def _translate_integrity(exc: IntegrityError, spec_label: str) -> BusinessError:
    """Dịch lỗi ràng buộc CSDL: trùng mã -> 409, khóa ngoại -> 404, CHECK -> 422."""
    sqlstate = getattr(exc.orig, "sqlstate", None)
    if sqlstate == "23505":
        diag = getattr(exc.orig, "diag", None)
        detail = getattr(diag, "message_detail", None) or str(exc.orig)
        match = _UNIQUE_DETAIL.search(detail)
        fields = (
            [f.strip() for f in match.group(1).split(",") if f.strip() != "warehouse_id"]
            if match
            else []
        )
        return BusinessError(
            code="MASTER_DATA_DUPLICATE",
            message=f"Trùng mã {spec_label} đã tồn tại",
            http_status=409,
            details={"fields": fields},
        )
    if sqlstate == "23503":
        return BusinessError(
            code="NOT_FOUND",
            message="Bản ghi tham chiếu không tồn tại",
            http_status=404,
        )
    if sqlstate == "23514":
        return _validation_error("Giá trị vi phạm ràng buộc dữ liệu")
    return translate_db_error(exc)


def _require_warehouse(user: UserContext) -> uuid.UUID:
    if user.warehouse_id is None:
        raise BusinessError(
            code="FORBIDDEN",
            message="Tài khoản chưa được gán kho làm việc",
            http_status=403,
        )
    return user.warehouse_id


def _scope_conditions(spec: ResourceSpec, user: UserContext) -> list[ColumnElement[bool]]:
    """Điều kiện phạm vi kho theo loại danh mục."""
    if spec.scope == "warehouse":
        return [spec.model.warehouse_id == _require_warehouse(user)]
    if spec.scope == "warehouses" and user.role_code != "admin":
        return [Warehouse.warehouse_id == _require_warehouse(user)]
    return []


def _parse_pk(spec: ResourceSpec, raw_id: str) -> Any:
    if not spec.pk_is_uuid:
        return raw_id
    try:
        return uuid.UUID(raw_id)
    except ValueError:
        raise _not_found(spec.label) from None


def _get_spec(resource: str) -> ResourceSpec:
    spec = RESOURCE_SPECS.get(resource)
    if spec is None:
        raise BusinessError(
            code="NOT_FOUND", message=f"Không có danh mục `{resource}`", http_status=404
        )
    return spec


def _load(
    db: Session, spec: ResourceSpec, user: UserContext, raw_id: str, for_update: bool = False
) -> Any:
    obj = MasterDataRepository.get_by_pk(
        db,
        spec.model,
        _column(spec, spec.pk),
        _parse_pk(spec, raw_id),
        conditions=_scope_conditions(spec, user),
        for_update=for_update,
    )
    if obj is None:
        raise _not_found(spec.label)
    return obj


def _check_references(
    db: Session, spec: ResourceSpec, user: UserContext, data: dict[str, Any]
) -> None:
    """Kiểm tham chiếu sang bảng khác trước khi ghi để trả 404 rõ ràng."""
    if spec.name == "locations" and data.get("zone_id") is not None:
        if not MasterDataRepository.zone_exists(db, data["zone_id"], _require_warehouse(user)):
            raise _not_found("khu vực (zone_id) trong kho")
    if spec.name == "skus" and data.get("category_id") is not None:
        if not MasterDataRepository.category_exists(db, data["category_id"]):
            raise _not_found("nhóm hàng (category_id)")
    if spec.name == "sku-barcodes" and data.get("sku_id") is not None:
        if not MasterDataRepository.sku_exists(db, data["sku_id"]):
            raise _not_found("SKU (sku_id)")


def _audit(
    db: Session,
    action_code: str,
    spec_or_entity: str,
    user: UserContext,
    entity_id: Any,
    old_values: dict[str, Any] | None,
    new_values: dict[str, Any] | None,
) -> None:
    create_audit_log(
        db,
        action_code=action_code,
        entity_name=spec_or_entity,
        actor_user_id=user.user_id,
        warehouse_id=user.warehouse_id,
        entity_id=entity_id if isinstance(entity_id, uuid.UUID) else None,
        old_values=old_values,
        new_values=new_values,
    )


def _table_name(spec: ResourceSpec) -> str:
    table_name: str = spec.model.__tablename__
    return table_name


# ----------------------------------------------------------------------------- nghiệp vụ chính


class MasterDataService:
    """Service điều phối nghiệp vụ danh mục nguồn."""

    @staticmethod
    def list_items(
        db: Session,
        user: UserContext,
        resource: str,
        params: dict[str, str],
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        """Danh sách có phân trang, sắp xếp, tìm kiếm, lọc; trả (items, total, page, page_size)."""
        spec = _get_spec(resource)

        try:
            page = int(params.get("page", "1"))
            page_size = int(params.get("page_size", "20"))
        except ValueError:
            raise _validation_error("page và page_size phải là số nguyên") from None
        if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
            raise _validation_error(
                f"page phải >= 1 và page_size trong khoảng 1 đến {MAX_PAGE_SIZE}"
            )

        conditions = _scope_conditions(spec, user)
        for name, raw in params.items():
            if name in LIST_RESERVED_PARAMS:
                continue
            parser = spec.filters.get(name)
            if parser is None:
                raise _validation_error(
                    f"Không lọc được theo `{name}`", allowed=sorted(spec.filters)
                )
            try:
                value = parser(raw)
            except ValueError as exc:
                raise _validation_error(f"Giá trị lọc `{name}` không hợp lệ: {exc}") from None
            conditions.append(_column(spec, name) == value)

        sort = params.get("sort") or spec.code_column
        descending = sort.startswith("-")
        sort_name = sort.lstrip("-")
        allowed_sort = {spec.pk, spec.code_column, *spec.search, *spec.filters}
        if sort_name not in allowed_sort:
            raise _validation_error(
                f"Không sắp xếp được theo `{sort_name}`", allowed=sorted(allowed_sort)
            )
        sort_column = _column(spec, sort_name)
        order_by = sort_column.desc() if descending else sort_column.asc()

        q = (params.get("q") or "").strip() or None
        items, total = MasterDataRepository.list_items(
            db,
            spec.model,
            conditions,
            [_column(spec, c) for c in spec.search],
            q,
            order_by,
            page,
            page_size,
        )
        return [_serialize(i) for i in items], total, page, page_size

    @staticmethod
    def get_item(db: Session, user: UserContext, resource: str, item_id: str) -> dict[str, Any]:
        """Chi tiết một bản ghi trong phạm vi của người dùng."""
        spec = _get_spec(resource)
        return _serialize(_load(db, spec, user, item_id))

    @staticmethod
    def create_item(
        db: Session, user: UserContext, resource: str, req: BaseModel
    ) -> dict[str, Any]:
        """Tạo bản ghi; tạo kho thì tạo kèm cấu hình mặc định."""
        spec = _get_spec(resource)
        data = req.model_dump()
        if spec.scope == "warehouse":
            data["warehouse_id"] = _require_warehouse(user)
        _check_references(db, spec, user, data)

        obj = spec.model(**data)
        try:
            MasterDataRepository.add(db, obj)
            if spec.name == "warehouses":
                MasterDataRepository.create_default_config(db, obj.warehouse_id)
        except IntegrityError as exc:
            raise _translate_integrity(exc, spec.label) from exc
        db.refresh(obj)

        result = _serialize(obj)
        _audit(
            db,
            "MASTER_DATA_CREATE",
            _table_name(spec),
            user,
            getattr(obj, spec.pk),
            None,
            result,
        )
        return result

    @staticmethod
    def update_item(
        db: Session, user: UserContext, resource: str, item_id: str, req: BaseModel
    ) -> dict[str, Any]:
        """Sửa một phần: chỉ trường gửi lên mới đổi."""
        spec = _get_spec(resource)
        data = req.model_dump(exclude_unset=True)
        if not data:
            raise _validation_error("Không có trường nào để cập nhật")

        columns = spec.model.__table__.columns
        for name, value in data.items():
            if value is None and not columns[name].nullable:
                raise _validation_error(f"Trường `{name}` không nhận giá trị null")

        obj = _load(db, spec, user, item_id, for_update=True)
        _check_references(db, spec, user, data)

        if spec.name == "box-types":
            tare = data.get("tare_weight_kg", obj.tare_weight_kg)
            max_weight = data.get("max_weight_kg", obj.max_weight_kg)
            if max_weight is not None and max_weight < tare:
                raise _validation_error("max_weight_kg không được nhỏ hơn tare_weight_kg")

        old_values = {name: _json_value(getattr(obj, name)) for name in data}
        for name, value in data.items():
            setattr(obj, name, value)
        try:
            MasterDataRepository.flush(db)
        except IntegrityError as exc:
            raise _translate_integrity(exc, spec.label) from exc
        db.refresh(obj)

        result = _serialize(obj)
        _audit(
            db,
            "MASTER_DATA_UPDATE",
            _table_name(spec),
            user,
            getattr(obj, spec.pk),
            old_values,
            {name: result[name] for name in data},
        )
        return result

    @staticmethod
    def deactivate_item(
        db: Session, user: UserContext, resource: str, item_id: str
    ) -> dict[str, Any]:
        """Ngừng sử dụng bản ghi (is_active = false) sau khi kiểm tra không còn được dùng."""
        spec = _get_spec(resource)
        if not spec.has_is_active:
            raise BusinessError(
                code="MASTER_DATA_NOT_DEACTIVATABLE",
                message=f"Danh mục {spec.label} không hỗ trợ ngừng sử dụng",
                http_status=409,
            )

        obj = _load(db, spec, user, item_id, for_update=True)
        if not obj.is_active:
            raise BusinessError(
                code="INVALID_STATE",
                message=f"{spec.label.capitalize()} đã ngừng sử dụng từ trước",
                http_status=409,
            )

        in_use_reason = _in_use_reason(db, spec, user, obj)
        if in_use_reason:
            raise BusinessError(
                code="MASTER_DATA_IN_USE",
                message=in_use_reason,
                http_status=409,
            )

        obj.is_active = False
        MasterDataRepository.flush(db)
        db.refresh(obj)

        _audit(
            db,
            "MASTER_DATA_DEACTIVATE",
            _table_name(spec),
            user,
            getattr(obj, spec.pk),
            {"is_active": True},
            {"is_active": False, spec.code_column: getattr(obj, spec.code_column)},
        )
        return _serialize(obj)

    # ------------------------------------------------------------------------- cấu hình kho

    @staticmethod
    def get_config(db: Session, user: UserContext, warehouse_id: str) -> dict[str, Any]:
        """Đọc cấu hình kho: vai trò thường chỉ kho của mình, admin xem mọi kho."""
        config = _load_config(db, user, warehouse_id, for_update=False)
        return _serialize(config)

    @staticmethod
    def update_config(
        db: Session, user: UserContext, warehouse_id: str, req: WarehouseConfigUpdate
    ) -> dict[str, Any]:
        """Sửa tham số vận hành kho, kiểm ngưỡng D1 không vượt ngưỡng D2."""
        data = req.model_dump(exclude_unset=True, mode="json")
        if not data:
            raise _validation_error("Không có trường nào để cập nhật")

        config = _load_config(db, user, warehouse_id, for_update=True)
        for name in (
            "threshold_x_d1_amount",
            "threshold_y_d2_amount",
            "tolerance_z_amount",
            "tolerance_z_percent",
            "reauth_min_amount",
            "over_receipt_tolerance_pct",
        ):
            if name in data:
                data[name] = Decimal(str(data[name]))
        if "approval_sla_hours" in data:
            data["approval_sla_hours"] = {
                tier: _number(Decimal(str(hours)))
                for tier, hours in data["approval_sla_hours"].items()
            }

        threshold_x = data.get("threshold_x_d1_amount", config.threshold_x_d1_amount)
        threshold_y = data.get("threshold_y_d2_amount", config.threshold_y_d2_amount)
        if threshold_x > threshold_y:
            raise BusinessError(
                code="MASTER_DATA_INVALID_THRESHOLD",
                message="Ngưỡng duyệt D1 (X) không được lớn hơn ngưỡng D2 (Y)",
                http_status=422,
                details={
                    "threshold_x_d1_amount": str(threshold_x),
                    "threshold_y_d2_amount": str(threshold_y),
                },
            )

        old_values = {name: _json_value(getattr(config, name)) for name in data}
        for name, value in data.items():
            setattr(config, name, value)
        config.updated_by = user.user_id
        config.updated_at = datetime.now(timezone.utc)
        MasterDataRepository.flush(db)
        db.refresh(config)

        result = _serialize(config)
        _audit(
            db,
            "WAREHOUSE_CONFIG_UPDATE",
            "warehouse_configs",
            user,
            config.config_id,
            old_values,
            {name: result[name] for name in data},
        )
        return result


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _in_use_reason(db: Session, spec: ResourceSpec, user: UserContext, obj: Any) -> str | None:
    """Lý do không cho ngừng sử dụng, hoặc None nếu được phép."""
    if spec.name == "warehouses":
        if user.warehouse_id == obj.warehouse_id:
            return "Không thể ngừng sử dụng kho bạn đang làm việc"
        if has_stock(db, warehouse_id=obj.warehouse_id):
            return "Kho còn tồn, không thể ngừng sử dụng"
    if spec.name == "zones" and MasterDataRepository.count_active_locations_in_zone(
        db, obj.zone_id
    ):
        return "Khu vực còn vị trí đang hoạt động, không thể ngừng sử dụng"
    if spec.name == "locations" and has_stock(db, location_id=obj.location_id):
        return "Vị trí còn tồn, không thể ngừng sử dụng"
    if spec.name == "skus" and has_stock(db, sku_id=obj.sku_id):
        return "SKU còn tồn, không thể ngừng sử dụng"
    return None


def _load_config(db: Session, user: UserContext, raw_id: str, for_update: bool) -> Any:
    try:
        warehouse_id = uuid.UUID(raw_id)
    except ValueError:
        raise _not_found("cấu hình kho") from None
    if user.role_code != "admin" and user.warehouse_id != warehouse_id:
        raise _not_found("cấu hình kho")
    config = MasterDataRepository.get_config(db, warehouse_id, for_update=for_update)
    if config is None:
        raise _not_found("cấu hình kho")
    return config


# ----------------------------------------------------------------------------- hàm công khai


def get_warehouse_config(db: Session, warehouse_id: uuid.UUID) -> dict[str, Any]:
    """Hàm công khai: toàn bộ cấu hình kho (NUMERIC giữ kiểu Decimal) cho module khác."""
    config = MasterDataRepository.get_config(db, warehouse_id)
    if config is None:
        raise _not_found("cấu hình kho")
    return _raw_dict(config)


def get_sku(db: Session, sku_id: uuid.UUID) -> dict[str, Any]:
    """Hàm công khai: thông tin SKU (gồm `unit_cost`, cờ theo dõi lô, hạn dùng, serial)."""
    sku = MasterDataRepository.get_by_pk(db, Sku, Sku.sku_id, sku_id)
    if sku is None:
        raise _not_found("SKU")
    return _raw_dict(sku)


def convert_to_base_uom(db: Session, sku_id: uuid.UUID, uom_code: str, qty: Decimal) -> Decimal:
    """Hàm công khai: quy đổi số lượng theo `uom_code` về đơn vị cơ sở `skus.base_uom`.

    Quy tắc chuẩn API mục 2.3: tồn kho, sổ cái, cấp phát và so lệch luôn theo `base_uom`.
    Hệ số lấy từ `sku_barcodes.conversion_factor` (1 đơn vị `uom_code` = hệ số x `base_uom`).
    Ném `NOT_FOUND` nếu không có SKU; `MASTER_DATA_UOM_NOT_CONVERTIBLE` (422) nếu đơn vị chưa
    có mã vạch quy đổi hoặc có nhiều hệ số mâu thuẫn.
    """
    sku = MasterDataRepository.get_by_pk(db, Sku, Sku.sku_id, sku_id)
    if sku is None:
        raise _not_found("SKU")
    code = uom_code.strip()
    if code == sku.base_uom:
        return qty

    factors = MasterDataRepository.get_conversion_factors(db, sku_id, code)
    if len(factors) != 1:
        reason = "chưa có mã vạch quy đổi" if not factors else "có nhiều hệ số khác nhau"
        raise BusinessError(
            code="MASTER_DATA_UOM_NOT_CONVERTIBLE",
            message=f"Không quy đổi được đơn vị `{code}` về `{sku.base_uom}`: {reason}",
            http_status=422,
            details={
                "sku_id": str(sku_id),
                "uom_code": code,
                "base_uom": sku.base_uom,
                "factors": [str(f) for f in factors],
            },
        )
    factor: Decimal = factors[0]
    return qty * factor


def get_location(db: Session, location_id: uuid.UUID, warehouse_id: uuid.UUID) -> dict[str, Any]:
    """Hàm công khai: thông tin vị trí thuộc kho chỉ định."""
    location = MasterDataRepository.get_by_pk(
        db,
        Location,
        Location.location_id,
        location_id,
        conditions=[Location.warehouse_id == warehouse_id],
    )
    if location is None:
        raise _not_found("vị trí")
    return _raw_dict(location)
