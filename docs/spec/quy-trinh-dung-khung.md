# Quy trình dựng khung dự án ABEST WMS và prompt giao cho agent

Nov 13, 2026 · @binh

Từ giờ đến khi xong khung để 4 người viết module, bạn làm 7 việc thủ công (khoảng 3 giờ, chủ yếu là tài khoản, quyết định và quyền merge); 9 bước dựng kỹ thuật giao cho agent, mỗi bước bắt buộc có test và báo cáo. Prompt dùng được với agent nào chạy được shell và git (Claude Code, Codex, Cursor...).

## 1. Thứ tự và phân chia

| Thứ tự | Mã | Ai | Việc | Đầu ra |
| --- | --- | --- | --- | --- |
| 1 | U1 | **Bạn** | Chuẩn bị máy và đăng nhập GitHub | Máy chạy được agent, Docker, Git |
| 2 | U2 | **Bạn** | Chốt công nghệ | Quyết định cuối |
| 3 | U3 | **Bạn** | Tạo repo, nhánh `main` và `develop` | Repo trống trên GitHub |
| 4 | U4 | **Bạn** | Gom tài liệu và file SQL vào repo | Commit đầu tiên trên `develop` |
| 5 | AG1 | Agent | Khung thư mục, README, cấu hình chất lượng code | Cây thư mục đúng đặc tả |
| 6 | AG2 | Agent | Docker Postgres, nạp DB, seed, test DB | `reset_db.sh` một lệnh |
| 7 | AG3 | Agent | Lõi server: envelope, lỗi, ENUM, health | Server chạy được |
| 8 | AG4 | Agent | Auth và phân quyền RBAC | 9 vai trò đăng nhập, chặn đúng quyền |
| 9 | AG5 | Agent | Giao diện hàm `inventory` và `tasks` | B, C gọi được tồn kho và task |
| 9 | AG6 | Agent | Khung client web (chạy song song với AG5) | Đăng nhập, menu theo quyền, trang mẫu |
| 10 | AG7 | Agent | Khung 8 module, ORM, router 501, test kiến trúc | Mỗi người mở nhánh là code được |
| 11 | AG8 | Agent | CI và `make ci` | Kiểm tra tự động trên mỗi PR |
| 12 | AG9 | Agent (phiên mới) | Kiểm tra độc lập từ bản clone sạch | Kết luận «Sẵn sàng giao module» hay không |
| sau mỗi AG | U5 | **Bạn** | Nghiệm thu và merge PR | `develop` luôn xanh |
| 13 | U6 | **Bạn** | Bảo vệ nhánh, thêm thành viên, tạo nhánh, gắn tag | Nhóm có quyền và nhánh riêng |
| 14 | U7 | **Bạn** | Giao việc cho nhóm | Mọi người bắt đầu code module |

AG5 và AG6 làm song song được; các bước còn lại làm lần lượt vì bước sau dựa vào bước trước.

## 2. Việc bắt buộc bạn làm

| Mã | Việc | Vì sao không giao agent |
| --- | --- | --- |
| U1 | Cài Git, Docker Desktop, Python 3.11 trở lên, agent. Chạy `gh auth login` để agent mở PR được. **Tự đăng nhập, không dán token vào chat hay prompt.** | Liên quan tài khoản và bí mật |
| U2 | Đọc mục 1 của tài liệu chuẩn công nghệ và API, quyết «chốt». Muốn đổi gì thì báo trước khi giao AG1, vì agent bám tài liệu. | Chỉ bạn có quyền quyết |
| U3 | Tạo repo private `abest-wms` trên GitHub, nhánh mặc định `main`, tạo thêm `develop`, clone về máy. | Cần tài khoản của bạn |
| U4 | Gom đầu vào vào repo, đúng tên file ở bảng dưới, commit lên `develop`. Hai tài liệu Google Doc cần xuất ra Markdown hoặc PDF: có thể nhờ mình xuất Markdown rồi tải về. | Chỉ bạn có file gốc |
| U5 | Sau mỗi bước agent: mở `docs/reports/<mã-bước>.md`, chạy `make ci`, đọc mục «Giả định» và «Chưa làm», rồi merge PR vào `develop`. | Bạn là người chịu trách nhiệm cuối, và merge là quyền của bạn |
| U6 | Sau AG9: bật bảo vệ `main` và `develop` (cần PR, không push thẳng), thêm 3 thành viên quyền Write, chạy `scripts/create_branches.sh`, bật GitHub Actions, gắn tag `v0.0-skeleton`. | Cần quyền chủ repo |
| U7 | Gửi nhóm bảng phân công (mục 8 đặc tả), link README và `docs/api/<module>.md` của từng người. | Việc giao tiếp của leader |

Tên file đầu vào cho U4 (đúng tên, vì prompt tham chiếu):

| File gốc của bạn | Đặt vào repo thành |
| --- | --- |
| `wms_database_schema_v4_1.sql` | `database/schema.sql` |
| `wms_database_patch_v4_2_1.sql` | `database/patch_v4_2_1.sql` |
| `wms_smoke_test_v4_2_1.sql` | `database/tests/smoke_test.sql` |
| `WMS_Mobile_Phân_rã_chức_năng_v3_máy_chiếu.pptx` | `docs/source/wms_decomposition_v3.pptx` |
| `wms_workflows_v2.drawio` | `docs/source/wms_workflows_v2.drawio` |
| Đặc tả dự án ABEST WMS (xuất ra) | `docs/spec/dac-ta-du-an.md` |
| Chuẩn công nghệ và hợp đồng API (xuất ra) | `docs/spec/chuan-api-cong-nghe.md` |

