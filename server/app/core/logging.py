"""ABEST WMS - Hệ thống Logging định dạng JSON và Bộ lọc che giấu dữ liệu nhạy cảm."""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from server.app.core.responses import get_current_request_id

# Các trường nhạy cảm cần được che giấu giá trị
SENSITIVE_KEYS = {
    "authorization",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "secret",
    "secret_key",
    "credentials",
}

# Regex tìm kiếm và thay thế thông tin nhạy cảm trong chuỗi văn bản đã format
MASK_PATTERNS = [
    # Authorization header / Bearer token
    (re.compile(r"(?i)(bearer\s+)[^\s,;\"']+"), r"\1***"),
    # Key-value dạng authorization=..., password: "...", 'token': '...'
    (
        re.compile(
            r"""(?i)(['"]?(?:authorization|password|token|access_token|refresh_token|cookie|secret|credentials)['"]?\s*[:=]\s*['"]?)[^'",;\s}\]]+(['"]?)"""
        ),
        r"\1***\2",
    ),
    # Cookie header
    (re.compile(r"(?i)(cookie\s*[:=]\s*)[^\r\n;]+"), r"\1***"),
]


def mask_sensitive_value(value: Any) -> Any:
    """Đệ quy quét và che giấu các giá trị nhạy cảm trong dict, list, tuple hoặc str."""
    if isinstance(value, dict):
        masked_dict: dict[str, Any] = {}
        for k, v in value.items():
            k_lower = str(k).lower().replace("-", "_")
            if any(sensitive in k_lower for sensitive in SENSITIVE_KEYS):
                masked_dict[k] = "***"
            else:
                masked_dict[k] = mask_sensitive_value(v)
        return masked_dict

    if isinstance(value, list):
        return [mask_sensitive_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(mask_sensitive_value(item) for item in value)

    if isinstance(value, str):
        masked_str = value
        for pattern, replacement in MASK_PATTERNS:
            masked_str = pattern.sub(replacement, masked_str)
        return masked_str

    return value


class SensitiveDataFilter(logging.Filter):
    """Logging filter che giấu dữ liệu nhạy cảm trong log record trước khi xuất."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Nếu có args, che giấu các đối số args mà không làm hỏng chuỗi định dạng %s
        if record.args:
            if isinstance(record.args, dict):
                record.args = mask_sensitive_value(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(mask_sensitive_value(arg) for arg in record.args)
        else:
            # Nếu không có args, có thể che giấu trực tiếp record.msg
            if isinstance(record.msg, (dict, list, tuple, str)):
                record.msg = mask_sensitive_value(record.msg)

        return True


class JSONFormatter(logging.Formatter):
    """Formatter xuất bản ghi log dưới dạng JSON cấu trúc với request_id."""

    def format(self, record: logging.LogRecord) -> str:
        # Chuẩn bị thời gian ISO 8601 UTC
        record_time = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        # Lấy request_id từ context hoặc record attribute
        req_id = getattr(record, "request_id", None) or get_current_request_id()

        # Format message chính và che giấu toàn diện
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)

        masked_message = mask_sensitive_value(message)

        log_data: dict[str, Any] = {
            "timestamp": record_time,
            "level": record.levelname,
            "logger": record.name,
            "message": masked_message,
            "request_id": req_id,
        }

        # Bổ sung exception info nếu có
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Che giấu dữ liệu nhạy cảm ở cấp toàn bộ log_data
        log_data = mask_sensitive_value(log_data)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """Cấu hình logging chuẩn JSON cho ứng dụng."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Tránh gắn handler trùng lặp
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())

    root_logger.addHandler(handler)
