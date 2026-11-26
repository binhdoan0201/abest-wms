"""Bảo vệ xác thực, phân quyền và điều hướng cho Web Client."""

from typing import Any

from fastapi import Request

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.session import get_session_token


class NeedAuthException(Exception):
    """Ngoại lệ phát sinh khi người dùng chưa đăng nhập hoặc token không hợp lệ."""


def get_current_user(request: Request) -> dict[str, Any]:
    """Dependency trích xuất và xác thực thông tin người dùng từ Backend qua cookie phiên."""
    token = get_session_token(request)
    if not token:
        raise NeedAuthException()

    try:
        api = ApiClient(token=token)
        response = api.get("/auth/me")
        user_data = response.get("data", {})
        if not isinstance(user_data, dict) or not user_data:
            raise NeedAuthException()
        return user_data
    except ClientApiError as exc:
        if exc.http_status == 401:
            raise NeedAuthException() from exc
        raise


def get_optional_user(request: Request) -> dict[str, Any] | None:
    """Dependency lấy thông tin người dùng nếu đã đăng nhập; trả về None nếu chưa."""
    token = get_session_token(request)
    if not token:
        return None
    try:
        api = ApiClient(token=token)
        response = api.get("/auth/me")
        return response.get("data")
    except Exception:
        return None


# Trang đầu sau đăng nhập: BGĐ vào bảng điều hành (A-13), vai trò khác vào tra cứu tồn.
HOME_BY_ROLE: dict[str, str] = {"bgd": "/dashboard", "admin": "/master-data"}
DEFAULT_HOME = "/inventory"


def has_permission(user: dict[str, Any], code: str) -> bool:
    """Người dùng có mã quyền `code` (danh sách quyền trả về từ `/auth/me`)."""
    for p in user.get("permissions", []):
        value = p.get("permission_code") if isinstance(p, dict) else p
        if value == code:
            return True
    return False


def home_path(user: dict[str, Any] | None) -> str:
    """Đường dẫn trang đầu theo vai trò."""
    role_code = (user or {}).get("role_code", "")
    return HOME_BY_ROLE.get(role_code, DEFAULT_HOME)


# Định nghĩa danh mục menu toàn hệ thống
NAV_ITEMS: list[dict[str, Any]] = [
    {
        "id": "dashboard",
        "title": "Tổng quan",
        "path": "/dashboard",
        "permission": "QL-8.1",
        "alt_permission": "BC-1",
        "icon": "chart-pie",
    },
    {
        "id": "inventory",
        "title": "Tồn kho",
        "path": "/inventory",
        "permission": "QL-1.1",
        "icon": "cube",
    },
    {
        "id": "inbound",
        "title": "Nhập kho",
        "path": "/inbound",
        "permission": "NH-1",
        "alt_permission": "CAT-1",
        "icon": "arrow-down-tray",
    },
    {
        "id": "outbound",
        "title": "Xuất kho",
        "path": "/outbound",
        "permission": "SO-1",
        "alt_permission": "DG-1",
        "icon": "arrow-up-tray",
    },
    {
        "id": "tasks",
        "title": "Nhiệm vụ",
        "path": "/tasks",
        "permission": None,  # Hiển thị cho các vai trò vận hành kho
        "exclude_roles": ["admin", "bgd"],
        "icon": "clipboard-document-list",
    },
    {
        "id": "cycle_count",
        "title": "Kiểm kê",
        "path": "/cycle-count",
        "permission": "KK-1",
        "icon": "calculator",
    },
    {
        "id": "approvals",
        "title": "Phê duyệt",
        "path": "/approvals",
        "permission": "TK-3.2",
        "alt_permission": "DY-1",
        "icon": "check-badge",
    },
    {
        "id": "master_data",
        "title": "Dữ liệu nguồn",
        "path": "/master-data",
        "permission": "AD-1",
        "icon": "cog-6-tooth",
    },
]


def build_user_menu(user: dict[str, Any]) -> list[dict[str, Any]]:
    """Xây dựng danh sách menu điều hướng hiển thị phù hợp với quyền hạn của người dùng."""
    role_code = user.get("role_code", "")
    raw_perms = user.get("permissions", [])

    # Trích xuất tập hợp các mã quyền
    perm_codes: set[str] = set()
    for p in raw_perms:
        if isinstance(p, dict):
            code = p.get("permission_code") or p.get("code") or ""
            if code:
                perm_codes.add(code)
        elif isinstance(p, str):
            perm_codes.add(p)

    visible_menu: list[dict[str, Any]] = []

    for item in NAV_ITEMS:
        # Kiểm tra loại trừ theo role
        if "exclude_roles" in item and role_code in item["exclude_roles"]:
            continue

        req_perm = item.get("permission")
        alt_perm = item.get("alt_permission")

        # Nếu không yêu cầu quyền cụ thể (None)
        if req_perm is None:
            visible_menu.append(item)
            continue

        # Nếu có quyền chính hoặc quyền phụ
        if req_perm in perm_codes or (alt_perm and alt_perm in perm_codes):
            visible_menu.append(item)

    return visible_menu