## 3. Cách giao một bước cho agent

1. Mở phiên agent mới trong thư mục repo, chạy `git checkout develop && git pull`.
2. Dán **khối bối cảnh chung** (mục 4), rồi dán prompt của bước đó.
3. Chờ agent xong, mở báo cáo trong `docs/reports/`, chạy `make ci`, làm theo bảng nghiệm thu ở cuối tài liệu.
4. Đạt thì merge PR rồi sang bước kế; chưa đạt thì dán lại phần lỗi cho agent sửa. Sửa hai lần vẫn không được thì gửi mình báo cáo và log.
5. Không giao hai bước cùng lúc, trừ AG5 và AG6.

## 4. Khối bối cảnh chung (dán vào đầu mọi prompt)

```text
Bạn là kỹ sư phần mềm trong dự án ABEST WMS (hệ thống quản lý kho). Repo là thư mục hiện tại.

Tài liệu bắt buộc đọc trước khi làm:
- docs/spec/dac-ta-du-an.md (kiến trúc, cấu trúc thư mục, quy cách đặt tên, phân quyền)
- docs/spec/chuan-api-cong-nghe.md (công nghệ chốt, quy ước API, mã lỗi, danh mục endpoint)
- database/schema.sql và database/patch_v4_2_1.sql (CSDL, ĐÃ ĐÓNG BĂNG)

Quy tắc cứng:
1. KHÔNG sửa database/schema.sql, database/patch_v4_2_1.sql, database/tests/smoke_test.sql. Nếu cần đổi DB thì dừng và ghi vào báo cáo.
2. KHÔNG tự bịa tên bảng, cột, hàm DB: đọc từ file SQL. Điều gì không chắc thì ghi vào mục Giả định của báo cáo.
3. Làm trên nhánh riêng chore/<mã-bước> tách từ develop; commit nhỏ theo Conventional Commits; KHÔNG push vào main hoặc develop; mở PR vào develop nếu có gh, nếu không thì dừng ở commit.
4. Không ghi bí mật (mật khẩu, token) vào repo; chỉ dùng .env.example.
5. Định danh viết bằng tiếng Anh, chú thích và docstring tiếng Việt. Tuân thủ mục 4 đặc tả (đặt tên) và mục 2.3 (phụ thuộc giữa các lớp); mục 7 đến 9 của chuẩn API (phân tầng, bảo mật, giao dịch).
6. Trước khi báo hoàn thành PHẢI chạy toàn bộ test của bước và dán kết quả thật vào báo cáo. Test đỏ thì sửa, không được báo xong.
7. Cuối bước ghi báo cáo vào docs/reports/<mã-bước>.md đúng mẫu: Mục tiêu; Đã làm (danh sách file); Cách chạy lại; Kết quả test (lệnh và kết quả thật); Giả định đã đặt; Chưa làm hoặc rủi ro; Đề xuất bước tiếp.
8. Thiếu thông tin hoặc bị chặn thì DỪNG và hỏi, không đoán.
```

## 5. AG1: khung repo

Phụ thuộc: U1 đến U4.

```text
[Dán khối bối cảnh chung]
Mã bước: ag1-skeleton. Nhánh: chore/ag1-skeleton.
Nhiệm vụ: dựng cấu trúc repo theo mục 3 đặc tả.

1. Tạo đúng cây thư mục mục 3: server/app/{core,shared,modules,integrations}, server/tests/{unit,integration,e2e,architecture}, client/app/{core,static,templates/_base,modules}, scripts, docs/{adr,api,reports}, .github. Thư mục rỗng có __init__.py hoặc .gitkeep hợp lý.
2. Tạo README.md (cài đặt, chạy DB, chạy server, chạy client, chạy test, mục Quy ước trỏ tới đặc tả), CONTRIBUTING.md (quy trình git mục 7: nhánh, commit, PR, các file chỉ leader sửa), .gitignore (mở rộng file có sẵn, giữ nguyên các dòng cũ), .env.example, server/requirements.txt và client/requirements.txt (ghim phiên bản cụ thể, đã kiểm tra cài được), pyproject.toml cấu hình ruff/black/mypy (dòng tối đa 100), .pre-commit-config.yaml, Makefile với các target: install, db-reset, lint, typecheck, test, ci (lint + typecheck + test), run-server, run-client.
3. Tạo .github/CODEOWNERS (dùng placeholder @A @B @C @D để người dùng thay) và .github/PULL_REQUEST_TEMPLATE.md (checklist Definition of Done mục 9).
4. Viết scripts/check_structure.py: kiểm mọi thư mục và file bắt buộc của mục 3 tồn tại, in danh sách thiếu, thoát mã khác 0 nếu thiếu.

Test bắt buộc (dán kết quả thật vào báo cáo):
(a) python scripts/check_structure.py thoát mã 0.
(b) Xóa virtualenv, tạo lại, make install thành công.
(c) make lint và make typecheck chạy không lỗi.
(d) pytest chạy được với ít nhất 1 test cấu trúc và pass.
Báo cáo: docs/reports/ag1-skeleton.md.
```

