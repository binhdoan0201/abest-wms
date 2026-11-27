"""ABEST WMS - Xử lý ngoại lệ, mã lỗi chuẩn và dịch lỗi cơ sở dữ liệu."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from server.app.core.responses import error_response

logger = logging.getLogger("server.exceptions")


class BusinessError(Exception):
    """Lớp ngoại lệ nghiệp vụ chuẩn của hệ thống."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 400,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        super().__init__(message)


def translate_db_error(exc: Exception) -> BusinessError:
    """Dịch lỗi từ PostgreSQL/SQLAlchemy sang mã lỗi nghiệp vụ chuẩn theo Mục 3 Chuẩn API.

    Xử lý các tiền tố trigger và ràng buộc CSDL:
    - BAN_GHI_BAT_BIEN -> INTERNAL_IMMUTABLE_RECORD (HTTP 500)
    - DON_BI_DONG_BANG -> ORDER_FROZEN (HTTP 409)
    - THIEU_XAC_THUC_LAI -> REAUTH_REQUIRED (HTTP 403)
    - VI_PHAM_TACH_QUYEN_SOD / chk_sod_no_self_approval -> SOD_VIOLATION (HTTP 403)
    - qty_available -> INVENTORY_INSUFFICIENT_QTY (HTTP 409)
    """
    error_str = str(exc)

    if "BAN_GHI_BAT_BIEN" in error_str:
        return BusinessError(
            code="INTERNAL_IMMUTABLE_RECORD",
            message=(
                "Bản ghi bất biến: không cho phép chỉnh sửa hoặc xóa lịch sử sổ cái / audit log"
            ),
            http_status=500,
            details={"db_message": "BAN_GHI_BAT_BIEN"},
        )

    if "DON_BI_DONG_BANG" in error_str:
        return BusinessError(
            code="ORDER_FROZEN",
            message="Đơn hàng đang bị đóng băng do có yêu cầu đổi/hủy từ ERP đang chờ Quản lý chốt",
            http_status=409,
            details={"db_message": "DON_BI_DONG_BANG"},
        )

    if "THIEU_XAC_THUC_LAI" in error_str:
        return BusinessError(
            code="REAUTH_REQUIRED",
            message="Yêu cầu xác thực lại bằng mật khẩu hoặc sinh trắc học khi duyệt giá trị lớn",
            http_status=403,
            details={"db_message": "THIEU_XAC_THUC_LAI"},
        )

    if "VI_PHAM_TACH_QUYEN_SOD" in error_str or "chk_sod_no_self_approval" in error_str:
        return BusinessError(
            code="SOD_VIOLATION",
            message=(
                "Vi phạm nguyên tắc phân tách nhiệm vụ (SoD): "
                "Người lập không được phép tự duyệt phiếu của chính mình"
            ),
            http_status=403,
            details={"db_message": "SOD_VIOLATION"},
        )

    if "qty_available" in error_str or "TON_KHO_KHONG_TON_TAI" in error_str:
        return BusinessError(
            code="INVENTORY_INSUFFICIENT_QTY",
            message="Số lượng tồn khả dụng không đủ để thực hiện giao dịch",
            http_status=409,
            details={"db_message": "INVENTORY_INSUFFICIENT_QTY"},
        )

    if "XUNG_DOT_PHIEN_BAN" in error_str:
        return BusinessError(
            code="VERSION_CONFLICT",
            message="Dữ liệu đã bị cập nhật bởi thao tác khác (xung đột phiên bản)",
            http_status=409,
            details={"db_message": "VERSION_CONFLICT"},
        )

    return BusinessError(
        code="DATABASE_ERROR",
        message="Lỗi thao tác cơ sở dữ liệu",
        http_status=500,
        details={"error": "Lỗi CSDL không xác định"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Đăng ký các exception handler tập trung cho FastAPI app."""

    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=error_response(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Chuyển đổi định dạng lỗi pydantic thành JSON an toàn
        details = {"errors": [err.get("msg", str(err)) for err in exc.errors()]}
        return JSONResponse(
            status_code=422,
            content=error_response(
                code="VALIDATION_ERROR",
                message="Dữ liệu yêu cầu không hợp lệ hoặc thiếu trường bắt buộc",
                details=details,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=error_response(
                code="INTERNAL_SERVER_ERROR",
                message="Đã xảy ra lỗi nội bộ hệ thống, vui lòng thử lại sau",
                details={},
            ),
        )
