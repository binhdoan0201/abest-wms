"""ABEST WMS - Pydantic Schemas cho Phân hệ Dữ liệu nguồn (Master Data)."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MasterDataResourceItem(BaseModel):
    """Schema đại diện cho một bản ghi danh mục nguồn."""

    id: uuid.UUID | str
    code: str
    name: str
    is_active: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class CreateResourceRequest(BaseModel):
    """Dữ liệu tạo mới danh mục nguồn."""

    code: str
    name: str
    extra: dict[str, Any] = Field(default_factory=dict)


class UpdateResourceRequest(BaseModel):
    """Dữ liệu cập nhật danh mục nguồn."""

    name: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
