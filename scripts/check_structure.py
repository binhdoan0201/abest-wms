#!/usr/bin/env python3
"""Script kiểm tra cấu trúc thư mục và các file bắt buộc của dự án ABEST WMS.

Tuân thủ Mục 3 của docs/spec/dac-ta-du-an.md và yêu cầu bước AG1.
"""

import sys
from pathlib import Path

# Thư mục gốc của repository
ROOT_DIR = Path(__file__).resolve().parent.parent

# Danh sách các thư mục bắt buộc theo Mục 3 Đặc tả
REQUIRED_DIRS = [
    ".github",
    ".github/workflows",
    "docs/spec",
    "docs/source",
    "docs/adr",
    "docs/api",
    "docs/reports",
    "database",
    "database/migrations",
    "database/seeds",
    "database/tests",
    "server/app/core",
    "server/app/shared",
    "server/app/modules/auth",
    "server/app/modules/master_data",
    "server/app/modules/inventory",
    "server/app/modules/inbound",
    "server/app/modules/outbound",
    "server/app/modules/tasks",
    "server/app/modules/approvals",
    "server/app/modules/cycle_count",
    "server/app/modules/dashboard",
    "server/app/integrations",
    "server/tests/unit",
    "server/tests/integration",
    "server/tests/e2e",
    "server/tests/architecture",
    "client/app/core",
    "client/app/static",
    "client/app/templates/_base",
    "client/app/modules",
    "scripts",
]

# Danh sách các file bắt buộc theo Mục 3 và bước AG1
REQUIRED_FILES = [
    "README.md",
    "CONTRIBUTING.md",
    ".env.example",
    ".gitignore",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "Makefile",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "database/schema.sql",
    "database/patch_v4_2_1.sql",
    "database/tests/smoke_test.sql",
    "server/requirements.txt",
    "client/requirements.txt",
    "server/app/main.py",
    "client/app/main.py",
    "scripts/check_structure.py",
]


def check_structure() -> tuple[list[str], list[str]]:
    """Kiểm tra sự tồn tại của thư mục và file bắt buộc."""
    missing_dirs: list[str] = []
    missing_files: list[str] = []

    for rel_dir in REQUIRED_DIRS:
        dir_path = ROOT_DIR / rel_dir
        if not dir_path.is_dir():
            missing_dirs.append(rel_dir)

    for rel_file in REQUIRED_FILES:
        file_path = ROOT_DIR / rel_file
        if not file_path.is_file():
            missing_files.append(rel_file)

    return missing_dirs, missing_files


def main() -> int:
    """Hàm thực thi chính."""
    print("=" * 60)
    print("ABEST WMS: Kiểm tra cấu trúc thư mục & file theo Mục 3 Đặc tả")
    print("=" * 60)

    missing_dirs, missing_files = check_structure()

    has_error = False

    if missing_dirs:
        has_error = True
        print("\n[LỖI] Các thư mục bắt buộc còn THIẾU:")
        for d in missing_dirs:
            print(f"  - [DIR]  {d}")

    if missing_files:
        has_error = True
        print("\n[LỖI] Các file bắt buộc còn THIẾU:")
        for f in missing_files:
            print(f"  - [FILE] {f}")

    if not has_error:
        print("\n[THÀNH CÔNG] Tất cả thư mục và file bắt buộc của Mục 3 đều TỒN TẠI!")
        print(f"  - Đã kiểm tra: {len(REQUIRED_DIRS)} thư mục.")
        print(f"  - Đã kiểm tra: {len(REQUIRED_FILES)} file bắt buộc.")
        print("=" * 60)
        return 0

    print("\n" + "=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
