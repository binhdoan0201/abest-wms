"""Kiểm tra tuân thủ phân tầng kiến trúc (Layering Architecture AST Tests).

Tuân thủ Mục 7.2 của Đặc tả Chuẩn API Công nghệ:
1. routers.py chỉ import services, schemas, core (KHÔNG BAO GIỜ import sqlalchemy hoặc models).
2. services.py chỉ import nội bộ module của mình và các module khác thông qua __init__.
3. Lời gọi hàm DB `fn_*` chỉ xuất hiện trong `repositories.py` (và chỉ module `inventory`
   được gọi `fn_apply_inventory_movement` và `fn_transfer_inventory`).
"""

import ast
import re
from pathlib import Path

MODULES_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "modules"


def get_all_module_dirs() -> list[Path]:
    """Lấy danh sách thư mục các module trong server/app/modules."""
    return [d for d in MODULES_DIR.iterdir() if d.is_dir() and not d.name.startswith("__")]


def test_routers_do_not_import_sqlalchemy_or_models() -> None:
    """Quy tắc 1: routers.py không import sqlalchemy hoặc models."""
    for mod_dir in get_all_module_dirs():
        routers_file = mod_dir / "routers.py"
        if not routers_file.exists():
            continue

        tree = ast.parse(routers_file.read_text(encoding="utf-8"), filename=str(routers_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "sqlalchemy" not in alias.name, (
                        f"Vi phạm kiến trúc: {routers_file.name} trong module {mod_dir.name} "
                        f"import trực tiếp '{alias.name}'. Routers không được import sqlalchemy."
                    )
                    assert "models" not in alias.name, (
                        f"Vi phạm kiến trúc: {routers_file.name} trong module {mod_dir.name} "
                        f"import '{alias.name}'. Routers không được import models."
                    )
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                assert "sqlalchemy" not in module_name, (
                    f"Vi phạm kiến trúc: {routers_file.name} trong module {mod_dir.name} "
                    f"import từ '{module_name}'. Routers không được import sqlalchemy."
                )
                assert "models" not in module_name, (
                    f"Vi phạm kiến trúc: {routers_file.name} trong module {mod_dir.name} "
                    f"import từ '{module_name}'. Routers không được import models."
                )


def test_services_only_import_cross_module_via_init() -> None:
    """Quy tắc 2: services.py chỉ import module khác thông qua __init__."""
    for mod_dir in get_all_module_dirs():
        services_file = mod_dir / "services.py"
        if not services_file.exists():
            continue

        tree = ast.parse(services_file.read_text(encoding="utf-8"), filename=str(services_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if "server.app.modules." in module_name:
                    parts = module_name.split(".")
                    # server.app.modules.<target_module>.<submodule>
                    if len(parts) >= 4:
                        target_mod = parts[3]
                        if target_mod != mod_dir.name:
                            # Không được import sâu vào models, repositories của module khác
                            assert len(parts) == 4, (
                                f"Vi phạm kiến trúc: {services_file} import sâu vào "
                                f"'{module_name}'. Giao tiếp chéo module bắt buộc qua __init__."
                            )


def test_fn_database_calls_only_in_repositories() -> None:
    """Quy tắc 3: Lời gọi hàm DB fn_* chỉ xuất hiện trong repositories.py.

    Đặc biệt, fn_apply_inventory_movement và fn_transfer_inventory chỉ thuộc inventory.
    """
    fn_pattern = re.compile(r"\bfn_[a-zA-Z0-9_]+\b")

    for mod_dir in get_all_module_dirs():
        for py_file in mod_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    matches = fn_pattern.findall(node.value)
                    if matches and ("SELECT" in node.value.upper() or "FROM" in node.value.upper()):
                        assert py_file.name == "repositories.py", (
                            f"Vi phạm kiến trúc: Lời gọi hàm DB SQL {matches} xuất hiện "
                            f"trong file {py_file.name} (chỉ được phép trong repositories.py)."
                        )
                        for fn_name in matches:
                            if fn_name in (
                                "fn_apply_inventory_movement",
                                "fn_transfer_inventory",
                            ):
                                assert mod_dir.name == "inventory", (
                                    f"Vi phạm kiến trúc: {fn_name} chỉ được phép gọi bởi "
                                    f"module inventory, phát hiện tại {py_file}."
                                )
