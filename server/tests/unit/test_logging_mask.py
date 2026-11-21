"""ABEST WMS - Kiểm thử Unit: Bộ lọc che giấu thông tin nhạy cảm trong Logging JSON.

Quy định:
- Tuyệt đối không ghi JWT, mật khẩu, header Authorization hay cookie vào log.
- Bộ lọc log phải che các trường authorization, password, token, cookie:
  ghi một log chứa các trường này và khẳng định đầu ra không lộ giá trị.
"""

import io
import json
import logging

from server.app.core.logging import JSONFormatter, SensitiveDataFilter
from server.app.core.responses import request_id_ctx


def test_logging_masks_sensitive_data_in_text_and_dict() -> None:
    """Khẳng định bộ lọc log che giấu hoàn toàn authorization, password, token, cookie."""
    # 1. Khởi tạo logger riêng cho bài test với stream thu thập dữ liệu
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())

    test_logger = logging.getLogger("test.security.logger")
    test_logger.setLevel(logging.INFO)
    test_logger.handlers = [handler]
    test_logger.propagate = False

    # Gắn request_id giả lập
    token = request_id_ctx.set("req-test-mask-1234")

    # Các giá trị nhạy cảm bí mật
    SECRET_PASSWORD = "P@ssword_Top_Secret_123"
    SECRET_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.SecretTokenContent"
    SECRET_AUTH = "Bearer SuperConfidentialBearerToken999"
    SECRET_COOKIE = "session_token=VerySecretCookieSessionId888"

    try:
        # 2. Ghi log dạng chuỗi chứa thông tin nhạy cảm
        test_logger.info(
            "User login attempt with password=%s and header %s",
            SECRET_PASSWORD,
            SECRET_AUTH,
        )

        test_logger.warning(
            "Client request with Cookie: %s and token=%s",
            SECRET_COOKIE,
            SECRET_TOKEN,
        )

        # 3. Ghi log dạng dict cấu trúc chứa các trường nhạy cảm
        test_logger.info(
            "Payload data payload: %s",
            {
                "username": "demo_user",
                "password": SECRET_PASSWORD,
                "token": SECRET_TOKEN,
                "authorization": SECRET_AUTH,
                "cookie": SECRET_COOKIE,
                "nested": {
                    "api_key": "some_key",
                    "secret": "DeepSecret123",
                },
            },
        )
    finally:
        request_id_ctx.reset(token)

    output = log_stream.getvalue()

    # 4. Khẳng định tuyệt đối KHÔNG lộ các giá trị thật ra đầu ra log
    assert SECRET_PASSWORD not in output, "Bị lộ mật khẩu trong log!"
    assert SECRET_TOKEN not in output, "Bị lộ JWT/token trong log!"
    assert "SuperConfidentialBearerToken999" not in output, "Bị lộ Bearer token trong log!"
    assert "VerySecretCookieSessionId888" not in output, "Bị lộ Cookie trong log!"
    assert "DeepSecret123" not in output, "Bị lộ nested secret trong log!"

    # 5. Khẳng định có ký tự che giấu '***'
    assert "***" in output

    # 6. Kiểm tra từng dòng là JSON hợp lệ có đủ các trường bắt buộc
    lines = [line.strip() for line in output.strip().split("\n") if line.strip()]
    assert len(lines) == 3

    for line in lines:
        parsed = json.loads(line)
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "message" in parsed
        assert "request_id" in parsed
        assert parsed["request_id"] == "req-test-mask-1234"
