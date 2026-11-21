#!/usr/bin/env python3
"""Script tự động sinh server/app/shared/enums.py từ PostgreSQL pg_enum.

Đảm bảo ENUM Python khớp 100% với ENUM của cơ sở dữ liệu.
Chạy lại được (Idempotent).
"""

import os
import sys
from collections import defaultdict
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "server" / "app" / "shared" / "enums.py"


def to_pascal_case(name: str) -> str:
    """Chuyển snake_case sang PascalCase cho tên class Enum."""
    parts = name.split("_")
    return "".join(p.capitalize() for p in parts)


def fetch_db_enums() -> dict[str, list[str]]:
    """Đọc toàn bộ ENUM từ cơ sở dữ liệu PostgreSQL."""
    load_dotenv(ROOT_DIR / ".env")

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_name = os.getenv("DB_NAME", "abest_wms")
    db_user = os.getenv("DB_USER", "wms_admin")
    db_password = os.getenv("DB_PASSWORD", "wms_secret_pass")

    conn_info = (
        f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"
    )

    query = """
        SELECT t.typname, e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        ORDER BY t.typname, e.enumsortorder;
    """

    enums_dict: dict[str, list[str]] = defaultdict(list)

    with psycopg.connect(conn_info) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            for typname, enumlabel in cur.fetchall():
                enums_dict[typname].append(enumlabel)

    return enums_dict


def generate_enums_code(enums_dict: dict[str, list[str]]) -> str:
    """Sinh mã nguồn Python cho file enums.py."""
    lines = [
        '"""ABEST WMS - ENUMs dùng chung, sinh tự động từ PostgreSQL pg_enum.',
        "",
        "DO NOT EDIT MANUALLY - Chạy `python scripts/gen_enums.py` để cập nhật.",
        '"""',
        "",
        "from enum import Enum",
        "",
        "",
    ]

    for typname in sorted(enums_dict.keys()):
        class_name = to_pascal_case(typname)
        labels = enums_dict[typname]

        lines.append(f"class {class_name}(str, Enum):")
        lines.append(f'    """PostgreSQL ENUM `{typname}`."""')
        lines.append("")
        for label in labels:
            lines.append(f'    {label} = "{label}"')
        lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    """Hàm thực thi chính."""
    print("=" * 60)
    print("ABEST WMS: Đang sinh server/app/shared/enums.py từ DB...")
    print("=" * 60)

    try:
        enums_dict = fetch_db_enums()
        print(f"Đã đọc được {len(enums_dict)} loại ENUM từ PostgreSQL:")
        for name, labels in sorted(enums_dict.items()):
            print(f"  - {name} ({len(labels)} giá trị)")

        code = generate_enums_code(enums_dict)
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(code, encoding="utf-8")

        print(f"\n[THÀNH CÔNG] Đã ghi file: {OUTPUT_FILE.relative_to(ROOT_DIR)}")
        return 0
    except Exception as exc:
        print(f"\n[LỖI] Không thể sinh enums: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
