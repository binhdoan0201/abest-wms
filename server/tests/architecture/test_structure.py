"""Kiểm tra kiến trúc và cấu trúc thư mục dự án ABEST WMS."""

from scripts.check_structure import check_structure


def test_project_structure_completeness():
    """Kiểm tra toàn bộ thư mục và file bắt buộc của Mục 3 Đặc tả đều tồn tại."""
    missing_dirs, missing_files = check_structure()

    assert not missing_dirs, f"Thư mục còn thiếu: {missing_dirs}"
    assert not missing_files, f"File còn thiếu: {missing_files}"
