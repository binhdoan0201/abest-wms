"""ABEST WMS - Pydantic Schemas cho Phân hệ Tồn kho (Inventory)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class BalanceItem(BaseModel):
    """Mục số dư tồn kho chi tiết."""

    model_config = ConfigDict(from_attributes=True)

    balance_id: uuid.UUID
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    sku_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    pallet_id: uuid.UUID | None = None
    serial_number: str | None = None
    qty_available: str
    qty_allocated: str
    qty_counting: str
    qty_locked: str
    qty_damaged: str
    version_no: int


class TransactionItem(BaseModel):
    """Bản ghi sổ cái giao dịch tồn kho."""

    model_config = ConfigDict(from_attributes=True)

    tx_id: uuid.UUID
    warehouse_id: uuid.UUID
    tx_type: str
    sku_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    pallet_id: uuid.UUID | None = None
    from_location_id: uuid.UUID | None = None
    to_location_id: uuid.UUID | None = None
    qty_change: str
    ref_doc_type: str
    ref_doc_id: uuid.UUID
    performed_by: uuid.UUID
    performed_at: datetime


class LotItem(BaseModel):
    """Thông tin lô hàng."""

    model_config = ConfigDict(from_attributes=True)

    lot_id: uuid.UUID
    sku_id: uuid.UUID
    lot_number: str
    manufacture_date: date | None = None
    expiry_date: date | None = None
    is_priority_dispatch: bool = False


class PalletItem(BaseModel):
    """Thông tin Pallet hàng."""

    model_config = ConfigDict(from_attributes=True)

    pallet_id: uuid.UUID
    pallet_code: str
    warehouse_id: uuid.UUID
    current_location_id: uuid.UUID | None = None
    status: str
    version_no: int


class LocationStockItem(BaseModel):
    """Tồn kho tại một vị trí."""

    location_id: uuid.UUID
    balances: list[BalanceItem]
