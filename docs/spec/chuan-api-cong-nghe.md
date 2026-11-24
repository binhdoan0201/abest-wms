# Chuẩn công nghệ và hợp đồng API cho ABEST WMS

Nov 13, 2026 · @binh

Tài liệu này chốt công nghệ và quy ước API để 4 người cùng code theo một chuẩn. Danh mục endpoint ở mục 4 là bản đầu tiên; chủ từng module hoàn thiện request/response trong `docs/api/<module>.md` theo mẫu ở mục 5 và gửi PR để module liên quan duyệt.

## 1. Công nghệ chốt

| Hạng mục | Quyết định | Lý do | Không dùng trong 15 ngày |
| --- | --- | --- | --- |
| Ngôn ngữ | Python 3.11 trở lên | Yêu cầu của nhóm |  |
| Server | FastAPI + Uvicorn | Tự sinh OpenAPI, kiểm dữ liệu bằng Pydantic v2, dễ chia module | Django (ORM lệch với schema có sẵn) |
| Truy cập DB | SQLAlchemy 2.x, driver psycopg 3 | Vừa ORM vừa gọi được hàm `fn_*` của DB bằng `text("SELECT fn_...")` |  |
| CSDL | PostgreSQL 15 trở lên (đã kiểm thử trên 16) | Schema v4.1 + patch v4.2.1 dùng ENUM, trigger, hàm PL/pgSQL | SQLite, MySQL |
| Nạp schema | `psql`: schema v4.1, patch v4.2.1, seed; Alembic chỉ cho thay đổi sau đó | ENUM thêm giá trị không chạy trong transaction của migration |  |
| Xác thực | JWT một token, hạn 8 giờ (một ca), mật khẩu bcrypt | Đủ cho demo, bỏ refresh token | SSO, OAuth |
| Client | Ứng dụng web chạy riêng: FastAPI + Jinja2 + HTMX + Tailwind (CDN), gọi server bằng `httpx` | Cùng ngôn ngữ, dựng nhanh, chạy trên điện thoại hoặc máy PDA bằng trình duyệt | React/Vue SPA, app native |
| Phiên đăng nhập phía client | Token lưu trong cookie `httpOnly` của client; trình duyệt không bao giờ cầm token | Tránh lộ token ra JavaScript |  |
| Quét mã | Máy quét kiểu bàn phím hoặc nhập tay | Không cần phần cứng thật | Quét bằng camera |
| Kiểm thử | `pytest`, `httpx.TestClient`, DB test trong Docker, cộng `wms_smoke_test_v4_2_1.sql` | Đã có bộ kiểm thử DB |  |
| Chất lượng code | `ruff`, `black`, `mypy`, `pre-commit` | Đồng nhất code của 4 người |  |
| Môi trường | `docker-compose` (Postgres), `.env` | Mọi người chạy giống nhau | Kubernetes |
| Việc nền | Không có tiến trình riêng: leo thang SLA gọi bằng endpoint `POST /approvals/escalate-expired` (bấm tay trong demo) | Bớt một thành phần phải dựng | Redis, Celery, message queue |

## 2. Quy ước chung của API

1. Tiền tố `/api/v1`. Tên đường dẫn `kebab-case`, danh từ số nhiều; hành động ngoài CRUD là `POST /{id}/<động-từ>`.
2. JSON dùng `snake_case`. Mã định danh là UUID dạng chuỗi.
3. **Số lượng và tiền (NUMERIC) trả và nhận dạng chuỗi**, ví dụ `"6.000"`, để không mất chính xác. Thời gian theo ISO 8601 UTC, ví dụ `"2026-11-13T08:30:00Z"`.
   - **Đơn vị tính**: tồn kho, sổ cái, cấp phát và so lệch luôn tính theo đơn vị cơ sở `skus.base_uom`. Chứng từ có `uom_code` khác (dòng PO, dòng GRN) phải quy đổi bằng `master_data.convert_to_base_uom` trước khi gọi `apply_movement` hoặc so với số dự kiến; đơn vị chưa có hệ số quy đổi trả 422 `MASTER_DATA_UOM_NOT_CONVERTIBLE`.