## 6. AG2: DB, seed và test DB

Phụ thuộc: AG1 đã merge.

```text
[Dán khối bối cảnh chung]
Mã bước: ag2-database. Nhánh: chore/ag2-database.
Nhiệm vụ: nạp DB và dữ liệu mẫu bằng một lệnh, có test.

1. docker-compose.yml: Postgres 16, volume, healthcheck, biến lấy từ .env (.env.example có giá trị dev mặc định).
2. scripts/reset_db.sh (bash, set -euo pipefail): chờ Postgres sẵn sàng, DROP và CREATE database, nạp theo thứ tự database/schema.sql, database/patch_v4_2_1.sql, rồi mọi file database/seeds/*.sql theo số thứ tự.
3. scripts/run_db_tests.sh: tạo một DB TẠM riêng (không dùng DB chính, vì smoke test chèn dữ liệu thử), nạp schema và patch, chạy database/tests/smoke_test.sql, chạy patch lần 2 để chứng minh chạy lại được, chạy database/tests/test_seed.sql trên DB chính đã seed, rồi xóa DB tạm.
4. Seed trong database/seeds/ (chạy lại được, dùng ON CONFLICT DO NOTHING hoặc reset trước):
   - 01_roles_permissions.sql: 9 vai trò đúng role_code (nv-nhan, nv-cat, nv-soan, nv-dongoi, nv-kiemke, thukho, quanly, bgd, admin), bảng permissions và role_permissions theo ma trận quyền: mục 5.3 đặc tả và các slide ma trận phân quyền trong docs/source/wms_decomposition_v3.pptx. Dùng đúng mã quyền ghi trên slide (NH-1, TK-3.2...). Mục nào slide không rõ thì ghi vào Giả định.
   - 02_master_demo.sql: 1 kho kèm warehouse_configs mặc định, 3 zone (dùng đúng giá trị ENUM của schema), 30 vị trí có barcode, 10 SKU (2 SKU có hạn dùng), box_types, 3 khách hàng, 3 nhà cung cấp, các reason_codes cần cho demo.
   - 03_users_demo.sql: 9 tài khoản demo, mỗi vai trò một người. Mật khẩu demo ghi trong README; hash bcrypt sinh bằng scripts/make_password_hash.py, không hard-code hash tay.
5. Viết database/tests/test_seed.sql (DO + RAISE EXCEPTION): đúng 9 vai trò; mỗi vai trò có đúng 1 user active; mỗi role_code có ít nhất 1 dòng role_permissions; đúng 1 kho; ít nhất 30 vị trí; ít nhất 10 SKU.

Test bắt buộc (dán kết quả thật vào báo cáo):
(a) scripts/reset_db.sh chạy 2 lần liên tiếp đều thành công.
(b) scripts/run_db_tests.sh in dòng TẤT CẢ BÀI KIỂM THỬ ĐẠT của smoke test, patch lần 2 không lỗi, test_seed.sql pass.
(c) make ci vẫn xanh.
Báo cáo: docs/reports/ag2-database.md.
```

## 7. AG3: lõi server

Phụ thuộc: AG1 và AG2 đã merge.

```text
[Dán khối bối cảnh chung]
Mã bước: ag3-server-core. Nhánh: chore/ag3-server-core.
Nhiệm vụ: dựng lõi server theo mục 1 đến 3 của chuẩn API.

1. server/app/main.py: tạo FastAPI với tiền tố /api/v1; tự nạp biến router của mọi file app/modules/*/routers.py nếu có; endpoint GET /health trả trạng thái app và kết nối DB.
2. core/config.py (pydantic-settings đọc .env), core/database.py (SQLAlchemy 2 và psycopg 3, session dependency, một transaction mỗi request: commit khi thành công, rollback khi lỗi).
3. core/responses.py: phản hồi thành công gồm data và meta.request_id; danh sách thêm meta.page, meta.page_size, meta.total; middleware gắn request_id (header X-Request-ID).
4. core/exceptions.py: BusinessError(code, message, http_status, details); handler chung cho BusinessError, lỗi kiểm dữ liệu (422 VALIDATION_ERROR) và lỗi chưa biết (500, không lộ chi tiết). Hàm translate_db_error() đổi lỗi Postgres sang mã ở bảng mã lỗi mục 3 chuẩn API: BAN_GHI_BAT_BIEN, DON_BI_DONG_BANG, THIEU_XAC_THUC_LAI, vi phạm check qty_available (INVENTORY_INSUFFICIENT_QTY), vi phạm SoD (SOD_VIOLATION). Tìm thông điệp thật của các lỗi này trong schema và patch, không đoán.
5. shared/enums.py: ENUM Python khớp 100% với ENUM của DB, SINH bằng scripts/gen_enums.py đọc từ DB đang chạy (không gõ tay, chạy lại được).
6. Logging JSON có request_id; tuyệt đối không ghi JWT, mật khẩu, header Authorization hay cookie vào log.

Test bắt buộc (pytest, DB thật qua docker; dán kết quả thật vào báo cáo):
(a) /health trả 200 và DB ok.
(b) Phản hồi thành công và phản hồi lỗi đúng mẫu mục 2 chuẩn API; request_id có trong mọi phản hồi.
(c) Mỗi lỗi DB gây ra bằng SQL thật (UPDATE inventory_transactions; trừ quá tồn; sửa đơn đang bị đóng băng; duyệt từ ngưỡng xác thực lại mà thiếu reauth; người lập tự duyệt) đều ra đúng mã và đúng HTTP.
(d) server/tests/architecture/test_enums_match_db.py: so ENUM Python với pg_enum, lệch thì fail.
(e) make ci xanh.
(f) Bộ lọc log che các trường authorization, password, token, cookie: ghi một log chứa các trường này và khẳng định đầu ra không lộ giá trị.
(g) Transaction: một request ghi 2 bước mà bước 2 lỗi thì bước 1 bị rollback, không để lại dòng nào.
Báo cáo: docs/reports/ag3-server-core.md.
```

