# Đặc tả dự án ABEST WMS: hệ thống quản lý kho

*Bản nháp v0.2 · Nhóm 4 người (A là leader) · Nguồn: slide phân rã v3, drawio workflows v2, SQL schema v4.1 + patch v4.2.1 · 13/11/2026*

## 1. Giới thiệu và phạm vi

### 1.1 Mục tiêu

Xây dựng hệ thống quản lý kho (WMS) cho doanh nghiệp Abest, phục vụ các nghiệp vụ nhận hàng, cất hàng, tồn kho, soạn hàng, đóng gói, xuất kho, kiểm kê, phê duyệt chênh lệch và điều phối công việc. Hệ thống có 9 vai trò người dùng và 9 tác nhân phụ (ERP, nhà cung cấp, khách hàng, TMS, máy quét/máy in, SSO/LDAP, FCM/APNs, Scheduler, hóa đơn điện tử).

Tài liệu gốc mô tả đầy đủ 178 chức năng, 27 quy tắc nghiệp vụ \[Q#\], 62 bảng (57 của schema v4.1 và 5 của patch v4.2.1), 20 kiểu ENUM. Bản đặc tả này **chọn một phần để làm demo vận hành kho cơ bản** và chia việc cho 4 người; phần còn lại để giai đoạn sau.

### 1.2 Phạm vi bản demo

| Có trong demo | Để giai đoạn sau |
| --- | --- |
| Đăng nhập, phân quyền theo 9 vai trò, audit log | SSO/LDAP thật, sinh trắc học |
| Danh mục: kho, zone, vị trí, SKU, mã vạch, NCC, khách hàng | Đồng bộ danh mục định kỳ từ ERP |
| Nhập kho: PO, ASN, GRN (đếm mù), pallet, cất hàng | Hàng trả RMA, trả NCC đầy đủ |
| Tồn kho 5 trạng thái, lô/hạn dùng, sổ cái giao dịch | Offline sync, thiết bị, in tem ZPL thật |
| Xuất kho: đơn, cấp phát FEFO/FIFO, soạn, đóng gói, GI | Wave/batch picking nâng cao, vận đơn TMS thật |
| Điều phối task (giao, nhận, từ chối, hoàn tất) | Ca làm, tăng ca, thời vụ, chứng nhận, đào tạo |
| Phê duyệt D1 → D2 → D3 với ngưỡng X/Y/Z | Ủy quyền duyệt, xác thực lại sinh trắc |
| Kiểm kê đếm mù, đếm lại, điều chỉnh tồn | Báo cáo hiệu suất nhân viên, sự cố an toàn |
| ERP/TMS giả lập (mock) | Hóa đơn điện tử, push notification FCM/APNs |

### 1.3 Thuật ngữ chính

| Viết tắt | Nghĩa | Tên dùng trong code |
| --- | --- | --- |
| PO / ASN | Đơn mua / thông báo giao hàng trước | `purchase_order`, `asn` |
| GRN | Phiếu nhập kho | `grn` |
| GI | Phiếu xuất kho | `goods_issue` |
| SKU / Lô | Mã hàng / lô sản xuất | `sku`, `lot` |
| Pallet | Tấm kê hàng | `pallet` |
| Kiểm kê | Cycle count | `cycle_count` |
| D1/D2/D3 | Cấp duyệt: Thủ kho / Quản lý kho / Ban giám đốc | `D1_THUKHO`, `D2_QUANLY`, `D3_BGD` |
| X, Y, Z | Ngưỡng duyệt D1, D2 và dung sai tự ghi nhận | `threshold_x_d1_amount`, `threshold_y_d2_amount`, `tolerance_z_*` |
| FEFO / FIFO | Hết hạn trước xuất trước / nhập trước xuất trước | `FEFO`, `FIFO` |

## 2. Kiến trúc: Client–Server kết hợp MVC

### 2.1 Mô hình tổng thể

```text
┌──────────────────────┐    HTTPS / JSON (REST)    ┌────────────────────────────────┐
│  CLIENT (Python)     │ ────────────────────────► │  SERVER (Python, REST API)     │
│  View: templates     │ ◄──────────────────────── │  Controller: routers+services  │
│  Controller: views   │                           │  Model: ORM + repositories     │
│  api_client (httpx)  │                           │  View: schemas (JSON)          │
└──────────────────────┘                           └───────────────┬────────────────┘
                                                                   │ SQL
                                                   ┌───────────────▼────────────────┐
                                                   │ PostgreSQL 15+ (v4.1+v4.2.1)   │
                                                   └────────────────────────────────┘
   Server còn có thư mục integrations/ (ERP mock, TMS mock).
```

Cách áp MVC cho từng phía:

| Lớp MVC | Phía server | Phía client |
| --- | --- | --- |
| **Model** | `models.py` (ORM), `repositories.py` (truy vấn DB) | `api_client.py` (gọi API, trả dữ liệu) |
| **Controller** | `routers.py` (nhận HTTP, kiểm quyền) và `services.py` (nghiệp vụ, transaction) | `views.py` (route của client: nhận thao tác người dùng, gọi api\_client) |
| **View** | `schemas.py` (Pydantic: hình dạng JSON vào/ra) | `templates/*.html` (giao diện) |

### 2.2 Công nghệ đề xuất (nhóm họp chốt, ghi vào ADR)

| Hạng mục | Đề xuất | Lý do |
| --- | --- | --- |
| Ngôn ngữ | Python 3.11+ | Yêu cầu của nhóm |
| Server | FastAPI + Uvicorn | Tự sinh tài liệu OpenAPI, kiểm tra dữ liệu bằng Pydantic |
| ORM, migration | SQLAlchemy 2.x; schema nạp bằng psql (v4.1 rồi patch v4.2.1), Alembic chỉ cho thay đổi sau đó | Thêm giá trị ENUM của patch không chạy được trong transaction của migration, nên không nạp ban đầu bằng Alembic |
| CSDL | PostgreSQL 15+ | Schema v4.1 và patch v4.2.1 dùng UUID, ENUM, trigger, `UNIQUE NULLS NOT DISTINCT` |
| Xác thực | JWT (access + refresh), băm mật khẩu bcrypt | Đủ cho demo; SSO giả lập |
| Client | Web mobile-first chạy riêng: Flask hoặc FastAPI + Jinja2 + HTMX | Dùng được trên điện thoại/máy PDA, không cần dựng app native |
| Quét mã | Máy quét kiểu bàn phím hoặc nhập tay (demo) | Camera trình duyệt để giai đoạn sau |
| Chất lượng | pytest, ruff, black, mypy, pre-commit | Đồng nhất code của 4 người |
| Môi trường | Docker Compose (Postgres) + `.env` | Mỗi người chạy giống nhau |

### 2.3 Quy tắc phụ thuộc giữa các lớp

1. `routers` chỉ gọi `services`, không import `sqlalchemy` hay `models`; không viết nghiệp vụ hay SQL trong router.
2. `services` gọi `repositories` (hoặc dùng session SQLAlchemy trực tiếp cho truy vấn đơn giản; mỗi module chọn một cách và ghi một dòng ở đầu `services.py`) và **hàm công khai của service module khác**; không truy cập trực tiếp bảng của module khác.
3. `repositories` chứa truy vấn nhiều bảng, báo cáo và mọi lời gọi hàm `fn_*` của module sở hữu hàm đó (chi tiết ở mục 7 của chuẩn API).
4. Mọi thay đổi tồn kho **bắt buộc** đi qua `inventory.services.apply_movement()` (tương ứng `fn_apply_inventory_movement` trong schema), không ai tự sửa `inventory_balances`.
5. Mọi lỗi nghiệp vụ ném `BusinessError(code, message)`; router không tự bắt từng nơi mà dùng exception handler chung.

**Quy tắc 6 (theo patch v4.2.1): nghiệp vụ lõi nằm ở DB, Python chỉ gọi, không viết lại.** Các hàm `fn_apply_inventory_movement`, `fn_transfer_inventory`, `fn_resolve_approval_tier`, `fn_receive_erp_order_change`, `fn_decide_order_change`, `fn_escalate_expired_approvals` là nguồn sự thật. Service gọi chúng qua `repositories.py`, đổi các lỗi `BAN_GHI_BAT_BIEN`, `DON_BI_DONG_BANG`, `THIEU_XAC_THUC_LAI` thành `BusinessError`, và không tự tính lại tầng duyệt hay số tồn.

## 3. Cấu trúc thư mục

```text
abest-wms/
├─ README.md                  # cách cài, chạy, quy ước
├─ CONTRIBUTING.md            # quy trình git, review
├─ docker-compose.yml         # postgres (+ pgadmin tuỳ chọn)
├─ .env.example
├─ .github/
│  ├─ CODEOWNERS
│  ├─ PULL_REQUEST_TEMPLATE.md
│  └─ workflows/ci.yml        # ruff, black --check, mypy, pytest
├─ docs/
│  ├─ spec/                   # đặc tả và chuẩn công nghệ + API
│  ├─ source/                 # slide v3, drawio v2 (tài liệu gốc)
│  ├─ adr/                    # quyết định kiến trúc: 0001-cong-nghe.md ...
│  ├─ api/                    # hợp đồng API từng module
│  └─ reports/                # báo cáo của từng bước dựng khung
├─ database/
│  ├─ schema.sql              # schema v4.1 (đã đóng băng)
│  ├─ patch_v4_2_1.sql        # patch v4.2.1 (đã đóng băng)
│  ├─ migrations/             # alembic, chỉ cho thay đổi sau v4.2.1
│  ├─ seeds/                  # roles, permissions, dữ liệu mẫu, users demo
│  └─ tests/                  # smoke_test.sql, test_seed.sql
├─ server/
│  ├─ requirements.txt
│  ├─ app/
│  │  ├─ main.py              # tạo app, tự nạp router của các module
│  │  ├─ core/                # config, database, security, rbac, exceptions, logging, audit
│  │  ├─ shared/              # enums (sinh từ DB), constants, utils
│  │  ├─ modules/
│  │  │  ├─ auth/             # models, schemas, repositories, services, routers
│  │  │  ├─ master_data/
│  │  │  ├─ inventory/
│  │  │  ├─ inbound/
│  │  │  ├─ outbound/
│  │  │  ├─ tasks/
│  │  │  ├─ approvals/
│  │  │  ├─ cycle_count/
│  │  │  └─ dashboard/
│  │  └─ integrations/        # erp_mock.py, tms_mock.py (cùng interface với bản thật)
│  └─ tests/
│     ├─ unit/<module>/
│     ├─ integration/<module>/
│     ├─ e2e/                 # kịch bản demo chạy từ đầu đến cuối
│     └─ architecture/        # test phân tầng, test ENUM khớp DB
├─ client/
│  ├─ requirements.txt
│  └─ app/
│     ├─ main.py
│     ├─ core/                # api_client.py, session.py, auth_guard.py, config.py
│     ├─ static/              # css, js, ảnh
│     ├─ templates/_base/     # layout, menu theo vai trò, component chung
│     └─ modules/<module>/    # views.py, templates/, forms.py (cùng tên module phía server)
└─ scripts/                   # reset_db.sh, run_db_tests.sh, create_branches.sh, check_structure.py
```

Mỗi module phía server có đúng 5 file: `models.py`, `schemas.py`, `repositories.py`, `services.py`, `routers.py`, cộng `__init__.py` chỉ export các hàm công khai mà module khác được phép gọi.

## 4. Quy cách đặt tên

### 4.1 Nguyên tắc chung

- Định danh (biến, hàm, lớp, file, bảng, endpoint) viết **tiếng Anh**; chú thích và docstring được viết tiếng Việt.
- Tuân theo PEP 8, tối đa 100 ký tự mỗi dòng, format bằng `black`, lint bằng `ruff`.
- Thuật ngữ nghiệp vụ dùng đúng bảng ở mục 1.3, không tự đặt biến thể (không viết `receipt` ở nơi này và `grn` ở nơi khác).

### 4.2 Bảng quy ước

| Đối tượng | Quy ước | Ví dụ |
| --- | --- | --- |
| File, thư mục Python | `snake_case` | `inventory_balance_repository.py` |
| Lớp (ORM, service, exception) | `PascalCase`, ORM dùng số ít | `InventoryBalance`, `GrnService`, `BusinessError` |
| Schema Pydantic | `<Thực thể><Mục đích>` | `GrnCreate`, `GrnUpdate`, `GrnRead`, `GrnListItem` |
| Hàm, biến | `snake_case`, hàm bắt đầu bằng động từ | `create_grn`, `confirm_putaway`, `calculate_discrepancy_amount` |
| Động từ chuẩn của service | `create_` `get_` `list_` `update_` `cancel_` `submit_` `approve_` `reject_` `assign_` `confirm_` `apply_` | `submit_grn_for_approval` |
| Biến boolean | tiền tố `is_` `has_` `can_` `should_` | `is_blind_receipt`, `has_discrepancy` |
| Hàm/biến nội bộ | tiền tố `_` | `_resolve_approval_tier` |
| Hằng số | `UPPER_SNAKE_CASE` | `MAX_RECOUNT_ATTEMPTS` |
| Giá trị ENUM | `UPPER_SNAKE_CASE`, **trùng giá trị ENUM trong DB** | `PENDING_D1`, `QUARANTINE_HOLD` |
| Bảng DB | `snake_case`, số nhiều (theo schema v4.1) | `inventory_balances`, `grn_lines` |
| Cột DB | `snake_case`; khóa chính `<bảng_số_ít>_id`; thời gian `_at`; số lượng `qty_`; tiền `_amount` | `grn_id`, `created_at`, `qty_available` |
| Endpoint REST | tiền tố `/api/v1`, `kebab-case`, danh từ số nhiều | `/api/v1/purchase-orders/{po_id}/lines` |
| Hành động không thuộc CRUD | `POST .../{id}/<động-từ>` | `POST /api/v1/grns/{grn_id}/submit` |
| Trường JSON | `snake_case` | `received_qty` |
| Mã quyền | giữ nguyên mã trong tài liệu gốc | `NH-1`, `TK-3.2`, `QL-7.3` |
| Mã vai trò | giữ nguyên `role_code` trong DB | `nv-nhan`, `thukho`, `quanly`, `bgd`, `admin` |
| Mã lỗi nghiệp vụ | `<MODULE>_<NGUYÊN_NHÂN>` | `INBOUND_PO_CLOSED`, `INVENTORY_INSUFFICIENT_QTY` |
| Test | `test_<hành_vi>_<điều_kiện>` | `test_apply_movement_rejects_negative_available_qty` |
| Template client | `<module>/<trang>.html` | `inbound/grn_count.html` |

### 4.3 Ví dụ ngắn đúng quy cách

```python
# server/app/modules/inbound/services.py
def submit_grn_for_approval(db: Session, grn_id: UUID, actor: CurrentUser) -> Grn:
    """Gửi GRN lệch lên cấp duyệt; mọi nghiệp vụ tính tầng duyệt đi qua approvals."""
    grn = grn_repository.get_by_id(db, grn_id)
    if grn.status != GrnStatus.COUNTING:
        raise BusinessError("INBOUND_GRN_INVALID_STATE", "GRN không ở trạng thái đang đếm")
    ...
```

## 5. Phân quyền hệ thống (RBAC)

### 5.1 Chín vai trò

| `role_code` | Vai trò | Nhóm (`actor_group`) | Kênh | Nhiệm vụ chính |
| --- | --- | --- | --- | --- |
| `nv-nhan` | Nhân viên nhận hàng | THUC\_THI | Mobile | Chọn phiếu, kiểm đếm mù, xử lý lệch, tạo pallet, đóng GRN |
| `nv-cat` | Nhân viên cất hàng | THUC\_THI | Mobile | Nhận task cất, quét pallet và vị trí đích |
| `nv-soan` | Nhân viên soạn hàng | THUC\_THI | Mobile | Thực hiện phiên pick, báo ngoại lệ |
| `nv-dongoi` | Nhân viên đóng gói, xuất hàng | THUC\_THI | Mobile | Kiểm đơn, đóng gói, in tem, lập GI |
| `nv-kiemke` | Nhân viên kiểm kê | THUC\_THI | Mobile | Đếm mù, ghi bất thường, đếm lại |
| `thukho` | Thủ kho / Trưởng ca | DIEU\_HANH | Mobile + Web | Điều phối task, duyệt D1, bàn giao ca, nghiệp vụ nội bộ |
| `quanly` | Quản lý kho | DIEU\_HANH | Mobile + Web | Giám sát, duyệt D2, nhân lực, xử lý ngoại lệ đơn |
| `bgd` | Ban giám đốc | LANH\_DAO | Web | Dashboard, duyệt D3, nhận cảnh báo sự cố |
| `admin` | Quản trị hệ thống | HE\_THONG | Web | Người dùng, phân quyền, danh mục, cấu hình; **không xem dữ liệu nghiệp vụ** |

### 5.2 Ký hiệu quyền (`role_permissions.access_type`)

`X` thực hiện · `X_OWN` thực hiện việc của mình · `V` chỉ xem · `V_OWN` chỉ xem dữ liệu của mình · `G` giao việc · `E` đề xuất · `D1`/`D2`/`D3` duyệt theo cấp · `-` không có quyền.

### 5.3 Ma trận quyền cho phạm vi demo

(Rút từ ma trận phân quyền trong slide v3; các dòng nhân lực/ca/tăng ca/thời vụ nằm ở giai đoạn sau.)

| Chức năng | Nhận | Cất | Soạn | Đóng gói | Kiểm kê | Thủ kho | Quản lý | BGĐ | Admin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nhận hàng | X | - | - | - | - | V | V | - | - |
| Cất hàng | - | X | - | - | - | G | V | - | - |
| Soạn hàng | - | - | X | - | - | G | V | - | - |
| Đóng gói, xuất kho | - | - | - | X | - | G | V | - | - |
| Kiểm kê | - | - | - | - | X | G | V | - | - |
| Duyệt chênh lệch | - | - | - | - | - | D1 | D2 | D3 | - |
| Duyệt điều chỉnh tồn, hủy hàng | - | - | - | - | - | E | D2 | D3 | - |
| Theo dõi phiếu nhập xuất | - | - | - | - | - | V | V | - | - |
| Điều phối task | - | - | - | - | - | G | G | - | - |
| Tra cứu tồn kho | V | V | V | V | - | V | V | V | - |
| KPI, dashboard, báo cáo | - | - | - | - | - | V | V | V | - |
| Người dùng, phân quyền, danh mục, cấu hình | - | - | - | - | - | - | - | - | X |
| Sự cố an toàn lao động | X | X | X | X | X | X | X | V | - |
| Khiếu nại, giao thất bại, trả NCC | - | - | - | - | - | V | X | - | - |

### 5.4 Quy tắc bất biến cần cài đặt

1. **Phạm vi kho**: người dùng chỉ thấy dữ liệu của kho mình (`users.primary_warehouse_id`); mọi truy vấn lọc theo `warehouse_id`.
2. **Phân tách nhiệm vụ (SoD)**: người lập đề xuất không bao giờ tự duyệt, ở mọi cấp (schema đã có `chk_sod_no_self_approval` và trigger `fn_enforce_sod_all_tiers`; tầng ứng dụng cũng phải kiểm).
3. **Tầng duyệt theo giá trị chênh lệch và người lập** (drawio trang 5): ≤ Z tự ghi nhận (`AUTO_TOLERANCE_Z`); ≤ X lên D1 (chỉ khi người lập là nhân viên thực thi); ≤ Y lên D2 (Thủ kho lập thì bắt đầu từ D2); vượt Y hoặc Quản lý lập thì lên D3. Hồ sơ lệch hạn dùng, nhận không PO/ASN hoặc hàng hư luôn phải duyệt, không áp Z.
4. Mặc định ngưỡng (`warehouse_configs`): X = 5.000.000 · Y = 20.000.000 · Z = 500.000 hoặc 1% (theo `tolerance_z_mode`) · xác thực lại từ 10.000.000.
5. **Admin chỉ cấu hình**: không có quyền đọc phiếu, tồn, đơn hàng.
6. **Nhân viên chỉ làm task được giao cho mình**, và chỉ đúng khâu của vai trò (`primary_stage`); task đang giữ tối đa 3 (`max_open_tasks_per_user`).
7. Mọi hành động ghi (tạo, sửa, duyệt, hủy) ghi `audit_logs`; mọi thay đổi tồn ghi `inventory_transactions` (sổ cái bất biến).
8. Cập nhật đồng thời dùng `version_no` (optimistic locking); sai phiên bản trả HTTP 409.

Các quy tắc 2, 3, 6 và 7 trên đã được DB cưỡng chế (trigger SoD, `fn_resolve_approval_tier`, trigger xác thực lại khi giá trị từ `reauth_min_amount`, sổ cái bất biến); tầng ứng dụng chỉ chuyển lỗi sang `BusinessError`. Hồ sơ duyệt quá hạn (`EXPIRED`) giữ nguyên trạng thái chờ duyệt nhưng được đánh dấu bằng cột `approval_expired_at` của `grns` và `cycle_count_lines`; màn hình duyệt cần lọc theo cột này để xử lý thủ công.

### 5.5 Cách cài đặt phân quyền trong code

- Bảng `permissions` và `role_permissions` được nạp bằng seed từ ma trận trên (nguồn sự thật là DB, không viết cứng trong router).
- JWT chứa `user_id`, `role_code`, `warehouse_id`.
- Mỗi endpoint khai báo mã quyền cần có: `Depends(require_permission("NH-1"))`; hàm này tra `role_permissions` và trả về `access_type`.
- Service nhận `access_type` để xử lý các trường hợp `X_OWN`, `V_OWN` (lọc theo `assigned_to = user_id`) và cấp `D1/D2/D3` (so với `approval_requests.current_tier`).
- Menu phía client được dựng từ danh sách quyền của người dùng; ẩn nút không có quyền, nhưng **server luôn kiểm lại**.

* Client chống CSRF bản gọn: chặn `POST`, `PUT`, `PATCH`, `DELETE` có `Origin` lạ và yêu cầu header `HX-Request` cho request HTMX (chuẩn API, mục 8).

## 6. Module và kịch bản demo vận hành kho cơ bản

### 6.1 Danh sách module

| Mã | Module | Bảng chính (schema v4.1) | Phụ thuộc | Chủ |
| --- | --- | --- | --- | --- |
| M0 | `core` + `auth` | `users`, `roles`, `permissions`, `role_permissions`, `audit_logs` | không | A |
| M1 | `inventory` | `lots`, `pallets`, `inventory_balances`, `inventory_transactions` | master\_data | A |
| M2 | `integrations` (mock) | `integration_sync_logs` | không | A |
| M3 | `master_data` | `warehouses`, `warehouse_configs`, `zones`, `locations`, `item_categories`, `skus`, `sku_barcodes`, `suppliers`, `customers`, `reason_codes`, `box_types` | auth | B |
| M4 | `inbound` | `purchase_orders`, `po_lines`, `asns`, `grns`, `grn_lines` | inventory, tasks, approvals | B |
| M5 | `outbound` | `outbound_orders`, `outbound_order_lines`, `pick_sessions`, `pick_lines`, `packages`, `goods_issues` | inventory, tasks | C |
| M6 | `tasks` | `tasks` | auth | D |
| M7 | `approvals` | `approval_requests`, `approval_histories`, `stock_adjustments` | tasks, inventory | D |
| M8 | `cycle_count` | `cycle_count_sheets`, `cycle_count_lines`, `cycle_count_attempts` | inventory, tasks, approvals | D |
| M9 | `dashboard` (chỉ đọc) | truy vấn tổng hợp | tất cả | D |

Bảng thêm từ patch v4.2.1: `inventory_allocations` (inventory, outbound), `package_lines` và `order_change_requests` (outbound), `grn_count_attempts` (inbound), `return_order_lines` (giai đoạn sau, hàng trả).

Đường găng: **`inventory` (A) và `tasks` (D)** là hai module mọi người khác phải gọi. Hai người này làm xong giao diện hàm công khai (có thể trả dữ liệu giả) ngay giai đoạn đầu để B và C không phải chờ.

### 6.2 Kịch bản demo (chạy xuyên suốt, dùng làm bài test e2e)

1. **Chuẩn bị**: Admin đăng nhập, kiểm tra danh mục kho, vị trí, SKU đã seed.
2. **ERP mock** đẩy 1 PO và 1 ASN.
3. **Nhận hàng**: `nv-nhan` chọn phiếu, quét và đếm mù; một dòng lệch vượt dung sai Z → hệ thống cách ly pallet, tạo yêu cầu duyệt → `thukho` duyệt D1 → GRN APPROVED, PO cập nhật, pallet STAGED, sinh task PUTAWAY.
4. **Cất hàng**: `thukho` giao task, `nv-cat` quét pallet và vị trí đích → pallet STORED, tồn tăng.
5. **Tra cứu**: `quanly` xem tồn theo SKU, vị trí, lô/hạn dùng và lịch sử giao dịch.
6. **Xuất kho**: ERP mock đẩy 1 SO → cấp phát FEFO → tạo phiên soạn, giao `nv-soan`; một dòng báo thiếu (ngoại lệ) → xử lý.
7. **Đóng gói và xuất**: `nv-dongoi` kiểm đơn, chọn thùng, lập GI, gán xe, tài xế ký (nhập tay) → SHIPPED, tồn bị trừ.
8. **Kiểm kê**: khóa vị trí, `nv-kiemke` đếm mù, lệch lớn → đếm lại bởi người khác → vẫn lệch → `thukho` chuyển D2 → `quanly` duyệt → điều chỉnh tồn.
9. **Lãnh đạo**: một ca lệch vượt ngưỡng Y lên D3, `bgd` duyệt; `bgd` xem dashboard tổng quan.

### 6.3 Các giai đoạn đề xuất (nhóm tự điền ngày)

| Giai đoạn | Nội dung | Điều kiện hoàn thành |
| --- | --- | --- |
| 0. Chuẩn bị | Họp chốt công nghệ (ADR), tạo repo, nhánh, bảng công việc | Mọi người chạy được `docker compose up` và `pytest` rỗng |
| 1. Nền tảng | Khung dự án, schema + seed, auth + RBAC, master\_data, tasks và inventory (bản đầu) | 9 tài khoản đăng nhập, mỗi vai trò chỉ thấy menu của mình |
| 2. Nghiệp vụ lõi | Inbound, putaway, outbound, giao task | Chạy được bước 1 đến 7 của kịch bản |
| 3. Kiểm soát | Approvals D1 đến D3, cycle\_count, ERP mock đầy đủ | Chạy được bước 8 và 9 |
| 4. Hoàn thiện | Dashboard, sửa lỗi, tài liệu, quay demo | Tag `v0.1-demo` trên `main` |

## 7. Quy trình Git và phân quyền kho mã

### 7.1 Nhánh

| Nhánh | Mục đích | Ai được ghi |
| --- | --- | --- |
| `main` | Bản ổn định, chạy được demo; gắn tag phát hành | Chỉ A gộp (merge) |
| `develop` | Tích hợp công việc của cả nhóm | Gộp qua pull request (PR) |
| `feature/<module>` | Nhánh dài hạn của người phụ trách module | Chủ module |
| `feature/<module>/<việc>` | Nhánh ngắn cho một việc cụ thể, tách từ nhánh module hoặc `develop` | Chủ module |
| `fix/<mô-tả>` | Sửa lỗi | Người sửa |

Nhánh theo người và module:

| Thành viên | Nhánh phụ trách |
| --- | --- |
| **A (leader)** | `feature/core-auth`, `feature/inventory`, `feature/integrations-mock` |
| **B** | `feature/master-data`, `feature/inbound` |
| **C** | `feature/outbound` |
| **D** | `feature/tasks`, `feature/approvals`, `feature/cycle-count`, `feature/dashboard` |

### 7.2 Quy tắc làm việc

1. Không đẩy (push) trực tiếp lên `main` và `develop`; luôn qua PR, cần ít nhất 1 người duyệt và CI xanh, gộp kiểu squash.
2. Mỗi ngày làm việc, kéo `develop` về và rebase nhánh của mình để xung đột nhỏ và sớm.
3. Reviewer: PR của B, C, D do A duyệt; PR của A do B duyệt. PR chạm vào module khác phải gắn thêm chủ module đó.
4. **Chỉ sửa trong module của mình.** Cần module khác thay đổi thì mở Issue hoặc PR gắn chủ module. Giao tiếp giữa module chỉ qua hàm công khai của `services`.
5. Các file dùng chung chỉ A sửa: `server/app/core/`, `server/app/shared/`, `server/app/main.py`, `database/schema.sql`, `database/migrations/`, `docker-compose.yml`, `.github/`. Khai báo trong `CODEOWNERS`.
6. Migration do A cấp số thứ tự và gộp, tránh hai người tạo hai migration cùng lúc.
7. Thông điệp commit theo Conventional Commits, scope là module: `feat(inbound): thêm API tạo GRN`, `fix(inventory): chặn tồn khả dụng âm`. Các loại: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
8. Không commit `.env`, mật khẩu, dữ liệu thật; chỉ commit `.env.example`.

### 7.3 Quyền trên kho mã

| Thành viên | Quyền GitHub/GitLab | Được làm thêm |
| --- | --- | --- |
| A | Admin/Maintainer | Cấu hình bảo vệ nhánh, gộp vào `main`, gắn tag, quản lý quyền |
| B, C, D | Write | Tạo nhánh, mở PR, review chéo; không gộp vào `main` |

## 8. Bảng phân công chi tiết

Quy ước: Ưu tiên P1 = bắt buộc cho demo, P2 = nên có, P3 = nếu còn thời gian. Mã quyền (NH-, TK-, QL-...) lấy từ slide v3.

**Điều chỉnh theo patch v4.2.1** (nghiệp vụ lõi đã nằm ở DB, Python gọi chứ không viết lại; công giảm khoảng 3 đến 5 người-ngày):

- A-06 chỉ bọc `fn_apply_inventory_movement`, `fn_transfer_inventory` và làm API tra cứu.
- D-03 chỉ bọc `fn_resolve_approval_tier`, `fn_escalate_expired_approvals` và API duyệt; không viết lại thuật toán tầng duyệt.
- C-02 ghi cấp phát vào `inventory_allocations`; B-05 ghi các lần đếm lại vào `grn_count_attempts`.
- C-07 nâng từ P3 lên P2: chủ yếu gọi `fn_receive_erp_order_change` và `fn_decide_order_change`.
- D-04, D-05: màn hình duyệt có bộ lọc hồ sơ hết hạn theo `approval_expired_at`.

### 8.1 Tóm tắt

| Thành viên | Vai trò | Module | Giao diện client phụ trách |
| --- | --- | --- | --- |
| **A** | Leader, kiến trúc, tích hợp | core, auth, inventory, integrations | Khung client, đăng nhập, tra cứu tồn |
| **B** | Danh mục và nhập kho | master\_data, inbound (gồm cất hàng) | Admin, `nv-nhan`, `nv-cat` |
| **C** | Xuất kho | outbound | `nv-soan`, `nv-dongoi` |
| **D** | Điều phối, duyệt, kiểm kê | tasks, approvals, cycle\_count, dashboard | `thukho`, `quanly`, `bgd`, `nv-kiemke` |

### 8.2 Thành viên A (leader)

| Mã | Công việc | Nhánh | Ưu tiên |
| --- | --- | --- | --- |
| A-01 | Khung dự án: cấu trúc thư mục, FastAPI app, cấu hình, phiên DB, Docker Compose, `.env.example`, CI, pre-commit, README, CONTRIBUTING | `feature/core-auth` | P1 |
| A-02 | Nạp schema v4.1, Alembic baseline, seed 9 vai trò, ma trận quyền, tài khoản demo | `feature/core-auth` | P1 |
| A-03 | Auth: đăng nhập JWT, làm mới token, `/me`, bắt đổi mật khẩu lần đầu, khóa tài khoản khi sai quá số lần | `feature/core-auth` | P1 |
| A-04 | RBAC: `require_permission`, lọc theo kho, `X_OWN`/`V_OWN`, kiểm tra SoD ở tầng ứng dụng | `feature/core-auth` | P1 |
| A-05 | Audit log, exception handler, chuẩn response, bảng mã lỗi, xử lý xung đột phiên bản (409) | `feature/core-auth` | P1 |
| A-06 | Inventory: lô, pallet, tồn 5 trạng thái, sổ cái; `apply_movement` (RECEIVE, PUTAWAY, ALLOCATE, DEALLOCATE, PICK, SHIP\_GI, ADJUSTMENT, LOCK\_COUNT); API tra cứu theo SKU, vị trí, lô (QL-1.1 đến QL-1.4) | `feature/inventory` | P1 |
| A-07 | ERP mock và TMS mock: đẩy PO, ASN, SO mẫu; nhận GRN, GI; ghi `integration_sync_logs`; thử lại khi lỗi | `feature/integrations-mock` | P1 |
| A-08 | Client lõi: `api_client`, phiên đăng nhập, layout, menu theo quyền, trang tra cứu tồn | `feature/core-auth` | P1 |
| A-09 | Review PR, giải quyết xung đột, gộp `develop` và `main`, gắn tag, viết bài test e2e theo kịch bản demo | các nhánh | P1 |

### 8.3 Thành viên B

| Mã | Công việc | Nhánh | Ưu tiên |
| --- | --- | --- | --- |
| B-01 | API danh mục: kho và cấu hình, zone, vị trí, nhóm hàng, SKU, mã vạch, NCC, khách hàng, mã lý do, loại thùng | `feature/master-data` | P1 |
| B-02 | Client cho Admin: màn hình danh mục và quản lý người dùng (gọi API của A) | `feature/master-data` | P2 |
| B-03 | PO, ASN: nhận từ ERP mock, danh sách, chi tiết (QL-2.1, QL-2.3) | `feature/inbound` | P1 |
| B-04 | GRN đếm mù: chọn phiếu, quét SKU, lô, hạn dùng, serial, lưu tạm (NH-1 đến NH-4) | `feature/inbound` | P1 |
| B-05 | Xử lý lệch: cảnh báo thừa, thiếu, hư, cách ly pallet, tạo yêu cầu duyệt (gọi `approvals` của D), đếm lại NH-5 | `feature/inbound` | P1 |
| B-06 | Hoàn tất GRN: tạo pallet, tem pallet (mock), trạng thái STAGED, cộng PO (tương ứng `fn_sync_po_on_grn_approved`), sinh task PUTAWAY | `feature/inbound` | P1 |
| B-07 | Cất hàng: gợi ý vị trí theo zone, sức chứa, cất một phần, báo vị trí đầy hoặc sai | `feature/inbound` | P1 |
| B-08 | Client cho `nv-nhan` và `nv-cat` | `feature/inbound` | P1 |

### 8.4 Thành viên C

| Mã | Công việc | Nhánh | Ưu tiên |
| --- | --- | --- | --- |
| C-01 | Nhận SO từ ERP mock: đơn và dòng, danh sách theo trạng thái (QL-3.1) | `feature/outbound` | P1 |
| C-02 | Cấp phát tồn FEFO/FIFO, ưu tiên lô `is_priority_dispatch`, đơn thiếu hàng chuyển ON\_HOLD | `feature/outbound` | P1 |
| C-03 | Phiên soạn (đơn lẻ, batch), sinh `pick_lines`, giao task PICKING qua `tasks`, sắp lộ trình theo vị trí | `feature/outbound` | P1 |
| C-04 | Thực hiện pick: quét vị trí, SKU, số lượng, bỏ qua dòng, ngoại lệ thiếu, hư, sai lô, thay lô | `feature/outbound` | P1 |
| C-05 | Đóng gói: kiểm đơn, chọn loại thùng, cân nặng, số kiện, `packages` | `feature/outbound` | P1 |
| C-06 | GI: gán xe và tài xế, quét kiện, chữ ký, SHIPPED và trừ tồn qua `inventory`; ba loại GI: `SO_SHIPMENT`, `INTER_WH_TRANSFER`, `SUPPLIER_RETURN` | `feature/outbound` | P1 |
| C-07 | ERP đổi hoặc hủy đơn: cờ `erp_change_pending`, hoàn tác phần đã làm bằng task RETURN\_PICKING (QL-5.1) | `feature/outbound` | P2 |
| C-08 | Client cho `nv-soan` và `nv-dongoi` | `feature/outbound` | P1 |

### 8.5 Thành viên D

| Mã | Công việc | Nhánh | Ưu tiên |
| --- | --- | --- | --- |
| D-01 | Module `tasks`: tạo, trạng thái, nhận, từ chối, hoàn tất, chống giao trùng bằng `version_no`, giới hạn task mở, SLA. **Làm sớm, B và C phụ thuộc** | `feature/tasks` | P1 |
| D-02 | Giao task thủ công và tự động, điều chuyển, đổi ưu tiên, hủy, task bị từ chối (TK-1.1 đến TK-1.6) | `feature/tasks` | P1 |
| D-03 | Engine phê duyệt: tính tầng theo Z, X, Y và người lập, D1 đến D3, SoD, lịch sử, khóa phiếu đang mở, leo thang khi quá SLA (kích hoạt tay trong demo) | `feature/approvals` | P1 |
| D-04 | Thủ kho duyệt: hàng chờ, chênh lệch nhận, chênh lệch kiểm kê, yêu cầu đếm lại, chuyển D2, đề xuất điều chỉnh (TK-3.1 đến TK-4.4) | `feature/approvals` | P1 |
| D-05 | Quản lý và BGĐ duyệt D2, D3; thực thi sau duyệt (ghi tồn qua `inventory`, đẩy ERP mock) (QL-7.1 đến QL-7.6) | `feature/approvals` | P1 |
| D-06 | Kiểm kê: phiếu, khóa vị trí, snapshot, đếm mù, so với Z, đếm lại tới giới hạn, tự đóng phiếu | `feature/cycle-count` | P1 |
| D-07 | Dashboard cơ bản: thẻ số task (TK-2.1), tồn, đơn trong ngày cho BGĐ; cảnh báo đơn giản trong app | `feature/dashboard` | P2 |
| D-08 | Client cho `thukho`, `quanly`, `bgd`, `nv-kiemke` | các nhánh của D | P1 |

## 9. Tiêu chí hoàn thành (Definition of Done)

Một việc chỉ được coi là xong khi đủ các mục sau:

- Tên file, hàm, biến theo mục 4; `ruff`, `black`, `mypy` không báo lỗi.
- Mỗi endpoint có khai báo mã quyền và đã thử với ít nhất một vai trò đúng và một vai trò sai.
- Hành động ghi có `audit_logs`; thay đổi tồn đi qua `apply_movement`.
- Có test đơn vị cho service (đặc biệt: sổ cái tồn, FEFO, tính tầng duyệt) và test tích hợp cho API chính.
- Cập nhật hợp đồng API trong `docs/api/<module>.md`.
- PR đã được review chéo, CI xanh, gộp vào `develop`.
- Chạy được đúng đoạn tương ứng trong kịch bản demo ở mục 6.2.

* Khi đổi schema hoặc hàm DB: nạp lại schema v4.1 và patch v4.2.1 trên DB trống, chạy patch lần 2, rồi chạy `wms_smoke_test_v4_2_1.sql`; cả ba bước phải không lỗi.

- Nghiệp vụ hoàn tất chứng từ có ghi tồn phải có test rollback; đối tượng có `version_no` phải có test 409; không ghi token hay mật khẩu vào log (chuẩn API, mục 8 và 9).

## 10. Còn thiếu gì: gợi ý để bản đặc tả hoàn chỉnh hơn

Trạng thái ngày 13/11/2026: **10.1 đã xử lý xong** bằng patch v4.2.1 và đã kiểm thử; **10.2 chưa làm**, vẫn là danh sách việc cần làm, cách làm ở cột cuối.

### 10.1 Chỗ lệch giữa các tài liệu nguồn (đã xử lý bằng patch v4.2.1)

Sơ đồ drawio v2 nhắc tới một số đối tượng mà file SQL v4.1 **chưa có**. Patch v4.2.1 đã bổ sung đủ các mục sau:

- Bảng: `inventory_allocations`, `package_lines`, `return_order_lines`.
- Hàm/trigger: `fn_resolve_approval_tier`, `fn_approval_mirror_status`.
- Giá trị và cột: trạng thái pallet `REJECTED_PENDING_RETURN`, loại GI `CUSTOMER_RETURN_BACK`, cột `grn_tolerance_apply`, cột `pick_lines.staged_location_id`.

**Kết quả kiểm chứng:** nạp schema v4.1 rồi patch v4.2.1 trên PostgreSQL 16 không lỗi, chạy patch thêm lần 2 và lần 3 vẫn không lỗi, ra 62 bảng. Bộ kiểm thử `wms_smoke_test_v4_2_1.sql` (sổ cái tồn, phân luồng tầng duyệt, ERP đổi/hủy đơn, leo thang SLA, xác thực lại, trigger PO, duyệt hết hạn) đạt toàn bộ. Patch v4.2.1 cũng sửa 4 lỗi của v4.2: chạy lại được, phần trăm đầy của vị trí, chú thích sai, đánh dấu duyệt hết hạn. **Nguồn sự thật duy nhất** là `schema.sql` cùng patch v4.2.1, nạp bằng `psql`; thay đổi về sau mới đi qua Alembic. Còn lại của 10.1: gắn tag `schema-v4.2.1` rồi đóng băng. Slide ghi 13 quy tắc \[Q\] cần chốt, SQL ghi 27, vẫn cần bảng đối chiếu (nằm ở mục 5 của 10.2).

### 10.2 Các mục còn thiếu

Cả 16 mục dưới đây **chưa làm**. Hai mục đã có một phần: mục 4 (seed) mới có dữ liệu mẫu tối thiểu trong file kiểm thử, chưa có seed demo đầy đủ; mục 9 (giao diện tích hợp ngoài) đã có phần DB (`integration_sync_logs`, hàm nhận đổi/hủy đơn từ ERP), còn thiếu interface và mock bằng Python.

| # | Còn thiếu | Vì sao cần | Gợi ý cách làm |
| --- | --- | --- | --- |
| 1 | **Chốt công nghệ** (đặc biệt dạng client: web mobile hay desktop) | Mọi người code khác hướng sẽ phải làm lại | Họp 30 phút, mỗi quyết định ghi một file ADR ngắn (bối cảnh, lựa chọn, lý do) trong `docs/adr/` |
| 2 | **Hợp đồng API** từng module | B, C, D phải gọi nhau và client gọi server | Làm theo hướng hợp đồng trước: chủ module viết danh sách endpoint, request, response, mã lỗi vào `docs/api/`, người dùng module xem và góp ý rồi mới code; dùng OpenAPI do FastAPI tự sinh để đối chiếu |
| 3 | **Máy trạng thái** của GRN, đơn xuất, pallet, task, phê duyệt | Các ENUM trong SQL đã có nhưng chưa có bảng chuyển trạng thái hợp lệ | Với mỗi đối tượng, vẽ một bảng: trạng thái hiện tại, hành động, ai được làm, trạng thái kế, tác dụng phụ (ghi tồn, tạo task); đưa vào test |
| 4 | **Dữ liệu mẫu và tài khoản demo** | Không có dữ liệu thì không chạy được kịch bản | Viết `database/seeds/` và `scripts/seed_demo.py`: 1 kho, vài zone, 30 đến 50 vị trí, 10 SKU (có hàng hạn dùng ngắn để thử FEFO), 1 PO, 1 SO, 9 tài khoản mỗi vai trò một người |
| 5 | **Quy tắc \[Q\] mặc định cho demo** | Nhiều quy tắc còn là câu hỏi mở | Dùng giá trị mặc định đã có trong `warehouse_configs`, ghi vào một bảng «giả định demo» để cả nhóm và giảng viên/khách hàng thấy |
| 6 | **Mã lỗi và chuẩn phản hồi** | Client cần hiển thị lỗi thống nhất | Một file `error_codes.md`: mã, HTTP status, thông điệp tiếng Việt, ai bắt; response lỗi luôn có `code`, `message`, `details` |
| 7 | **Đồng thời và nhất quán tồn** | Hai người cùng thao tác một vị trí hoặc task | Dùng `version_no` (optimistic locking) và transaction khi gọi `apply_movement`; viết test hai phiên chạy song song |
| 8 | **Bảo mật** | Có nhiều vai trò, có duyệt tiền | Băm mật khẩu, JWT hết hạn ngắn, giới hạn đăng nhập sai, SSO giả lập (`SSO_LDAP` và `LOCAL_SEASONAL`), xác thực lại khi giá trị từ `reauth_min_amount` |
| 9 | **Giao diện tích hợp ngoài** (ERP, TMS, máy quét, máy in) | Chưa có hệ thống thật | Định nghĩa interface (ví dụ `ErpGateway`) cùng bản mock; sau này thay bằng bản thật mà không đổi service |
| 10 | **Chiến lược kiểm thử** | Nhóm 4 người dễ làm hỏng code của nhau | Đơn vị cho service, tích hợp với DB test (Docker), e2e theo kịch bản demo; đặt mục tiêu độ phủ riêng cho `inventory` và `approvals` |
| 11 | **CI/CD và môi trường** | Đảm bảo ai cũng chạy giống nhau | GitHub Actions chạy lint, kiểm kiểu, test; `docker-compose` cho Postgres; `pre-commit` chặn code sai format trước khi commit |
| 12 | **Quản lý công việc** | Bảng phân công cần theo dõi được | Dùng GitHub Projects hoặc bảng Kanban: mỗi mã việc (A-01, B-04...) là một Issue, nhãn theo module và ưu tiên, họp đứng 10 phút mỗi ngày |
| 13 | **Giao diện (UX) cho điện thoại** | Người dùng kho dùng một tay, màn hình nhỏ | Làm wireframe 5 màn chính (nhận hàng, cất, soạn, đóng gói, kiểm kê); nút lớn, quét mã là thao tác chính; có thể dựng từ các hàm trong slide |
| 14 | **Yêu cầu phi chức năng** | Chưa có số đo cụ thể | Ghi vài chỉ tiêu: thời gian phản hồi API, số người dùng đồng thời cho demo, múi giờ (`TIMESTAMPTZ`), ngôn ngữ giao diện tiếng Việt, sao lưu DB |
| 15 | **Rủi ro và phương án dự phòng** | Leader vừa code vừa review dễ quá tải | Lập bảng rủi ro: A quá tải (chuyển A-07 sang D hoặc giảm P3), `inventory` trễ (B, C dùng stub), schema đổi giữa chừng (đóng băng schema sau giai đoạn 1) |
| 16 | **Hướng dẫn cho người mới** | Dễ bỏ sót, nhất là khi nhóm đổi người | `README.md` có đúng các bước: cài, chạy DB, nạp seed, chạy server, chạy client, chạy test |