4. Xác thực bằng header `Authorization: Bearer <token>`. Token chứa `sub` (user\_id), `role_code`, `warehouse_id`. **Client không gửi `warehouse_id`**: server lấy từ token và lọc mọi truy vấn theo kho.
5. Phản hồi thành công: `{"data": ..., "meta": {"request_id": "..."}}`. Danh sách thêm `meta.page`, `meta.page_size`, `meta.total`.
6. Phản hồi lỗi: `{"error": {"code": "MÃ_LỖI", "message": "tiếng Việt", "details": {}}}`.
7. Phân trang bằng `?page=1&page_size=20` (tối đa 100); sắp xếp `?sort=-created_at`; lọc bằng tham số cùng tên trường (`?status=PENDING_D1`).
8. **Khóa đồng thời**: đối tượng có `version_no` thì request ghi phải gửi `version_no` đang giữ; sai phiên bản trả 409 `VERSION_CONFLICT` kèm `details.current_version_no`.
9. **Đếm mù**: khi `grns.is_blind_receipt = TRUE`, server **không trả** `qty_expected` cho vai trò `nv-nhan`; tương tự với phiếu kiểm kê (`nv-kiemke`). Đây là việc của tầng service, không để client tự ẩn.
10. Quyền dùng cột «Vai trò» ở mục 4; quyền theo mã (`NH-1`...) do A nạp từ ma trận mục 5.3 của đặc tả. Admin không đọc được dữ liệu nghiệp vụ.
11. Request tạo chứng từ nhận header `Idempotency-Key` (tùy chọn trong demo, bắt buộc khi làm offline sau này).
12. Đổi hợp đồng: sửa `docs/api/<module>.md` bằng PR, gắn chủ module và ít nhất một module gọi nó; thay đổi làm hỏng client cũ phải báo cả nhóm.

## 3. Bảng mã lỗi chung

| Mã | HTTP | Khi nào | Nguồn |
| --- | --- | --- | --- |
| `VALIDATION_ERROR` | 422 | Dữ liệu vào sai kiểu hoặc thiếu | Pydantic |
| `AUTH_INVALID_CREDENTIALS` | 401 | Sai tài khoản hoặc mật khẩu | `auth` |
| `AUTH_TOKEN_EXPIRED` | 401 | Token hết hạn | `auth` |
| `FORBIDDEN` | 403 | Vai trò không có quyền | `core.rbac` |
| `SOD_VIOLATION` | 403 | Người lập tự duyệt phiếu của mình | trigger SoD của DB |
| `REAUTH_REQUIRED` | 403 | Duyệt giá trị từ `reauth_min_amount` mà thiếu `reauth_method` | DB: `THIEU_XAC_THUC_LAI` |
| `NOT_FOUND` | 404 | Không có đối tượng hoặc thuộc kho khác | repository |
| `VERSION_CONFLICT` | 409 | Sai `version_no` | service |
| `INVALID_STATE` | 409 | Đối tượng không ở trạng thái cho phép hành động | service |
| `ORDER_FROZEN` | 409 | Đơn đang chờ Quản lý chốt đổi/hủy từ ERP | DB: `DON_BI_DONG_BANG` |
| `INVENTORY_INSUFFICIENT_QTY` | 409 | Trừ quá tồn khả dụng | DB: check `qty_available` |
| `INTERNAL_IMMUTABLE_RECORD` | 500 | Mã đang sửa hoặc xóa sổ cái, audit log | DB: `BAN_GHI_BAT_BIEN` (lỗi lập trình, ghi log) |
| `<MODULE>_<NGUYÊN_NHÂN>` | 400 hoặc 409 | Lỗi nghiệp vụ riêng của module | chủ module tự thêm vào `docs/api/<module>.md` |

