"""Unit tests B-03: hàm hỗ trợ của InboundService (không cần CSDL)."""

import uuid
from decimal import Decimal

import pytest

from server.app.core.exceptions import BusinessError
from server.app.modules.inbound import services as inbound_services
from server.app.modules.inbound.models import POLine


def test_fmt_qty_three_decimals() -> None:
    assert inbound_services._fmt_qty(Decimal("6")) == "6.000"
    assert inbound_services._fmt_qty(None) is None


def test_parse_sort_descending() -> None:
    result = inbound_services._parse_sort(
        "-created_at", inbound_services.PO_SORT_FIELDS, "-created_at"
    )
    assert result == ("created_at", True)


def test_parse_sort_rejects_unknown_field() -> None:
    with pytest.raises(BusinessError) as exc:
        inbound_services._parse_sort("po_id", inbound_services.PO_SORT_FIELDS, "-created_at")
    assert exc.value.code == "VALIDATION_ERROR"


def test_parse_paging_limits() -> None:
    assert inbound_services._parse_paging(1, 20) == (1, 20)
    with pytest.raises(BusinessError):
        inbound_services._parse_paging(0, 20)
    with pytest.raises(BusinessError):
        inbound_services._parse_paging(1, 101)


def test_po_line_hides_quantities_for_receiver() -> None:
    line = POLine(
        po_line_id=uuid.uuid4(),
        po_id=uuid.uuid4(),
        line_number=1,
        sku_id=uuid.uuid4(),
        uom_code="CTN",
        qty_ordered=Decimal("10"),
        qty_received=Decimal("0"),
        version_no=1,
    )
    hidden = inbound_services._po_line_dict(line, hide_qty=True)
    assert hidden["qty_ordered"] is None
    assert hidden["qty_received"] is None
    shown = inbound_services._po_line_dict(line, hide_qty=False)
    assert shown["qty_ordered"] == "10.000"
    assert shown["qty_received"] == "0.000"