## 8. AG4: xác thực và phân quyền

Phụ thuộc: AG3 đã merge.

```text
[Dán khối bối cảnh chung]
Mã bước: ag4-auth-rbac. Nhánh: chore/ag4-auth-rbac.
Nhiệm vụ: module auth và hạ tầng phân quyền.

1. server/app/modules/auth/ đủ 5 file (models, schemas, repositories, services, routers) và __init__.py. Endpoint: POST /auth/login, GET /auth/me (trả người dùng, role_code, kho, danh sách quyền gồm permission_code và access_type), POST /auth/change-password.
2. JWT HS256 hết hạn sau 8 giờ, claim sub, role_code, warehouse_id; mật khẩu bcrypt. Sai mật khẩu trả AUTH_INVALID_CREDENTIALS, token hết hạn trả AUTH_TOKEN_EXPIRED. Nếu schema có cột đếm lần sai và ngưỡng khóa thì khóa tài khoản theo đó; nếu không có thì bỏ qua và ghi vào báo cáo.
3. core/rbac.py: dependency require_permission(mã quyền) trả về access_type; helper enforce_warehouse_scope; helper cho X_OWN và V_OWN (lọc theo người dùng).
4. core/audit.py: ghi audit_logs cho các thao tác bắt buộc ở mục 9.3 chuẩn API (đăng nhập, tạo, gửi, duyệt, từ chối chứng từ, biến động tồn, giao, nhận, hủy task, đổi hoặc hủy đơn ERP).
5. Một router thử nghiệm CHỈ nằm trong thư mục test (không đưa vào bản chạy thật) để kiểm tra phân quyền.

Test bắt buộc (dán kết quả thật vào báo cáo):
(a) 9 tài khoản seed đều đăng nhập được; /auth/me trả đúng role và danh sách quyền khác nhau giữa các vai trò.
(b) Test tham số hóa theo từng cặp (vai trò, quyền) trong role_permissions: endpoint thử trả 200 nếu có quyền và 403 FORBIDDEN nếu không; riêng admin phải bị chặn mọi quyền nghiệp vụ.
(c) Sai mật khẩu, token hỏng, token hết hạn đều trả đúng mã lỗi.
(d) Phạm vi kho: tạo kho thứ hai trong test, tài khoản của kho này không thấy dữ liệu của kho kia.
(e) audit_logs có dòng mới sau một hành động ghi.
(f) Đổi mật khẩu rồi đăng nhập bằng mật khẩu mới.
(g) make ci xanh.
(h) Đăng nhập thành công và thất bại rồi đọc toàn bộ log: không chứa token, mật khẩu hay header Authorization.
Báo cáo: docs/reports/ag4-auth-rbac.md.
```

## 9. AG5: giao diện hàm inventory và tasks

Phụ thuộc: AG4 đã merge. Làm song song được với AG6.

```text
[Dán khối bối cảnh chung]
Mã bước: ag5-inventory-tasks. Nhánh: chore/ag5-inventory-tasks.
Mục tiêu: B và C gọi được tồn kho và task ngay. Bản này là lớp bọc mỏng quanh hàm DB, phần còn lại do chủ module hoàn thiện sau.

1. server/app/modules/inventory/: services.apply_movement(...) và services.transfer_inventory(...) bọc fn_apply_inventory_movement và fn_transfer_inventory (xem đúng chữ ký trong database/patch_v4_2_1.sql), dịch lỗi bằng translate_db_error; repositories.py chứa lệnh SQL; routers.py có GET /inventory/balances, /inventory/transactions, /lots, /pallets, /pallets/{id}, /locations/{id}/stock theo mục 4.3 chuẩn API, đúng cột Vai trò; __init__.py chỉ export apply_movement và transfer_inventory.
2. server/app/modules/tasks/: bản tối thiểu chạy được gồm create_task, assign_task, accept_task, reject_task, complete_task (service và repository) trên bảng tasks, kiểm trạng thái hợp lệ và version_no; router theo mục 4.7; __init__.py export các hàm; đánh dấu TODO rõ ràng cho phần chủ module hoàn thiện (giao tự động, SLA, điều chuyển).

Test bắt buộc (dán kết quả thật vào báo cáo):
(a) apply_movement RECEIVE hai lần cùng vị trí: tồn cộng đúng, version_no tăng.
(b) Trừ quá tồn: BusinessError INVENTORY_INSUFFICIENT_QTY.
(c) transfer_inventory giữ nguyên bucket ALLOCATED.
(d) GET /inventory/balances lọc đúng, và vai trò nv-kiemke và admin bị 403.
(e) tasks: tạo, giao, nhận, hoàn tất theo đúng thứ tự; sai thứ tự trả INVALID_STATE; sai version_no trả VERSION_CONFLICT; nhân viên chỉ thấy task của mình.
(f) make ci xanh.
Báo cáo: docs/reports/ag5-inventory-tasks.md.
```