Tầng service bắt lỗi DB theo tiền tố trong thông báo (`BAN_GHI_BAT_BIEN`, `DON_BI_DONG_BANG`, `THIEU_XAC_THUC_LAI`) và chuyển thành mã ở bảng trên bằng một hàm dịch lỗi duy nhất trong `core/exceptions.py`.

## 4. Danh mục endpoint theo module

Cột «Vai trò» dùng `role_code`; «mọi vai trò» là mọi người dùng đã đăng nhập. Mọi endpoint lọc theo kho trong token. Chủ module bổ sung body, response, mã lỗi riêng.

### 4.1 `auth` (A)

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| POST | `/auth/login` | Đăng nhập, trả token | công khai |
| GET | `/auth/me` | Thông tin người dùng và danh sách quyền | mọi vai trò |
| POST | `/auth/change-password` | Đổi mật khẩu (bắt buộc lần đầu) | mọi vai trò |

### 4.2 `master_data` (A)

Mẫu chung cho mỗi tài nguyên: `GET /{tài-nguyên}`, `GET /{tài-nguyên}/{id}`, `POST /{tài-nguyên}`, `PATCH /{tài-nguyên}/{id}`, `POST /{tài-nguyên}/{id}/deactivate`.

| Tài nguyên | Đọc | Ghi |
| --- | --- | --- |
| `warehouses`, `zones`, `locations`, `item-categories`, `skus`, `sku-barcodes`, `suppliers`, `customers`, `reason-codes`, `box-types` | mọi vai trò (trừ `admin` với dữ liệu nghiệp vụ không liên quan) | `admin` |
| `users`, `roles` | `admin` | `admin` |

### 4.3 `inventory` (A)

Không có endpoint ghi tồn công khai: mọi thay đổi tồn đi qua `apply_movement` và `transfer_inventory` do module khác gọi trong service.

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| GET | `/inventory/balances` | Tồn theo SKU, vị trí, lô, trạng thái (`?sku_id=&location_id=&lot_id=`) | `nv-nhan`, `nv-cat`, `nv-soan`, `nv-dongoi`, `thukho`, `quanly`, `bgd` |
| GET | `/inventory/transactions` | Sổ cái giao dịch tồn | `thukho`, `quanly` |
| GET | `/lots` | Danh sách lô và hạn dùng | như trên |
| GET | `/pallets`, `/pallets/{id}` | Pallet và trạng thái | như trên |
| GET | `/locations/{id}/stock` | Hàng đang có tại một vị trí | như trên |

### 4.4 `integrations` (A, chỉ môi trường dev)

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| POST | `/integrations/erp/purchase-orders` | ERP mock đẩy PO | `admin` |
| POST | `/integrations/erp/asns` | ERP mock đẩy ASN | `admin` |
| POST | `/integrations/erp/outbound-orders` | ERP mock đẩy SO | `admin` |
| POST | `/integrations/erp/outbound-orders/{order_id}/changes` | ERP mock đổi hoặc hủy đơn (gọi `fn_receive_erp_order_change`) | `admin` |
| GET | `/integrations/sync-logs` | Nhật ký đồng bộ | `quanly`, `admin` |

### 4.5 `inbound` (B)

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| GET | `/purchase-orders`, `/purchase-orders/{id}` | Xem PO và dòng | `nv-nhan`, `thukho`, `quanly` |
| GET | `/asns` | Xem ASN | `nv-nhan`, `thukho`, `quanly` |
| POST | `/grns` | Tạo GRN từ PO hoặc ASN | `nv-nhan` |
| GET | `/grns`, `/grns/{id}` | Xem GRN (đếm mù thì ẩn `qty_expected`) | `nv-nhan`, `thukho`, `quanly` |
| POST | `/grns/{id}/lines` | Ghi một dòng đếm (SKU, lô, hạn, số lượng, hàng hư) | `nv-nhan` |
| POST | `/grns/{id}/submit` | Chốt đếm; gọi `fn_resolve_approval_tier`, tự ghi nhận hoặc tạo yêu cầu duyệt | `nv-nhan` |
| POST | `/grns/{id}/recount` | Đếm lại khi bị yêu cầu | `nv-nhan` |
| POST | `/grns/{id}/complete` | Hoàn tất: tạo pallet, trạng thái STAGED, sinh task PUTAWAY | `nv-nhan` |
| POST | `/putaway/suggest` | Gợi ý vị trí cất cho pallet | `nv-cat` |
| POST | `/pallets/{id}/putaway` | Xác nhận cất vào `location_id` | `nv-cat` |

