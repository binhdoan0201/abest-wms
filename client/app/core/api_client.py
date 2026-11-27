"""HTTP Client kết nối từ Web Client tới Backend Server API."""

from typing import Any

import httpx

from client.app.core.config import get_client_settings

settings = get_client_settings()


class ClientApiError(Exception):
    """Lỗi phản hồi từ Backend Server API."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{http_status}] {code}: {message}")
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


class ApiClient:
    """Lớp giao tiếp HTTP Client với Backend Server API theo chuẩn phong bì ABEST WMS."""

    backend_app: Any = None  # Cấu hình trong test để gọi trực tiếp in-memory backend

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.token = token
        effective_base = base_url if base_url is not None else get_client_settings().SERVER_API_URL
        self.base_url = effective_base.rstrip("/")
        self.timeout = timeout

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_client(self) -> Any:
        if self.backend_app is not None:
            from starlette.testclient import TestClient

            return TestClient(self.backend_app, base_url=self.base_url)
        return httpx.Client(timeout=self.timeout)

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            raw_payload = response.json()
            payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
        except Exception:
            payload = {}

        if response.status_code >= 400:
            error_data = payload.get("error", {})
            code = error_data.get("code", f"HTTP_{response.status_code}")
            message = error_data.get("message", response.text or "Lỗi giao tiếp máy chủ")
            details = error_data.get("details", {})
            raise ClientApiError(
                code=code,
                message=message,
                http_status=response.status_code,
                details=details,
            )

        return payload

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Gửi GET request tới Backend Server."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._get_client()
        try:
            resp = client.get(url, params=params, headers=self._get_headers())
            return self._handle_response(resp)
        finally:
            if hasattr(client, "close"):
                client.close()

    def post(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Gửi POST request tới Backend Server."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._get_client()
        try:
            resp = client.post(url, json=json_data, params=params, headers=self._get_headers())
            return self._handle_response(resp)
        finally:
            if hasattr(client, "close"):
                client.close()

    def put(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Gửi PUT request tới Backend Server."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._get_client()
        try:
            resp = client.put(url, json=json_data, params=params, headers=self._get_headers())
            return self._handle_response(resp)
        finally:
            if hasattr(client, "close"):
                client.close()

    def patch(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Gửi PATCH request tới Backend Server."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._get_client()
        try:
            resp = client.patch(url, json=json_data, params=params, headers=self._get_headers())
            return self._handle_response(resp)
        finally:
            if hasattr(client, "close"):
                client.close()

    def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Gửi DELETE request tới Backend Server."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._get_client()
        try:
            resp = client.delete(url, params=params, headers=self._get_headers())
            return self._handle_response(resp)
        finally:
            if hasattr(client, "close"):
                client.close()
