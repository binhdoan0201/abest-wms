"""Bộ kiểm thử cho Web Client ABEST WMS (AG6).

Kiểm tra:
(a) Đăng nhập đúng và sai.
(b) Chưa đăng nhập vào /inventory thì bị chuyển sang /login.
(c) Test tham số hóa 9 vai trò: menu hiện đúng mục theo quyền.
(d) Lỗi API 403 và 409 hiện đúng thông báo trên giao diện.
(e) Mở /inventory bằng tài khoản được phép thấy dữ liệu seed.
(g) make ci xanh.
(h) POST có Origin lạ bị từ chối; POST HTMX thiếu header HX-Request bị từ chối;
    cookie phiên có HttpOnly và SameSite.
"""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import build_user_menu
from client.app.main import app as client_app
from server.app.main import app as backend_app


@pytest.fixture(autouse=True)
def setup_api_client_backend() -> Generator[None, None, None]:
    """Cấu hình ApiClient sử dụng in-memory backend_app trong quá trình test."""
    original_backend = ApiClient.backend_app
    ApiClient.backend_app = backend_app
    yield
    ApiClient.backend_app = original_backend


@pytest.fixture
def test_client() -> TestClient:
    """Tạo TestClient cho ứng dụng client web."""
    return TestClient(client_app, base_url="http://localhost:3000")


# ============================================================================
# (a) Đăng nhập đúng và sai
# ============================================================================
def test_client_login_success_and_failure(test_client: TestClient) -> None:
    """Kiểm tra luồng đăng nhập thành công và thất bại."""
    # 1. Đăng nhập thành công với tài khoản seed thukho / Demo@123456
    resp_success = test_client.post(
        "/login",
        data={"username": "thukho", "password": "Demo@123456"},
        follow_redirects=False,
    )
    assert resp_success.status_code == 303
    assert resp_success.headers.get("location") == "/inventory"
    cookie_header = resp_success.headers.get("set-cookie", "")
    assert "abest_session=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header or "samesite=lax" in cookie_header

    # 2. Đăng nhập thất bại: Sai mật khẩu
    resp_wrong_pass = test_client.post(
        "/login",
        data={"username": "thukho", "password": "WrongPassword@999"},
        follow_redirects=False,
    )
    assert resp_wrong_pass.status_code in {400, 401}
    assert (
        "AUTH_INVALID_CREDENTIALS" in resp_wrong_pass.text
        or "không chính xác" in resp_wrong_pass.text
    )

    # 3. Đăng nhập thất bại: Tài khoản không tồn tại
    resp_not_found = test_client.post(
        "/login",
        data={"username": "non_existent_user", "password": "Demo@123456"},
        follow_redirects=False,
    )
    assert resp_not_found.status_code in {400, 401}
    assert (
        "AUTH_INVALID_CREDENTIALS" in resp_not_found.text
        or "không chính xác" in resp_not_found.text
    )


# ============================================================================
# (b) Chưa đăng nhập vào /inventory thì bị chuyển sang /login
# ============================================================================
def test_unauthenticated_redirect_to_login(test_client: TestClient) -> None:
    """Kiểm tra khi chưa có cookie phiên đăng nhập thì bị chuyển hướng sang /login."""
    # Truy cập /inventory khi chưa đăng nhập
    resp_inv = test_client.get("/inventory", follow_redirects=False)
    assert resp_inv.status_code == 303
    assert resp_inv.headers.get("location") == "/login"

    # Truy cập trang gốc / khi chưa đăng nhập
    resp_root = test_client.get("/", follow_redirects=False)
    assert resp_root.status_code == 303
    assert resp_root.headers.get("location") == "/login"