### 4.6 `outbound` (C)

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| GET | `/outbound-orders`, `/outbound-orders/{id}` | Xem đơn xuất (`?status=`) | `thukho`, `quanly` |
| POST | `/outbound-orders/{id}/allocate` | Cấp phát FEFO/FIFO, ghi `inventory_allocations` | `thukho`, `quanly` |
| POST | `/pick-sessions` | Tạo phiên soạn từ một hoặc nhiều đơn | `thukho` |
| GET | `/pick-sessions/{id}` | Xem phiên và các dòng soạn | `nv-soan`, `thukho` |
| POST | `/pick-sessions/{id}/lines/{line_id}/confirm` | Xác nhận soạn một dòng | `nv-soan` |
| POST | `/pick-sessions/{id}/lines/{line_id}/exception` | Báo thiếu, hư, sai lô | `nv-soan` |
| POST | `/outbound-orders/{id}/packages` | Đóng gói: tạo kiện và dòng kiện | `nv-dongoi` |
| POST | `/goods-issues` | Lập GI, gán xe và tài xế | `nv-dongoi` |
| POST | `/goods-issues/{id}/confirm` | Xác nhận giao, đơn SHIPPED, trừ tồn | `nv-dongoi` |
| POST | `/order-changes/{id}/decide` | Quản lý chốt yêu cầu đổi/hủy của ERP (`ACCEPT` hoặc `REJECT`, gọi `fn_decide_order_change`) | `quanly` |

### 4.7 `tasks` (D)

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| GET | `/tasks` | Danh sách (`?scope=mine`, `queue`, `all`) | nhân viên thực thi xem của mình; `thukho`, `quanly` xem tất cả |
| GET | `/tasks/{id}` | Chi tiết | như trên |
| POST | `/tasks` | Tạo task thủ công | `thukho`, `quanly` |
| POST | `/tasks/{id}/assign` | Giao cho `user_id` | `thukho`, `quanly` |
| POST | `/tasks/{id}/accept` | Nhận task | nhân viên được giao |
| POST | `/tasks/{id}/reject` | Từ chối kèm `reason_code` | nhân viên được giao |
| POST | `/tasks/{id}/complete` | Hoàn tất | nhân viên được giao |
| POST | `/tasks/{id}/reassign`, `/tasks/{id}/cancel` | Điều chuyển, hủy | `thukho`, `quanly` |

### 4.8 `approvals` (D)

Yêu cầu duyệt chênh lệch (`GRN_DISCREPANCY`, `CYCLE_COUNT_DIFF`) được tạo từ service của module khác; riêng đề xuất điều chỉnh tồn / hủy hàng (`TK-4.3`) do Thủ kho tạo qua endpoint riêng bên dưới.

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| GET | `/approvals` | Hàng chờ (`?status=&tier=&object_type=&expired=true`) | `thukho` (D1), `quanly` (D2), `bgd` (D3) |
| GET | `/approvals/{id}` | Chi tiết, lịch sử và khóa xem đúng tầng (`?lock=true`, timeout 15 phút) | như trên |
| POST | `/approvals/{id}/unlock` | Nhả khóa xem hồ sơ chủ động | người giữ khóa |
| POST | `/approvals/stock-adjustments` | Đề xuất điều chỉnh tồn hoặc hủy hàng | `thukho` |
| POST | `/approvals/{id}/approve` | Duyệt chốt ở tầng hiện tại; gửi `reauth_method` + `reauth_password` nếu từ ngưỡng xác thực lại | đúng cấp của yêu cầu |
| POST | `/approvals/{id}/escalate` | Thủ kho chuyển tiếp hồ sơ lên Quản lý kho (D2) | `thukho` |
| POST | `/approvals/{id}/reject` | Từ chối kèm lý do | đúng cấp của yêu cầu |
| POST | `/approvals/{id}/request-info` | Trả về người lập xin thêm thông tin hoặc đếm lại | đúng cấp của yêu cầu |
| POST | `/approvals/escalate-expired` | Chạy leo thang SLA toàn hệ thống (gọi `fn_escalate_expired_approvals`) | `quanly` |

