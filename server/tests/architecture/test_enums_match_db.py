"""ABEST WMS - Kiểm thử kiến trúc: Đối chiếu ENUM Python với PostgreSQL pg_enum.

Quy định:
- ENUM Python trong server/app/shared/enums.py phải khớp 100% với pg_enum trong DB.
- Lệch tên, lệch số lượng giá trị hoặc lệch nhãn đều phải fail.
"""

import inspect
from collections import defaultdict
from enum import Enum

import pytest
from sqlalchemy import text

from server.app.core.database import engine
from server.app.shared import enums as shared_enums


def to_pascal_case(name: str) -> str:
    """Chuyển snake_case sang PascalCase."""
    parts = name.split("_")
    return "".join(p.capitalize() for p in parts)


@pytest.mark.architecture
def test_enums_match_db_strictly() -> None:
    """Khẳng định mọi ENUM trong database có class tương ứng trong enums.py với đầy đủ giá trị."""
    # 1. Đọc ENUM thực tế từ pg_enum trong CSDL
    query = text(
        """
        SELECT t.typname, e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        ORDER BY t.typname, e.enumsortorder;
        """
    )

    db_enums: dict[str, list[str]] = defaultdict(list)
    with engine.connect() as conn:
        result = conn.execute(query)
        for typname, enumlabel in result:
            db_enums[typname].append(enumlabel)

    assert len(db_enums) > 0, "Không tìm thấy ENUM nào trong cơ sở dữ liệu PostgreSQL"

    # 2. Lấy danh sách các Enum class trong server.app.shared.enums
    python_enum_classes: dict[str, type[Enum]] = {
        name: obj
        for name, obj in inspect.getmembers(shared_enums, inspect.isclass)
        if issubclass(obj, Enum) and obj is not Enum
    }

    # 3. So khớp từng ENUM từ DB với Python
    for db_typname, db_labels in db_enums.items():
        expected_class_name = to_pascal_case(db_typname)
        assert expected_class_name in python_enum_classes, (
            f"Thiếu class Enum `{expected_class_name}` trong server.app.shared.enums "
            f"cho kiểu DB `{db_typname}`"
        )

        enum_cls = python_enum_classes[expected_class_name]
        py_values = [member.value for member in enum_cls]

        assert len(py_values) == len(db_labels), (
            f"Enum `{expected_class_name}` lệch số lượng giá trị: "
            f"Python có {len(py_values)} ({py_values}), DB có {len(db_labels)} ({db_labels})"
        )

        assert py_values == db_labels, (
            f"Enum `{expected_class_name}` lệch nhãn hoặc thứ tự: "
            f"Python={py_values} != DB={db_labels}"
        )

    # 4. Kiểm tra chiều ngược lại: Không có Enum thừa trong Python
    assert len(python_enum_classes) == len(db_enums), (
        f"Số lượng Enum trong Python ({len(python_enum_classes)}) "
        f"lệch với số lượng ENUM trong DB ({len(db_enums)})"
    )
