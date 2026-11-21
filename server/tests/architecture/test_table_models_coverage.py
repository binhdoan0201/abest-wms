"""Kiểm tra độ bao phủ mô hình ORM theo Mục 6.1 Đặc tả dự án.

Khẳng định toàn bộ 43 bảng CSDL thuộc 10 module theo Mục 6.1
được định nghĩa đầy đủ bằng SQLAlchemy 2.0 ORM models và đăng ký trong Base.metadata.tables.
"""

import importlib

from server.app.core.database import Base

SECTION_6_1_TABLES: dict[str, list[str]] = {
    "auth": ["users", "roles", "permissions", "role_permissions", "audit_logs"],
    "inventory": [
        "lots",
        "pallets",
        "inventory_balances",
        "inventory_transactions",
        "inventory_allocations",
    ],
    "tasks": ["tasks"],
    "master_data": [
        "warehouses",
        "warehouse_configs",
        "zones",
        "locations",
        "item_categories",
        "skus",
        "sku_barcodes",
        "suppliers",
        "customers",
        "reason_codes",
        "box_types",
    ],
    "inbound": [
        "purchase_orders",
        "po_lines",
        "asns",
        "grns",
        "grn_lines",
        "grn_count_attempts",
    ],
    "outbound": [
        "outbound_orders",
        "outbound_order_lines",
        "pick_sessions",
        "pick_lines",
        "packages",
        "goods_issues",
        "package_lines",
        "order_change_requests",
    ],
    "approvals": ["approval_requests", "approval_histories", "stock_adjustments"],
    "cycle_count": ["cycle_count_sheets", "cycle_count_lines", "cycle_count_attempts"],
    "integrations": ["integration_sync_logs"],
    "dashboard": [],  # Phân hệ chỉ đọc, 0 bảng CSDL riêng
}


def test_section_6_1_tables_coverage() -> None:
    """Xác nhận tất cả 43 bảng trong Mục 6.1 đều có ORM model tương ứng."""
    # Nạp toàn bộ models của 10 modules
    for module_name in SECTION_6_1_TABLES:
        importlib.import_module(f"server.app.modules.{module_name}.models")

    registered_tables = set(Base.metadata.tables.keys())

    all_expected_tables: list[str] = []
    for module_name, tables in SECTION_6_1_TABLES.items():
        for table in tables:
            all_expected_tables.append(table)
            assert table in registered_tables, (
                f"Bảng '{table}' của module '{module_name}' (Mục 6.1 đặc tả) "
                f"chưa được định nghĩa ORM model trong Base.metadata!"
            )

    # Đảm bảo tổng số bảng theo đúng cam kết là 43
    assert (
        len(all_expected_tables) == 43
    ), f"Kỳ vọng 43 bảng theo Mục 6.1, thực tế cấu hình: {len(all_expected_tables)}"