### 4.9 `cycle_count` (B)

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| POST | `/cycle-counts` | Tạo phiếu kiểm kê, khóa vị trí | `thukho` |
| GET | `/cycle-counts`, `/cycle-counts/{id}` | Xem phiếu (đếm mù thì ẩn tồn hệ thống) | `thukho`, `nv-kiemke` |
| POST | `/cycle-counts/{id}/lines/{line_id}/count` | Ghi số đếm | `nv-kiemke` |
| POST | `/cycle-counts/{id}/lines/{line_id}/recount` | Đếm lại, phải là người khác lần trước | `nv-kiemke` |
| POST | `/cycle-counts/{id}/close` | Đóng phiếu | `thukho` |

### 4.10 `dashboard` (A, chỉ đọc)

| Method | Đường dẫn | Mục đích | Vai trò |
| --- | --- | --- | --- |
| GET | `/dashboard/tasks`, `/dashboard/inventory`, `/dashboard/orders` | Số liệu tổng quan | `thukho`, `quanly`, `bgd` |

## 5. Mẫu hợp đồng một endpoint

Mỗi module dùng đúng khung này cho từng endpoint trong `docs/api/<module>.md`. Ví dụ dưới đây dùng các cột đã có trong bảng `grn_lines`.

```markdown
### POST /api/v1/grns/{grn_id}/lines
- Mục đích: ghi một dòng đếm cho GRN đang ở trạng thái đang đếm
- Vai trò: nv-nhan (chỉ GRN do mình nhận)
- Hàm DB và bảng chạm tới: grn_lines (ghi), grns (đọc trạng thái, version_no)
- Trạng thái trước / sau: COUNTING / COUNTING
- Request body:
  po_line_id (uuid, tùy chọn), sku_id (uuid), lot_id (uuid, tùy chọn),
  uom_code (chuỗi), qty_actual (chuỗi số), qty_damaged (chuỗi số),
  serial_numbers (mảng chuỗi, tùy chọn), reason_code (chuỗi, tùy chọn), version_no (số nguyên)
- Phản hồi 201: grn_line_id, grn_id, sku_id, qty_actual, qty_damaged (không có qty_expected nếu đếm mù)
- Lỗi: VALIDATION_ERROR 422, NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409, INBOUND_PO_CLOSED 409
```

Ví dụ request và phản hồi:

```json
// POST /api/v1/grns/7b1f.../lines
{
  "po_line_id": "2c9e...",
  "sku_id": "5a41...",
  "uom_code": "PCS",
  "qty_actual": "6.000",
  "qty_damaged": "1.000",
  "version_no": 3
}
// 201 Created
{
  "data": {
    "grn_line_id": "c0d3...",
    "grn_id": "7b1f...",
    "sku_id": "5a41...",
    "qty_actual": "6.000",
    "qty_damaged": "1.000"
  },
  "meta": { "request_id": "a8f2..." }
}
// 409 Conflict khi version_no cũ
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "GRN đã được người khác cập nhật",
    "details": { "current_version_no": 4 }
  }
}
```

## 6. Việc cần làm để chuẩn này có hiệu lực

