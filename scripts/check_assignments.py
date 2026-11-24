#!/usr/bin/env python3
"""
Kiểm tra tính nhất quán của bảng phân công công việc.
Đọc docs/spec/dac-ta-du-an.md, lấy các dòng bảng bắt đầu bằng «| <mã việc> |»,
và khẳng định mỗi mã việc (A-01 đến A-13, B-03 đến B-10, C-01 đến C-08, D-01 đến D-05, D-08)
xuất hiện đúng 1 lần trong docs/PHAN_CONG.md.
"""

import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = REPO_ROOT / "docs" / "spec" / "dac-ta-du-an.md"
PHAN_CONG_FILE = REPO_ROOT / "docs" / "PHAN_CONG.md"

EXPECTED_CODES = (
    {f"A-{i:02d}" for i in range(1, 14)}
    | {f"B-{i:02d}" for i in range(3, 11)}
    | {f"C-{i:02d}" for i in range(1, 9)}
    | {f"D-{i:02d}" for i in range(1, 6)}
    | {"D-08"}
)


def extract_task_codes(file_path: Path) -> list[str]:
    """Trích xuất danh sách mã công việc từ các dòng bắt đầu bằng | <mã việc> |."""
    if not file_path.is_file():
        print(f"LỖI: Không tìm thấy file {file_path}", file=sys.stderr)
        sys.exit(1)

    codes: list[str] = []
    task_pattern = re.compile(r"^\|\s*([A-D]-\d{2})\s*\|")

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = task_pattern.match(line)
            if match:
                codes.append(match.group(1))

    return codes


def main() -> int:
    print("Đang kiểm tra phân công công việc...")
    print(f"- File đặc tả: {SPEC_FILE}")
    print(f"- File phân công: {PHAN_CONG_FILE}")

    spec_codes = extract_task_codes(SPEC_FILE)
    print(f"-> Tìm thấy {len(spec_codes)} mã công việc trong {SPEC_FILE.name}.")

    spec_set = set(spec_codes)
    missing_in_spec = EXPECTED_CODES - spec_set
    extra_in_spec = spec_set - EXPECTED_CODES

    if missing_in_spec or extra_in_spec:
        print("LỖI: Đặc tả không khớp danh sách mã kỳ vọng!", file=sys.stderr)
        if missing_in_spec:
            print(f"  Thiếu trong spec: {sorted(missing_in_spec)}", file=sys.stderr)
        if extra_in_spec:
            print(f"  Thừa trong spec: {sorted(extra_in_spec)}", file=sys.stderr)
        return 1

    phan_cong_codes = extract_task_codes(PHAN_CONG_FILE)
    print(f"-> Tìm thấy {len(phan_cong_codes)} mã công việc trong {PHAN_CONG_FILE.name}.")

    counts = Counter(phan_cong_codes)
    errors: list[str] = []

    for code in sorted(EXPECTED_CODES):
        occurrences = counts.get(code, 0)
        if occurrences == 0:
            errors.append(f"Mã '{code}' KHÔNG xuất hiện trong {PHAN_CONG_FILE.name}")
        elif occurrences > 1:
            errors.append(
                f"Mã '{code}' xuất hiện {occurrences} lần trong "
                f"{PHAN_CONG_FILE.name} (kỳ vọng đúng 1 lần)"
            )

    extra_in_phan_cong = set(phan_cong_codes) - EXPECTED_CODES
    if extra_in_phan_cong:
        for code in sorted(extra_in_phan_cong):
            errors.append(f"Mã không hợp lệ '{code}' xuất hiện trong {PHAN_CONG_FILE.name}")

    if errors:
        print("LỖI KIỂM TRA PHÂN CÔNG:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(
        f"THÀNH CÔNG: Toàn bộ {len(EXPECTED_CODES)} mã việc xuất hiện đúng 1 lần "
        f"trong {PHAN_CONG_FILE.name}!"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
