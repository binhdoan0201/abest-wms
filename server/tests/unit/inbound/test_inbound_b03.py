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


def test_get_grn_detail_can_recount_only_when_need_info_and_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from typing import cast

    from sqlalchemy.orm import Session

    from server.app.core.rbac import UserContext
    from server.app.modules.inbound.services import InboundService

    grn_id = uuid.uuid4()
    wh_id = uuid.uuid4()
    user_id = uuid.uuid4()
    fake_grn = SimpleNamespace(
        grn_id=grn_id,
        grn_number="GRN-TEST-001",
        po_id=uuid.uuid4(),
        asn_id=None,
        warehouse_id=wh_id,
        received_by=user_id,
        status="PENDING_D1",
        is_blind_receipt=False,
        recount_count=1,
        version_no=1,
        created_at=None,
        updated_at=None,
    )
    user = cast(
        UserContext,
        SimpleNamespace(
            user_id=user_id,
            username="nv_nhan",
            role_code="nv_nhan",
            primary_warehouse_id=wh_id,
            warehouse_ids=[wh_id],
            primary_stage=None,
            is_seasonal=False,
            is_safety_checked=True,
        ),
    )

    monkeypatch.setattr(inbound_services, "_require_warehouse", lambda _u: None)
    monkeypatch.setattr(inbound_services, "enforce_warehouse_scope", lambda _u, _w: None)
    monkeypatch.setattr(
        inbound_services.InboundRepository, "get_grn_by_id", lambda _db, _gid: fake_grn
    )
    monkeypatch.setattr(inbound_services.InboundRepository, "get_grn_lines", lambda _db, _gid: [])
    monkeypatch.setattr(inbound_services, "_grn_dict", lambda _g, _hb: {"grn_id": str(grn_id)})

    monkeypatch.setattr(
        inbound_services.InboundRepository, "list_recountable_grn_ids", lambda _db, _ids: set()
    )
    assert InboundService.get_grn_detail(cast(Session, None), user, grn_id)["can_recount"] is False

    monkeypatch.setattr(
        inbound_services.InboundRepository,
        "list_recountable_grn_ids",
        lambda _db, _ids: {grn_id},
    )
    assert InboundService.get_grn_detail(cast(Session, None), user, grn_id)["can_recount"] is True
