"""Kiểm tra đối chiếu OpenAPI sinh ra từ FastAPI với các hợp đồng docs/api/*.md.

Đảm bảo mọi endpoint đã cam kết trong tài liệu đặc tả và hợp đồng API
đều được khai báo và hiện diện đầy đủ trong OpenAPI schema.
"""

import re
from pathlib import Path

from server.app.main import app

DOCS_API_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "api"
RESOURCES = [
    "warehouses",
    "zones",
    "locations",
    "item-categories",
    "skus",
    "sku-barcodes",
    "suppliers",
    "customers",
    "reason-codes",
    "box-types",
    "users",
    "roles",
]


def test_all_doc_endpoints_present_in_openapi() -> None:
    """Xác nhận toàn bộ các endpoint trong docs/api/*.md đều được khai báo trong OpenAPI."""
    openapi = app.openapi()
    openapi_endpoints = set()

    for path, methods in openapi.get("paths", {}).items():
        for m in methods.keys():
            if m in ("get", "post", "put", "patch", "delete"):
                normalized_path = re.sub(r"\{[^}]+\}", "{id}", path)
                openapi_endpoints.add((m.upper(), normalized_path))

    doc_pattern = re.compile(r"###\s+\d*\.?\s*(GET|POST|PUT|PATCH|DELETE)\s+(/api/v1/[^\s\n]+)")
    doc_endpoints = set()

    for md_file in DOCS_API_DIR.glob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        for match in doc_pattern.finditer(content):
            method, path = match.groups()
            if "{resource}" in path:
                for resource in RESOURCES:
                    expanded = path.replace("{resource}", resource)
                    normalized = re.sub(r"\{[^}]+\}", "{id}", expanded)
                    doc_endpoints.add((method.upper(), normalized))
            else:
                normalized = re.sub(r"\{[^}]+\}", "{id}", path)
                doc_endpoints.add((method.upper(), normalized))

    missing_in_openapi = doc_endpoints - openapi_endpoints
    assert not missing_in_openapi, (
        f"Các endpoint có trong tài liệu docs/api/*.md nhưng chưa được khai báo "
        f"trong router FastAPI (OpenAPI): {missing_in_openapi}"
    )