## 10. AG6: khung client

Phụ thuộc: AG4 đã merge. Làm song song được với AG5.

```text
[Dán khối bối cảnh chung]
Mã bước: ag6-client. Nhánh: chore/ag6-client.
Nhiệm vụ: dựng khung client web.

1. client/app: FastAPI + Jinja2 + HTMX + Tailwind (CDN), mobile-first.
2. core/api_client.py (httpx, gắn Authorization từ cookie phiên, đọc phản hồi theo mẫu chuẩn API, ném ClientApiError mang code và message); core/session.py (token trong cookie httpOnly, SameSite=Lax); core/auth_guard.py (chưa đăng nhập thì chuyển /login; 403 thì hiện trang không đủ quyền). Thêm middleware chống CSRF bản gọn theo mục 8 chuẩn API: chặn POST, PUT, PATCH, DELETE có Origin hoặc Referer không trùng host client; request HTMX phải có header HX-Request: true; cookie phiên HttpOnly, SameSite=Lax, Secure theo cấu hình.
3. templates/_base: layout, menu dựng từ GET /auth/me theo quyền (ẩn mục không có quyền), vùng hiển thị lỗi và toast dùng chung; trang /login; trang mẫu /inventory (bảng tồn từ GET /inventory/balances) tách view, controller và template đúng MVC mục 2.1 để các module khác bắt chước.
4. client/app/modules/<module>/ cho 8 module: thư mục kèm views.py có router rỗng; chưa làm giao diện.

Test bắt buộc (TestClient, dùng server thật chạy qua docker; dán kết quả thật vào báo cáo):
(a) Đăng nhập đúng và sai.
(b) Chưa đăng nhập vào /inventory thì bị chuyển sang /login.
(c) Test tham số hóa 9 vai trò: menu hiện đúng mục theo quyền.
(d) Lỗi API 403 và 409 hiện đúng thông báo trên giao diện.
(e) Mở /inventory bằng tài khoản được phép thấy dữ liệu seed.
(f) Nếu cài được playwright: chụp ảnh trang /login và /inventory ở khung rộng 390px, lưu vào docs/reports/assets/ag6/.
(g) make ci xanh.
(h) POST có Origin lạ bị từ chối; POST HTMX thiếu header HX-Request bị từ chối; cookie phiên có HttpOnly và SameSite.
Báo cáo: docs/reports/ag6-client.md.
```

## 11. AG7: khung 8 module

Phụ thuộc: AG5 và AG6 đã merge. Đây là bước dài nhất.

```text
[Dán khối bối cảnh chung]
Mã bước: ag7-module-scaffold. Nhánh: chore/ag7-module-scaffold.
Mục tiêu: B, C, D mở nhánh là code được ngay, không phải dựng lại cấu trúc.

1. Với mỗi module master_data, inbound, outbound, approvals, cycle_count, dashboard, integrations (auth, inventory, tasks đã có): server/app/modules/<m>/ có đủ models.py, schemas.py, repositories.py, services.py, routers.py, __init__.py (chỉ export hàm công khai). models.py định nghĩa ORM cho mọi bảng thuộc module đó theo bảng module ở mục 6.1 đặc tả, đọc từ schema để khớp tên cột và kiểu (dùng Numeric cho NUMERIC). routers.py khai báo đủ endpoint của mục 4 chuẩn API, trả 501 Not Implemented kèm mã quyền đã khai báo, để OpenAPI hiện đủ danh mục.
2. Mỗi module có server/tests/unit/<m>/ và server/tests/integration/<m>/ với 1 test mẫu chạy được (ví dụ router trả 501 và đúng quyền).
3. docs/api/<m>.md cho từng module: sinh từ mẫu mục 5 chuẩn API, liệt kê mọi endpoint của mục 4, phần body và phản hồi để trống đánh dấu TODO chủ module.
4. client/app/modules/<m>/ có views.py và templates/ placeholder.
5. server/tests/architecture/test_layering.py kiểm bằng AST: routers.py chỉ import services, schemas và core, không import sqlalchemy hay models; services chỉ import repositories, models, schemas, sqlalchemy của chính module và module khác qua __init__ (không import trực tiếp models hoặc repositories của module khác); lời gọi hàm fn_* chỉ xuất hiện trong repositories.py, và chỉ module inventory được gọi fn_apply_inventory_movement và fn_transfer_inventory.
6. scripts/create_branches.sh (có tùy chọn --dry-run, CHƯA chạy thật): tạo và push feature/core-auth, feature/inventory, feature/integrations-mock, feature/master-data, feature/inbound, feature/outbound, feature/tasks, feature/approvals, feature/cycle-count, feature/dashboard từ develop.

Test bắt buộc (dán kết quả thật vào báo cáo):
(a) test_layering.py pass.
(b) Một test sinh OpenAPI và khẳng định mọi endpoint ở mục 4 chuẩn API đều có trong OpenAPI (danh sách đọc từ docs/api/*.md).
(c) Mọi bảng của mục 6.1 đều có model ORM (test đối chiếu với information_schema).
(d) create_branches.sh --dry-run in đúng danh sách nhánh.
(e) make ci xanh.
Báo cáo: docs/reports/ag7-module-scaffold.md.
```

