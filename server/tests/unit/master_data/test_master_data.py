"""Unit tests cho hàm công khai của module master_data và inventory.has_stock."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from server.app.core.database import SessionLocal
from server.app.core.exceptions import BusinessError
from server.app.modules.inventory import has_stock
from server.app.modules.master_data import (
    convert_to_base_uom,
    get_location,
    get_sku,
    get_warehouse_config,
)


def test_public_read_functions_return_raw_types() -> None:
    db = SessionLocal()
    try:
        row = db.execute(text("SELECT warehouse_id, location_id FROM locations LIMIT 1")).one()
        warehouse_id, location_id = row[0], row[1]
        sku_id = db.execute(text("SELECT sku_id FROM skus LIMIT 1")).scalar_one()

        config = get_warehouse_config(db, warehouse_id)
        assert isinstance(config["threshold_x_d1_amount"], Decimal)
        assert isinstance(config["task_sla_minutes"], dict)
        assert config["picking_rule"] in ("FEFO", "FIFO")

        sku = get_sku(db, sku_id)
        assert isinstance(sku["unit_cost"], Decimal)
        assert "is_lot_tracked" in sku

        location = get_location(db, location_id, warehouse_id)
        assert location["location_id"] == location_id
        assert isinstance(location["status"], str)

        with pytest.raises(BusinessError) as exc:
            get_location(db, location_id, uuid.uuid4())
        assert exc.value.code == "NOT_FOUND"

        with pytest.raises(BusinessError):
            get_sku(db, uuid.uuid4())
        with pytest.raises(BusinessError):
            get_warehouse_config(db, uuid.uuid4())
    finally:
        db.close()


def test_has_stock_filters() -> None:
    db = SessionLocal()
    try:
        assert has_stock(db, warehouse_id=uuid.uuid4()) is False
        assert has_stock(db, location_id=uuid.uuid4()) is False
        assert has_stock(db, sku_id=uuid.uuid4()) is False

        stocked = db.execute(
            text(
                "SELECT location_id, sku_id FROM inventory_balances "
                "WHERE qty_available <> 0 OR qty_allocated <> 0 OR qty_counting <> 0 "
                "OR qty_locked <> 0 OR qty_damaged <> 0 LIMIT 1"
            )
        ).first()
        if stocked is not None:
            assert has_stock(db, location_id=stocked[0]) is True
            assert has_stock(db, sku_id=stocked[1]) is True
    finally:
        db.close()


def test_convert_to_base_uom_uses_barcode_factor() -> None:
    """SKU-FOOD-001 có base_uom BOX và mã vạch thùng CTN = 12 BOX (seed 04)."""
    db = SessionLocal()
    try:
        sku_id = db.execute(
            text("SELECT sku_id FROM skus WHERE sku_code = 'SKU-FOOD-001'")
        ).scalar_one()

        assert convert_to_base_uom(db, sku_id, "CTN", Decimal("3")) == Decimal("36")
        assert convert_to_base_uom(db, sku_id, "BOX", Decimal("5")) == Decimal("5")

        with pytest.raises(BusinessError) as exc:
            convert_to_base_uom(db, sku_id, "PALLET", Decimal("1"))
        assert exc.value.code == "MASTER_DATA_UOM_NOT_CONVERTIBLE"
        assert exc.value.http_status == 422

        with pytest.raises(BusinessError) as exc:
            convert_to_base_uom(db, uuid.uuid4(), "BOX", Decimal("1"))
        assert exc.value.code == "NOT_FOUND"
    finally:
        db.close()
