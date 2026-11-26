"""ABEST WMS - Pydantic Schemas cho Phân hệ Dữ liệu nguồn (Master Data).

Mỗi danh mục có một schema tạo (`...Create`) và một schema sửa một phần (`...Update`).
Mọi schema cấm trường lạ (`extra="forbid"`), nên gửi `warehouse_id`, mã định danh khi sửa
hoặc cột chỉ đọc (`locations.status`) đều bị từ chối 422 theo hợp đồng `docs/api/master_data.md`.
"""

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.app.shared.enums import PickingRuleType, TaskType

ZoneTypeLiteral = Literal[
    "STORAGE",
    "RECEIVING_DOCK",
    "PACKING",
    "DAMAGED",
    "QUARANTINE",
    "STAGING",
    "COLD",
    "HAZMAT",
]
StorageRequirementLiteral = Literal["NORMAL", "COLD", "HAZMAT"]
ShelfLifeActionLiteral = Literal["WARN", "BLOCK"]
ReasonCategoryLiteral = Literal[
    "DAMAGED",
    "DISCREPANCY",
    "TASK_REJECT",
    "ORDER_CANCEL",
    "SCRAP",
    "OVERRIDE",
    "PACKING_EXCEPTION",
]


class _StrictModel(BaseModel):
    """Lớp cơ sở: cấm trường lạ và tự cắt khoảng trắng hai đầu chuỗi."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------- warehouses
class WarehouseCreate(_StrictModel):
    """Tạo kho."""

    erp_warehouse_code: str = Field(min_length=1, max_length=50)
    warehouse_name: str = Field(min_length=1, max_length=200)
    branch_code: str | None = Field(None, max_length=50)
    address: str | None = None


class WarehouseUpdate(_StrictModel):
    """Sửa kho (không đổi `erp_warehouse_code`)."""

    warehouse_name: str | None = Field(None, min_length=1, max_length=200)
    branch_code: str | None = Field(None, max_length=50)
    address: str | None = None


# --------------------------------------------------------------------------- zones
class ZoneCreate(_StrictModel):
    """Tạo khu vực trong kho của người dùng."""

    zone_code: str = Field(min_length=1, max_length=50)
    zone_name: str = Field(min_length=1, max_length=150)
    zone_type: ZoneTypeLiteral


class ZoneUpdate(_StrictModel):
    """Sửa khu vực (không đổi `zone_code`)."""

    zone_name: str | None = Field(None, min_length=1, max_length=150)
    zone_type: ZoneTypeLiteral | None = None


# --------------------------------------------------------------------------- locations
class LocationCreate(_StrictModel):
    """Tạo vị trí; `status` do inventory và cycle_count quản lý nên không nhận từ client."""

    zone_id: uuid.UUID
    location_code: str = Field(min_length=1, max_length=100)
    barcode: str = Field(min_length=1, max_length=100)
    aisle: str | None = Field(None, max_length=20)
    rack: str | None = Field(None, max_length=20)
    shelf_level: str | None = Field(None, max_length=20)
    bin: str | None = Field(None, max_length=20)
    max_weight_kg: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    max_volume_m3: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=4)
    max_pallets: int | None = Field(None, ge=0)


class LocationUpdate(_StrictModel):
    """Sửa vị trí (không đổi `location_code`)."""

    zone_id: uuid.UUID | None = None
    barcode: str | None = Field(None, min_length=1, max_length=100)
    aisle: str | None = Field(None, max_length=20)
    rack: str | None = Field(None, max_length=20)
    shelf_level: str | None = Field(None, max_length=20)
    bin: str | None = Field(None, max_length=20)
    max_weight_kg: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    max_volume_m3: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=4)
    max_pallets: int | None = Field(None, ge=0)


# --------------------------------------------------------------------------- item-categories
class ItemCategoryCreate(_StrictModel):
    """Tạo nhóm hàng."""

    category_code: str = Field(min_length=1, max_length=50)
    category_name: str = Field(min_length=1, max_length=150)
    min_receiving_shelf_life_days: int = Field(0, ge=0)
    shelf_life_violation_action: ShelfLifeActionLiteral = "WARN"


class ItemCategoryUpdate(_StrictModel):
    """Sửa nhóm hàng (không đổi `category_code`)."""

    category_name: str | None = Field(None, min_length=1, max_length=150)
    min_receiving_shelf_life_days: int | None = Field(None, ge=0)
    shelf_life_violation_action: ShelfLifeActionLiteral | None = None


# --------------------------------------------------------------------------- skus
class SkuCreate(_StrictModel):
    """Tạo SKU."""

    sku_code: str = Field(min_length=1, max_length=100)
    sku_name: str = Field(min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    base_uom: str = Field(min_length=1, max_length=30)
    unit_cost: Decimal = Field(Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    min_stock_level: Decimal = Field(Decimal("0"), ge=0, max_digits=18, decimal_places=3)
    is_lot_tracked: bool = True
    is_expiry_tracked: bool = True
    is_serial_tracked: bool = False
    storage_requirement: StorageRequirementLiteral = "NORMAL"
    unit_weight_kg: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=4)
    unit_volume_m3: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=6)


class SkuUpdate(_StrictModel):
    """Sửa SKU (không đổi `sku_code`)."""

    sku_name: str | None = Field(None, min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    base_uom: str | None = Field(None, min_length=1, max_length=30)
    unit_cost: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=4)
    min_stock_level: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=3)
    is_lot_tracked: bool | None = None
    is_expiry_tracked: bool | None = None
    is_serial_tracked: bool | None = None
    storage_requirement: StorageRequirementLiteral | None = None
    unit_weight_kg: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=4)
    unit_volume_m3: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=6)


# --------------------------------------------------------------------------- sku-barcodes
class SkuBarcodeCreate(_StrictModel):
    """Tạo mã vạch cho SKU."""

    sku_id: uuid.UUID
    barcode: str = Field(min_length=1, max_length=150)
    uom_code: str = Field(min_length=1, max_length=30)
    conversion_factor: Decimal = Field(Decimal("1"), gt=0, max_digits=12, decimal_places=4)


class SkuBarcodeUpdate(_StrictModel):
    """Sửa mã vạch (không đổi `sku_id`, `barcode`)."""

    uom_code: str | None = Field(None, min_length=1, max_length=30)
    conversion_factor: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=4)


# --------------------------------------------------------------------------- suppliers
class SupplierCreate(_StrictModel):
    """Tạo nhà cung cấp."""

    erp_supplier_code: str = Field(min_length=1, max_length=50)
    supplier_name: str = Field(min_length=1, max_length=255)
    contact_person: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)


class SupplierUpdate(_StrictModel):
    """Sửa nhà cung cấp (không đổi `erp_supplier_code`)."""

    supplier_name: str | None = Field(None, min_length=1, max_length=255)
    contact_person: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=150)


# --------------------------------------------------------------------------- customers
class CustomerCreate(_StrictModel):
    """Tạo khách hàng."""

    erp_customer_code: str = Field(min_length=1, max_length=50)
    customer_name: str = Field(min_length=1, max_length=255)
    shipping_address: str | None = None
    phone: str | None = Field(None, max_length=50)


class CustomerUpdate(_StrictModel):
    """Sửa khách hàng (không đổi `erp_customer_code`)."""

    customer_name: str | None = Field(None, min_length=1, max_length=255)
    shipping_address: str | None = None
    phone: str | None = Field(None, max_length=50)


# --------------------------------------------------------------------------- reason-codes
class ReasonCodeCreate(_StrictModel):
    """Tạo mã lý do."""

    reason_code: str = Field(min_length=1, max_length=50)
    reason_category: ReasonCategoryLiteral
    description: str = Field(min_length=1, max_length=255)


class ReasonCodeUpdate(_StrictModel):
    """Sửa mã lý do (không đổi `reason_code`)."""

    reason_category: ReasonCategoryLiteral | None = None
    description: str | None = Field(None, min_length=1, max_length=255)


# --------------------------------------------------------------------------- box-types
class BoxTypeCreate(_StrictModel):
    """Tạo loại thùng; `max_weight_kg` không được nhỏ hơn `tare_weight_kg`."""

    box_code: str = Field(min_length=1, max_length=50)
    box_name: str = Field(min_length=1, max_length=100)
    length_cm: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    width_cm: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    height_cm: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    tare_weight_kg: Decimal = Field(Decimal("0"), ge=0, max_digits=8, decimal_places=3)
    max_weight_kg: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)

    @model_validator(mode="after")
    def _check_weight(self) -> "BoxTypeCreate":
        if self.max_weight_kg is not None and self.max_weight_kg < self.tare_weight_kg:
            raise ValueError("max_weight_kg không được nhỏ hơn tare_weight_kg")
        return self


class BoxTypeUpdate(_StrictModel):
    """Sửa loại thùng (không đổi `box_code`); ràng buộc trọng lượng kiểm ở service."""

    box_name: str | None = Field(None, min_length=1, max_length=100)
    length_cm: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)
    width_cm: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)
    height_cm: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)
    tare_weight_kg: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=3)
    max_weight_kg: Decimal | None = Field(None, gt=0, max_digits=8, decimal_places=2)


# --------------------------------------------------------------------------- vehicles
class VehicleCreate(_StrictModel):
    """Tạo xe và tài xế (gán khi lập GI)."""

    license_plate: str = Field(min_length=1, max_length=30)
    vehicle_type: str | None = Field(None, max_length=50)
    driver_name: str = Field(min_length=1, max_length=150)
    driver_phone: str | None = Field(None, max_length=30)
    carrier_name: str | None = Field(None, max_length=150)


class VehicleUpdate(_StrictModel):
    """Sửa xe (không đổi `license_plate`)."""

    vehicle_type: str | None = Field(None, max_length=50)
    driver_name: str | None = Field(None, min_length=1, max_length=150)
    driver_phone: str | None = Field(None, max_length=30)
    carrier_name: str | None = Field(None, max_length=150)


# --------------------------------------------------------------------------- warehouse config
class ApprovalSlaHours(_StrictModel):
    """SLA duyệt (giờ) cho từng cấp D1, D2, D3."""

    D1: Decimal = Field(gt=0)
    D2: Decimal = Field(gt=0)
    D3: Decimal = Field(gt=0)


class WarehouseConfigUpdate(_StrictModel):
    """Sửa tham số vận hành kho; mọi trường tùy chọn và không nhận `null`."""

    threshold_x_d1_amount: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    threshold_y_d2_amount: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    tolerance_z_mode: Literal["AMOUNT_ONLY", "PERCENT_ONLY", "BOTH_AND"] | None = None
    tolerance_z_amount: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    tolerance_z_percent: Decimal | None = Field(None, ge=0, le=100, decimal_places=2)
    reauth_min_amount: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    picking_rule: PickingRuleType | None = None
    blind_receipt_policy: Literal["REJECT", "WARN_HOLD_D1"] | None = None
    missing_cert_policy: Literal["HARD_BLOCK", "SOFT_OVERRIDE"] | None = None
    counting_location_tx_policy: Literal["BLOCK", "QUEUE"] | None = None
    task_sla_minutes: dict[TaskType, int] | None = None
    approval_sla_hours: ApprovalSlaHours | None = None
    max_open_tasks_per_user: int | None = Field(None, gt=0)
    max_recount_attempts: int | None = Field(None, gt=0)
    dashboard_refresh_seconds: int | None = Field(None, gt=0)
    offline_task_reclaim_minutes: int | None = Field(None, gt=0)
    allow_same_counter_recount: bool | None = None
    grn_tolerance_apply: bool | None = None
    over_receipt_tolerance_pct: Decimal | None = Field(None, ge=0, le=100, decimal_places=2)

    @model_validator(mode="after")
    def _check_values(self) -> "WarehouseConfigUpdate":
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"Trường `{name}` không nhận giá trị null")
        if self.task_sla_minutes is not None:
            for task_type, minutes in self.task_sla_minutes.items():
                if minutes <= 0:
                    raise ValueError(f"task_sla_minutes.{task_type.value} phải lớn hơn 0")
        return self