## 12. AG8: CI

Phụ thuộc: AG7 đã merge.

```text
[Dán khối bối cảnh chung]
Mã bước: ag8-ci. Nhánh: chore/ag8-ci.
Nhiệm vụ: kiểm tra tự động trên mỗi PR.

1. .github/workflows/ci.yml chạy khi có PR vào develop hoặc main: ruff, black --check, mypy; khởi tạo Postgres 16 (service container); chạy scripts/run_db_tests.sh; rồi pytest (unit, integration, architecture); cache pip.
2. make ci chạy đúng chuỗi lệnh đó ở máy local.
3. Cập nhật README: mục CI và huy hiệu trạng thái.

Test bắt buộc (dán kết quả thật vào báo cáo):
(a) make ci chạy thành công ở máy local.
(b) Kiểm cú pháp workflow bằng actionlint nếu cài được, nếu không thì python yaml.safe_load.
(c) Ghi vào báo cáo cách xem kết quả CI đầu tiên trên GitHub sau khi push (agent không thể tự kiểm được bước này).
Báo cáo: docs/reports/ag8-ci.md.
```

## 13. AG9: kiểm tra độc lập

Phụ thuộc: mọi PR AG1 đến AG8 đã merge vào `develop`. **Mở phiên agent mới, không dùng lại phiên cũ**, để agent không dựa vào trí nhớ.

```text
[Dán khối bối cảnh chung, nhưng BỎ quy tắc 3 và 7; quy tắc mới: KHÔNG sửa bất kỳ file nào ngoài docs/reports/ag9-verify.md]
Mã bước: ag9-verify.
Vai trò: người kiểm tra độc lập. Clone sạch nhánh develop vào một thư mục mới và CHỈ làm theo README.md từng bước, không dùng hiểu biết nào khác.

1. Ghi lại mọi chỗ README sai hoặc thiếu khiến không chạy được.
2. Chạy: make install, make db-reset, scripts/run_db_tests.sh, make ci; chạy server và client; đăng nhập client bằng cả 9 tài khoản seed và ghi menu mỗi vai trò thấy.
3. Thử phá luật: gọi từ vai trò nv-nhan một endpoint của thukho (phải 403); đưa token hỏng; gửi 2 request ghi cùng version_no (chỉ 1 thành công); trừ tồn vượt mức.
4. Kiểm checklist bàn giao: cây thư mục đúng mục 3 đặc tả; 9 vai trò đăng nhập được; require_permission hoạt động; apply_movement và transfer_inventory chạy; giao diện hàm tasks chạy; OpenAPI có đủ endpoint ở mục 4 chuẩn API; ENUM Python khớp DB; CI xanh.

Kết quả duy nhất: docs/reports/ag9-verify.md gồm bảng Đạt hoặc Không đạt cho từng mục kèm bằng chứng (lệnh và kết quả thật), danh sách lỗi theo mức nghiêm trọng, và kết luận ghi đúng một trong hai: SẴN SÀNG GIAO MODULE hoặc CHƯA SẴN SÀNG kèm lý do.
```

## 14. Bạn nghiệm thu nhanh sau mỗi bước (U5)

| Bước | Bạn chạy hoặc xem | Đạt khi |
| --- | --- | --- |
| AG1 | `python scripts/check_structure.py` và `make ci` | Thoát mã 0 |
| AG2 | `scripts/reset_db.sh` hai lần, rồi `scripts/run_db_tests.sh` | Cả hai thành công, có dòng TẤT CẢ BÀI KIỂM THỬ ĐẠT |
| AG3 | `make run-server`, mở `http://localhost:8000/health` và `/docs` | `/health` báo DB ok; `/docs` hiện Swagger |
| AG4 | Trong Swagger đăng nhập bằng `nv-nhan`, gọi `/auth/me`, rồi đăng nhập `admin` gọi lại | Hai vai trò trả danh sách quyền khác nhau |
| AG5 | `make ci`; trong Swagger gọi `GET /inventory/balances` | Test xanh, trả danh sách (rỗng cũng được) |
| AG6 | Xem ảnh trong `docs/reports/assets/ag6/`; `make run-client`, đăng nhập thử hai vai trò | Menu hai vai trò khác nhau |
| AG7 | Mở `/docs` của server | Thấy đủ nhóm endpoint của 10 module, gọi thử trả 501 |
| AG8 | `make ci`; push lên GitHub và xem tab Actions | Workflow chạy và xanh |
| AG9 | Đọc `docs/reports/ag9-verify.md` | Kết luận ghi SẴN SÀNG GIAO MODULE |

Ngoài các lệnh trên, **luôn đọc hai mục «Giả định» và «Chưa làm hoặc rủi ro»** của báo cáo. Đây là nơi agent tự thú nhận chỗ đoán; nếu thấy giả định về DB hoặc phân quyền khác ý bạn, sửa ngay ở bước đó, không để dồn.

## 15. Khi agent làm sai

