"""Test định dạng số kiểu Việt Nam trên client (C3, tổng duyệt 28/11)."""

from decimal import Decimal

import pytest

from client.app.core.formatting import format_qty, format_qty_input, format_vnd


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("180.000", "180"),
        ("6.000", "6"),
        ("0.000", "0"),
        ("-3.000", "-3"),
        ("1234.500", "1.234,5"),
        ("2.125", "2,125"),
        (Decimal("1000000"), "1.000.000"),
        (37, "37"),
        (None, ""),
        ("abc", "abc"),
    ],
)
def test_format_qty(raw: object, expected: str) -> None:
    assert format_qty(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("8.000", "8"), ("2.500", "2.5"), ("1234.000", "1234"), ("0.000", "0"), (None, "")],
)
def test_format_qty_input_stays_parseable(raw: object, expected: str) -> None:
    assert format_qty_input(raw) == expected


def test_format_vnd() -> None:
    assert format_vnd("450000.00") == "450.000 ₫"
    assert format_vnd("1350000.00") == "1.350.000 ₫"
    assert format_vnd(None) == ""


def test_format_vn_datetime_and_labels() -> None:
    from client.app.core.formatting import format_vn_datetime, vi_label

    assert format_vn_datetime("2026-11-28T05:40:26.565178Z") == "28/11/2026 12:40"
    assert format_vn_datetime("2026-11-28T01:41:04+00:00") == "28/11/2026 08:41"
    assert format_vn_datetime(None) == ""
    assert format_vn_datetime("không phải ngày") == "không phải ngày"
    assert vi_label("GRN_DISCREPANCY") == "Chênh lệch nhận hàng"
    assert vi_label("REQUEST_RECOUNT") == "Yêu cầu đếm lại"
    assert vi_label("MA_LA") == "MA_LA"


def test_vi_label_scoped_contexts() -> None:
    from client.app.core.formatting import vi_label

    assert vi_label("PENDING", "PO") == "Chờ nhận hàng"
    assert vi_label("CLOSED", "GRN") == "Đã hoàn tất"
    assert vi_label("APPROVED", "GRN") == "Đã duyệt"
    assert vi_label("OPEN", "CC") == "Đang mở"
    assert vi_label("PENDING", "CC") == "Chờ đếm"