| Việc | Ai | Hạn | Xong khi |
| --- | --- | --- | --- |
| Cả nhóm đọc và chốt mục 1 (công nghệ) | Cả nhóm, A ghi ADR | Ngày 1 | Có `docs/adr/0001-cong-nghe.md`, không còn ý kiến mở |
| Dựng khung chung: envelope, dịch lỗi, `require_permission`, `api_client` | A | Ngày 1 đến 2 | Một endpoint mẫu `GET /auth/me` chạy đủ envelope và mã lỗi |
| Viết `docs/api/<module>.md` theo mẫu mục 5 cho module của mình | A (auth, master\_data, inventory, integrations, dashboard), B (inbound, cycle\_count), C (outbound), D (tasks, approvals) | Ngày 2 đến 3 | Mọi endpoint của mục 4 có đủ body, phản hồi, mã lỗi; module gọi đến đã ghi «ok» trong PR |
| Sinh OpenAPI từ FastAPI rồi đối chiếu với `docs/api/` | A | Ngày 3 | Không còn endpoint nào khác nhau giữa code và tài liệu |

## 7. Phân tầng xử lý và MVC

Hệ thống dùng Client–Server kết hợp MVC và phân tầng; không thêm thành phần công nghệ hoặc dịch vụ độc lập nào ngoài mục 1.

### 7.1 Trách nhiệm từng thành phần

| Thành phần | Công nghệ | File | Trách nhiệm |
| --- | --- | --- | --- |
| View | Jinja2, HTMX, Tailwind CSS | `client/app/**/templates/` | Hiển thị và nhận thao tác người dùng; gửi yêu cầu tới Backend API; không tự quyết định quyền nghiệp vụ |
| Controller phía client | FastAPI | `client/app/modules/<m>/views.py` | Nhận thao tác từ View, gọi `api_client`, trả giao diện |
| Controller phía server | FastAPI Router | `routers.py` | Nhận request, kiểm quyền bằng `require_permission`, gọi Service; không chứa nghiệp vụ, không viết SQL |
| Schema | Pydantic v2 | `schemas.py` | Kiểm tra dữ liệu vào và định dạng phản hồi |
| Service | Python | `services.py` | Nghiệp vụ, kiểm điều kiện trước khi ghi, điều phối transaction, gọi hàm DB |
| Repository | SQLAlchemy 2.x | `repositories.py` | Truy vấn và thao tác dữ liệu; không chứa quy tắc nghiệp vụ |
| Model | SQLAlchemy 2.x | `models.py` | Ánh xạ bảng PostgreSQL |

### 7.2 Quy tắc

1. Router không chứa nghiệp vụ phức tạp, không import `sqlalchemy` hay `models`.
2. Service kiểm điều kiện nghiệp vụ trước khi đổi dữ liệu; Repository không quyết định nghiệp vụ.
3. **Repository linh hoạt:** module có truy vấn đơn giản được để Service dùng session SQLAlchemy trực tiếp thay vì tạo Repository riêng. Mỗi module chọn một cách, ghi một dòng ở đầu `services.py`, và dùng nhất quán trong module đó.
4. **Giới hạn của quy tắc 3:** lời gọi hàm `fn_*` của DB luôn nằm trong `repositories.py` của module sở hữu hàm đó (inventory, approvals, outbound); module khác gọi qua hàm công khai của Service. Chỉ `inventory.services` được gọi `fn_apply_inventory_movement` và `fn_transfer_inventory`.
5. Truy vấn nhiều bảng hoặc báo cáo (dashboard) đặt trong `repositories.py`, không viết trong Service.
6. Thao tác ảnh hưởng tồn kho tuân thủ mục 9.
7. Giữ cây thư mục theo mục 3 của đặc tả (chia theo module, mỗi module một bộ file) vì khớp với phân công nhánh, `CODEOWNERS` và test kiến trúc. Không tự thêm tầng hoặc dịch vụ mới; không bắt buộc tách file riêng cho chức năng nhỏ, gom trong cùng module. Không dựng tiến trình nền nên bỏ thư mục `scheduler/`.
8. Client và Server chạy độc lập, nói chuyện qua HTTP API; Client không bao giờ kết nối trực tiếp PostgreSQL.

## 8. Bảo mật Client–Server