# ============================================================================
# (c) Test tham số hóa 9 vai trò: menu hiện đúng mục theo quyền
# ============================================================================
@pytest.mark.parametrize(
    "username,expected_items,forbidden_items",
    [
        ("nv_nhan", ["Nhập kho", "Tồn kho", "Nhiệm vụ"], ["Kiểm kê", "Dữ liệu nguồn"]),
        ("nv_cat", ["Nhập kho", "Tồn kho", "Nhiệm vụ"], ["Kiểm kê", "Dữ liệu nguồn"]),
        ("nv_soan", ["Xuất kho", "Tồn kho", "Nhiệm vụ"], ["Kiểm kê", "Dữ liệu nguồn"]),
        ("nv_dongoi", ["Xuất kho", "Tồn kho", "Nhiệm vụ"], ["Kiểm kê", "Dữ liệu nguồn"]),
        (
            "nv_kiemke",
            ["Kiểm kê", "Nhiệm vụ"],
            ["Tồn kho", "Nhập kho", "Xuất kho", "Dữ liệu nguồn"],
        ),
        ("thukho", ["Nhập kho", "Xuất kho", "Tồn kho", "Nhiệm vụ", "Phê duyệt"], ["Dữ liệu nguồn"]),
        (
            "quanly",
            ["Tổng quan", "Nhập kho", "Xuất kho", "Tồn kho", "Nhiệm vụ", "Phê duyệt"],
            ["Dữ liệu nguồn"],
        ),
        ("bgd", ["Tổng quan", "Tồn kho", "Phê duyệt"], ["Dữ liệu nguồn", "Nhiệm vụ", "Kiểm kê"]),
        ("admin", ["Dữ liệu nguồn"], ["Tồn kho", "Nhập kho", "Xuất kho", "Nhiệm vụ", "Kiểm kê"]),
    ],
)
def test_parameterized_9_roles_menu_by_permission(
    test_client: TestClient,
    username: str,
    expected_items: list[str],
    forbidden_items: list[str],
) -> None:
    """Kiểm tra ma trận menu điều hướng cho cả 9 vai trò seed."""
    # 1. Đăng nhập để lấy cookie phiên
    login_resp = test_client.post(
        "/login",
        data={"username": username, "password": "Demo@123456"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303
    session_cookie = login_resp.cookies.get("abest_session")
    assert session_cookie is not None

    # 2. Lấy thông tin user profile từ /auth/me qua ApiClient
    api = ApiClient(token=session_cookie)
    me_resp = api.get("/auth/me")
    user_data = me_resp.get("data", {})

    # 3. Kiểm tra danh mục menu sinh ra từ build_user_menu
    menu = build_user_menu(user_data)
    menu_titles = [item["title"] for item in menu]

    for expected in expected_items:
        assert expected in menu_titles, f"Vai trò {username} phải thấy menu '{expected}'"

    for forbidden in forbidden_items:
        assert (
            forbidden not in menu_titles
        ), f"Vai trò {username} KHÔNG được thấy menu '{forbidden}'"


# ============================================================================
# (d) Lỗi API 403 và 409 hiện đúng thông báo trên giao diện
# ============================================================================
def test_client_ui_displays_403_and_409_errors(test_client: TestClient) -> None:
    """Kiểm tra giao diện xử lý và hiển thị thông báo lỗi 403 và 409 thân thiện."""
    # 1. Kiểm tra 403: Đăng nhập bằng nv_kiemke (không có quyền QL-1.1 xem tồn kho)
    login_kiemke = test_client.post(
        "/login",
        data={"username": "nv_kiemke", "password": "Demo@123456"},
        follow_redirects=False,
    )
    cookie_kiemke = login_kiemke.cookies.get("abest_session")

    resp_403 = test_client.get(
        "/inventory",
        cookies={"abest_session": cookie_kiemke or ""},
        follow_redirects=False,
    )
    assert resp_403.status_code == 403
    assert "403 - Không Đủ Quyền Truy Cập" in resp_403.text
    assert "FORBIDDEN" in resp_403.text

    # 2. Kiểm tra thông báo lỗi 409: Giả lập ClientApiError 409
    # Khi tầng view bắt lỗi 409 từ ApiClient, nó render index.html kèm banner thông báo lỗi
    login_thukho = test_client.post(
        "/login",
        data={"username": "thukho", "password": "Demo@123456"},
        follow_redirects=False,
    )
    cookie_thukho = login_thukho.cookies.get("abest_session")

    # Monkeypatch ApiClient.get để mô phỏng lỗi 409 INVENTORY_INSUFFICIENT_QTY
    def mock_get_409(self: ApiClient, path: str, params: Any = None) -> dict[str, Any]:
        if "balances" in path:
            raise ClientApiError(
                code="INVENTORY_INSUFFICIENT_QTY",
                message="Số lượng tồn khả dụng không đủ để thực hiện thao tác",
                http_status=409,
            )
        return original_get(self, path, params)

    original_get = ApiClient.get
    ApiClient.get = mock_get_409  # type: ignore[assignment]
    try:
        resp_409 = test_client.get(
            "/inventory",
            cookies={"abest_session": cookie_thukho or ""},
        )
        assert resp_409.status_code == 409
        assert "INVENTORY_INSUFFICIENT_QTY" in resp_409.text
        assert "không đủ" in resp_409.text
    finally:
        ApiClient.get = original_get  # type: ignore[assignment]


# ============================================================================
# (e) Mở /inventory bằng tài khoản được phép thấy dữ liệu seed
# ============================================================================
def test_inventory_page_displays_seed_data_for_authorized_role(test_client: TestClient) -> None:
    """Tài khoản có quyền QL-1.1 (thukho) mở /inventory thấy giao diện tồn kho và dữ liệu."""
    login_resp = test_client.post(
        "/login",
        data={"username": "thukho", "password": "Demo@123456"},
        follow_redirects=False,
    )
    cookie = login_resp.cookies.get("abest_session")
    assert cookie is not None

    resp = test_client.get(
        "/inventory",
        cookies={"abest_session": cookie},
    )
    assert resp.status_code == 200
    assert "Bảng Cân Đối Tồn Kho" in resp.text
    assert "Mã SKU" in resp.text
    assert "Vị trí" in resp.text
    assert "Khả dụng" in resp.text


# ============================================================================
# (h) POST có Origin lạ bị từ chối; POST HTMX thiếu header HX-Request bị từ chối;
#     cookie phiên có HttpOnly và SameSite
# ============================================================================
def test_csrf_and_security_headers(test_client: TestClient) -> None:
    """Kiểm tra CSRF Origin/Referer guard, HTMX header requirement và thuộc tính Cookie."""
    # 1. POST có Origin lạ bị từ chối 403
    resp_bad_origin = test_client.post(
        "/login",
        data={"username": "thukho", "password": "Demo@123456"},
        headers={"Origin": "https://malicious-attacker.com"},
    )
    assert resp_bad_origin.status_code == 403
    assert "CSRF_ORIGIN_MISMATCH" in resp_bad_origin.text

    # 2. POST có Referer lạ bị từ chối 403
    resp_bad_referer = test_client.post(
        "/login",
        data={"username": "thukho", "password": "Demo@123456"},
        headers={"Referer": "https://evil-phishing.org/login"},
    )
    assert resp_bad_referer.status_code == 403
    assert "CSRF_REFERER_MISMATCH" in resp_bad_referer.text

    # 3. Request HTMX thiếu header HX-Request: true bị từ chối 403
    # Gửi request tới endpoint HTMX /inventory/refresh nhưng không có HX-Request: true
    resp_bad_htmx = test_client.post(
        "/inventory/refresh",
        headers={"HX-Target": "table-container"},  # Chứa header hx- nhưng thiếu hx-request
    )
    assert resp_bad_htmx.status_code == 403
    assert "HTMX_HEADER_MISSING" in resp_bad_htmx.text

    # 4. Request HTMX có đầy đủ HX-Request: true được chấp nhận
    # Đăng nhập lấy cookie trước
    login_resp = test_client.post(
        "/login",
        data={"username": "thukho", "password": "Demo@123456"},
        headers={"Origin": "http://localhost:3000"},
        follow_redirects=False,
    )
    cookie = login_resp.cookies.get("abest_session")

    resp_good_htmx = test_client.post(
        "/inventory/refresh",
        headers={"HX-Request": "true", "Origin": "http://localhost:3000"},
        cookies={"abest_session": cookie or ""},
    )
    assert resp_good_htmx.status_code == 200
    assert "<table" in resp_good_htmx.text

    # 5. Cookie phiên có đầy đủ HttpOnly và SameSite
    cookie_header = login_resp.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header or "samesite=lax" in cookie_header