- **Test đỏ hoặc báo cáo thiếu kết quả thật:** dán lại cho agent câu «Chạy lại toàn bộ test của bước, sửa đến khi xanh, rồi cập nhật báo cáo bằng kết quả thật».
- **Agent sửa file SQL đã đóng băng:** từ chối PR, dùng `git checkout develop -- database/` để khôi phục, rồi giao lại và nhắc quy tắc 1.
- **Agent bịa tên cột hoặc bảng:** trỏ tới dòng trong `schema.sql` hoặc `patch_v4_2_1.sql`, yêu cầu đọc lại và sửa; đây là lý do quy tắc 2 có trong khối chung.
- **Sửa hai lần vẫn không xong:** gửi mình báo cáo, log lỗi và tên bước.

## 16. Chuẩn bị thư mục gốc cho AG0

Tạo thư mục `abest-wms/`, mở nó bằng agent, và tạo bên trong một thư mục con `_inbox/` chứa các file sau. `_inbox/` sẽ không được commit.

| # | File | Tên trong `_inbox/` | Ghi chú |
| --- | --- | --- | --- |
| 1 | Schema v4.1 | `wms_database_schema_v4_1.sql` | Đóng băng |
| 2 | Patch v4.2.1 | `wms_database_patch_v4_2_1.sql` | Đóng băng |
| 3 | Smoke test | `wms_smoke_test_v4_2_1.sql` | Đóng băng |
| 4 | Slide phân rã chức năng v3 | `WMS_Mobile_Phân_rã_chức_năng_v3_máy_chiếu.pptx` | Nguồn cho ma trận quyền |
| 5 | Sơ đồ workflows v2 | file `.drawio` bạn đang có | Agent tự khớp tên |
| 6 | Đặc tả dự án | `dac-ta-du-an.md` | Xuất Markdown từ tài liệu đặc tả |
| 7 | Chuẩn công nghệ và hợp đồng API | `chuan-api-cong-nghe.md` | Xuất Markdown |
| 8 | Tài liệu quy trình này | `quy-trinh-dung-khung.md` | Agent đọc bảng nghiệm thu ở mục 14 |
| 9 | Danh sách thành viên | `members.txt` | Chỉ dùng ở U6, không commit |

Nội dung mẫu của `members.txt` (A là bạn nên không cần ghi):

```text
B=ten-github-cua-B
C=ten-github-cua-C
D=ten-github-cua-D
```

Bốn việc agent **không tự làm được** dù bạn dán prompt: cài phần mềm còn thiếu và chạy `gh auth login` (U1), xác nhận quyết định công nghệ (U2, bạn xác nhận bằng việc dán prompt), bấm merge (U5), và gửi tin cho nhóm (U7). Ngoài ra bảo vệ nhánh ở U6 chỉ bật được nếu gói GitHub của bạn cho phép.

## 17. Prompt AG0: U1 đến U4 (chạy ngay, mỗi U một báo cáo)

```text
Bạn là trợ lý DevOps cho dự án ABEST WMS. Thư mục hiện tại là thư mục gốc dự án; các file nguồn nằm trong ./_inbox/.

Quy tắc:
1. Mỗi lệnh tạo, ghi hoặc push lên GitHub, và mọi lệnh gh, PHẢI HỎI TÔI DUYỆT trước khi chạy.
2. KHÔNG tự cài phần mềm, KHÔNG yêu cầu tôi dán token hay mật khẩu.
3. Không sửa nội dung bất kỳ file .sql nào.
4. Thiếu thông tin hoặc bị chặn thì DỪNG và hỏi, không đoán.
5. Mỗi U có MỘT báo cáo riêng theo mẫu: Mục tiêu; Đã làm; Lệnh đã chạy và kết quả thật; Kết luận ĐẠT hoặc KHÔNG ĐẠT; Việc tôi cần làm tiếp. U trước chưa ĐẠT thì không làm U sau.

U1. Kiểm tra máy. Báo cáo: docs/reports/u1-machine.md
- Chỉ đọc: git --version; docker --version và docker info; python --version (cần 3.11 trở lên); gh --version; gh auth status.
- Ghi bảng: công cụ, phiên bản, đạt hoặc không.
- Thiếu gì, hoặc gh chưa đăng nhập, thì DỪNG, nói tôi cần làm gì (cài thêm, hoặc tự chạy gh auth login), chờ tôi báo xong rồi chạy lại phần kiểm tra.

U2. Ghi nhận quyết định công nghệ. Báo cáo: docs/reports/u2-tech-decision.md
- Đọc ./_inbox/chuan-api-cong-nghe.md, lấy bảng ở mục 1 (Công nghệ chốt).
- Tạo docs/adr/0001-cong-nghe.md: tóm tắt bảng đó (hạng mục, quyết định, lý do, không dùng) và dòng «Trạng thái: Đã chốt bởi leader» kèm ngày hôm nay. Việc tôi dán prompt này là xác nhận tôi chốt đúng như file; KHÔNG thêm hay đổi quyết định nào. Chỉ tạo file, chưa commit.

U3. Tạo repo. Báo cáo: docs/reports/u3-repo.md
- git init với nhánh main nếu chưa có; tạo .gitignore tối thiểu gồm _inbox/, .env, __pycache__/, .venv/; commit đầu tiên chỉ gồm .gitignore.
- gh repo create abest-wms --private --source=. --remote=origin --push; rồi tạo nhánh develop từ main và push.
- Xác nhận bằng gh repo view và git branch -a.

U4. Gom file nguồn. Báo cáo: docs/reports/u4-sources.md
- Làm trên nhánh develop. Chuyển file từ _inbox vào repo:
  wms_database_schema_v4_1.sql -> database/schema.sql
  wms_database_patch_v4_2_1.sql -> database/patch_v4_2_1.sql
  wms_smoke_test_v4_2_1.sql -> database/tests/smoke_test.sql
  file .pptx -> docs/source/wms_decomposition_v3.pptx
  file .drawio -> docs/source/wms_workflows_v2.drawio
  dac-ta-du-an.md -> docs/spec/dac-ta-du-an.md
  chuan-api-cong-nghe.md -> docs/spec/chuan-api-cong-nghe.md
  quy-trinh-dung-khung.md -> docs/spec/quy-trinh-dung-khung.md
- Đưa docs/adr/0001-cong-nghe.md và các báo cáo u1 đến u3 vào docs/reports/ cùng commit.
- Commit thông điệp «chore: add source docs and frozen database files», push develop.
- Xác nhận: so sha256 của 3 file database/ với file gốc trong _inbox (phải trùng); _inbox không bị commit (git status sạch); in git log --oneline -3 và cây thư mục hai cấp.

Kết thúc: in bảng tổng hợp U1 đến U4 (ĐẠT hoặc KHÔNG ĐẠT) và nói rõ tôi đã sẵn sàng giao AG1 chưa.
```