1. Giữ nguyên mục 1: JWT một token 8 giờ, bcrypt. Không thêm OAuth, SSO, refresh token trong 15 ngày.
2. Token chỉ nằm trong cookie `HttpOnly` của client; JavaScript không đọc được. Bật `Secure` khi chạy HTTPS (môi trường dev dùng HTTP thì tắt bằng cấu hình); `SameSite=Lax`.
3. Luồng thật: trình duyệt nói chuyện với client bằng cookie, client nói chuyện với server bằng header `Authorization: Bearer`. Vì server không nhận cookie, **chống CSRF chỉ cần làm ở client**.
4. **Chống CSRF bản gọn (bắt buộc):** middleware ở client chặn mọi `POST`, `PUT`, `PATCH`, `DELETE` có `Origin` (hoặc `Referer`) không trùng host của client; request HTMX phải có header `HX-Request: true`. Token CSRF đầy đủ (double-submit) để giai đoạn sau.
5. Server kiểm JWT, vai trò và quyền ở mọi endpoint cần bảo vệ. Ẩn nút hay ẩn menu trên giao diện không được tính là phân quyền.
6. Không gửi mật khẩu, secret key hay chuỗi kết nối DB về trình duyệt; cấu hình nhạy cảm chỉ ở `.env`.
7. Không ghi JWT, mật khẩu, header `Authorization` hay cookie vào log.

Test bắt buộc cho mục này: (a) POST có `Origin` lạ bị từ chối; (b) cookie phiên có cờ `HttpOnly` và `SameSite`; (c) chạy một chuỗi đăng nhập rồi đọc toàn bộ log, không chứa token hay mật khẩu.

## 9. Giao dịch và kiểm soát đồng thời

### 9.1 Transaction

1. Một request là một transaction (đã có ở lõi server). Nghiệp vụ ghi nhiều bước gom trong cùng transaction; một bước lỗi thì rollback toàn bộ.
2. Không để chứng từ hoàn tất mà tồn chưa cập nhật, hoặc ngược lại: đổi trạng thái chứng từ và gọi `apply_movement` hoặc `transfer_inventory` trong **cùng** transaction.
3. Ưu tiên hàm PostgreSQL đã có trong schema và patch.

### 9.2 Đồng thời

1. Đối tượng có `version_no` tuân theo quy ước 8 ở mục 2; sai phiên bản trả 409 `VERSION_CONFLICT`.
2. Việc kiểm và trừ tồn nằm trong hàm DB nên Python **không tự đọc tồn rồi ghi lại**. Nếu bắt buộc đọc rồi ghi ngoài hàm DB thì dùng `SELECT ... FOR UPDATE` trong cùng transaction.
3. Tồn khả dụng không âm do DB chặn (trả `INVENTORY_INSUFFICIENT_QTY`); app không viết lại phép kiểm này.

### 9.3 Lịch sử và audit

1. Không UPDATE hay DELETE sổ cái tồn (trigger DB chặn); app không viết lệnh như vậy.
2. Mọi biến động tồn đi qua `apply_movement` hoặc `transfer_inventory`.
3. Bắt buộc ghi `audit_logs` cho: đăng nhập, tạo, gửi, duyệt, từ chối chứng từ, biến động tồn, giao, nhận, hủy task, đổi hoặc hủy đơn từ ERP.
4. Lỗi nghiệp vụ và xung đột trả mã lỗi ở mục 3.

### 9.4 Test bắt buộc

| Test | Chủ | Nội dung |
| --- | --- | --- |
| Rollback chứng từ và tồn | B (inbound), C (outbound), D (cycle\_count) | Ép bước ghi tồn lỗi, chứng minh trạng thái chứng từ không đổi: `grns/{id}/complete`, `goods-issues/{id}/confirm`, điều chỉnh sau kiểm kê |
| Xung đột phiên bản | Mỗi module có `version_no` | Hai request cùng `version_no`, chỉ một thành công, một trả 409 |
| Trừ tồn đồng thời | A (inventory) | Hai kết nối trừ cùng một lượng tồn, tồn không âm và có một request trả `INVENTORY_INSUFFICIENT_QTY` |