## 18. Prompt U5: nghiệm thu sau mỗi bước AG1 đến AG8

Dán sau khi agent xong một bước, thay mã bước vào chỗ trống. Mỗi lần chạy sinh một báo cáo riêng.

```text
Bạn là người nghiệm thu, KHÔNG sửa code. Bước vừa xong: <mã bước, ví dụ ag3-server-core>.

1. git fetch; chuyển sang nhánh chore/<mã bước> (hoặc PR tôi nêu).
2. Đọc docs/reports/<mã bước>.md: có đủ 7 mục mẫu không; kết quả test có phải kết quả thật không (chạy lại để đối chiếu).
3. Chạy make ci và lệnh nghiệm thu riêng của bước đó ở bảng mục 14 của docs/spec/quy-trinh-dung-khung.md; dán output thật.
4. Đọc mục Giả định đã đặt và Chưa làm hoặc rủi ro; liệt kê điều tôi cần quyết hoặc yêu cầu sửa.
5. Kiểm file đóng băng không đổi: git diff develop -- database/schema.sql database/patch_v4_2_1.sql database/tests/smoke_test.sql phải rỗng.
6. Kết luận một trong hai: NÊN MERGE hoặc KHÔNG NÊN MERGE, kèm lý do. KHÔNG tự merge; chỉ khi tôi nói «merge» mới chạy gh pr merge --squash.
Báo cáo: docs/reports/u5-<mã bước>.md
```

## 19. Prompt U6 và U7: chỉ chạy SAU KHI AG9 kết luận SẴN SÀNG

```text
Bạn là trợ lý DevOps cho dự án ABEST WMS. Điều kiện đầu: docs/reports/ag9-verify.md phải kết luận SẴN SÀNG GIAO MODULE; nếu không thì DỪNG. Quy tắc như prompt AG0: mọi lệnh gh hoặc push phải hỏi tôi duyệt, không đoán thông tin, mỗi mục có báo cáo riêng (Mục tiêu; Đã làm; Lệnh và kết quả thật; ĐẠT hoặc KHÔNG ĐẠT; Việc tôi cần làm tiếp).

U6a. Thành viên. Báo cáo: docs/reports/u6a-members.md
- Đọc ./_inbox/members.txt (dòng dạng B=username). Hỏi duyệt từng người rồi thêm collaborator quyền Write bằng gh api. Không đoán username.

U6b. Nhánh. Báo cáo: docs/reports/u6b-branches.md
- Chạy scripts/create_branches.sh --dry-run, đưa tôi xem danh sách; tôi duyệt thì chạy thật. Xác nhận bằng git branch -r.

U6c. Bảo vệ nhánh. Báo cáo: docs/reports/u6c-protection.md
- Dùng gh api để xem repo là private hay public. Thử cấu hình bảo vệ main và develop: bắt buộc PR, ít nhất 1 người duyệt, bắt buộc check ci xanh, cấm push thẳng.
- Nếu API báo cần gói trả phí thì KHÔNG cố tiếp: ghi KHÔNG ĐẠT kèm thông báo lỗi thật và đề xuất 3 hướng (nâng gói, để repo public, hoặc giữ private và dùng kỷ luật chỉ đi qua PR).

U6d. Actions và tag. Báo cáo: docs/reports/u6d-tag.md
- gh run list --limit 3 để xác nhận CI đã chạy xanh trên develop. Nếu xanh: git tag -a v0.0-skeleton -m «Khung dự án sẵn sàng giao module» trên develop và push tag. Nếu đỏ: DỪNG, báo lỗi.

U7. Soạn tin giao việc. Báo cáo và sản phẩm: docs/reports/u7-kickoff-message.md
- Soạn một tin nhắn để tôi gửi nhóm, gồm: link repo; cách chạy (trỏ README); nhánh và module của từng người (bảng ở mục 8 đặc tả); file docs/api/<module>.md mỗi người phải hoàn thiện đầu tiên; quy tắc git (mục 7.2 đặc tả); nhắc test và báo cáo bắt buộc. KHÔNG gửi tin đi, chỉ soạn.
```
