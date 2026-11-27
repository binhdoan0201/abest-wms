# Báo cáo AG1: Dựng khung Repository và Cấu hình Chất lượng Code

## 1. Mục tiêu
- Dựng toàn bộ cấu trúc thư mục của dự án ABEST WMS theo đúng Mục 3 của `docs/spec/dac-ta-du-an.md`.
- Cấu hình các công cụ kiểm soát chất lượng mã nguồn: `black`, `ruff`, `mypy`, `pre-commit` (độ dài dòng tối đa 100).
- Thiết lập tài liệu quy trình: `README.md`, `CONTRIBUTING.md`, `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`.
- Thiết lập file môi trường mẫu `.env.example`, `.gitignore` mở rộng, `Makefile` hỗ trợ đa nền tảng.
- Viết script `scripts/check_structure.py` và bài test kiến trúc `server/tests/architecture/test_structure.py`.

## 2. Đã làm (Danh sách file)
- **Cấu hình gốc và tài liệu dự án:**
  - `README.md`: Hướng dẫn cài đặt, chạy Docker DB, server, client, test và liên kết tài liệu quy ước.
  - `CONTRIBUTING.md`: Quy trình Git, quản lý nhánh, quy tắc Conventional Commits, phân quyền file leader.
  - `.gitignore`: Mở rộng file có sẵn, giữ nguyên các dòng cũ và bỏ qua file sinh ra bởi Python/IDE/test.
  - `.env.example`: Biến môi trường mẫu cho development.
  - `pyproject.toml`: Cấu hình độ dài dòng 100 cho Black, Ruff, cấu hình MyPy và Pytest.
  - `.pre-commit-config.yaml`: Cấu hình hook pre-commit cho Black, Ruff, trailing-whitespace, yaml.
  - `Makefile` & `make.bat`: Hỗ trợ các target: `install`, `db-reset`, `lint`, `typecheck`, `test`, `ci`, `run-server`, `run-client`.
- **Cấu hình GitHub:**
  - `.github/CODEOWNERS`: Quy định quyền sở hữu file, file dùng chung chỉ @A sửa, phân công module @A, @B, @C, @D.
  - `.github/PULL_REQUEST_TEMPLATE.md`: Biểu mẫu PR kèm checklist Definition of Done theo Mục 9 Đặc tả.
- **Server:**
  - `server/requirements.txt`: Ghim các phiên bản cụ thể cho FastAPI, Uvicorn, SQLAlchemy, Psycopg 3, PyJWT, Bcrypt, Pytest, Black, Ruff, MyPy.
  - `server/app/main.py`: Entrypoint FastAPI backend tối thiểu với endpoint `GET /health`.
  - Các package có `__init__.py`: `core/`, `shared/`, `modules/{auth, master_data, inventory, inbound, outbound, tasks, approvals, cycle_count, dashboard}/`, `integrations/`.
  - Các thư mục test có `__init__.py`: `server/tests/{unit, integration, e2e, architecture}/`.
  - `server/tests/architecture/test_structure.py`: Test tự động kiểm tra tính đầy đủ của cấu trúc Mục 3.
- **Client:**
  - `client/requirements.txt`: Ghim phiên bản FastAPI, Jinja2, HTTPX, Pydantic-settings.
  - `client/app/main.py`: Entrypoint FastAPI client tối thiểu với endpoint `GET /health`.
  - Các package: `client/app/core/`, `client/app/modules/`.
  - Các thư mục rỗng có `.gitkeep`: `client/app/static/`, `client/app/templates/_base/`.
- **Database & Docs & Scripts:**
  - `.gitkeep` trong `database/migrations/`, `database/seeds/`, `docs/api/`.
  - `scripts/check_structure.py`: Script kiểm tra 32 thư mục và 17 file bắt buộc.

## 3. Cách chạy lại
```bash
# 1. Kiểm tra cấu trúc thư mục
python scripts/check_structure.py

# 2. Cài đặt môi trường ảo và thư viện
make install

# 3. Kiểm tra linting và formatting
make lint

# 4. Kiểm tra kiểu tĩnh MyPy
make typecheck

# 5. Chạy test
make test

# 6. Chạy toàn bộ kiểm tra CI
make ci
```

## 4. Kết quả test (Lệnh và kết quả thật)

### (a) Kiểm tra cấu trúc: `python scripts/check_structure.py`
- **Lệnh:**
  ```powershell
  .venv\Scripts\python.exe scripts\check_structure.py
  ```
- **Kết quả thật:**
  ```text
  ============================================================
  ABEST WMS: Kiểm tra cấu trúc thư mục & file theo Mục 3 Đặc tả
  ============================================================

  [THÀNH CÔNG] Tất cả thư mục và file bắt buộc của Mục 3 đều TỒN TẠI!
    - Đã kiểm tra: 32 thư mục.
    - Đã kiểm tra: 17 file bắt buộc.
  ============================================================
  ```
- **Mã thoát:** 0 (ĐẠT).

### (b) Tạo lại virtualenv và `make install`:
- **Lệnh:**
  ```powershell
  mingw32-make install
  ```
- **Kết quả thật:**
  ```text
  python -m venv .venv
  .venv/Scripts/python.exe -m pip install --upgrade pip
  ...
  Successfully installed pip-26.3
  .venv/Scripts/python.exe -m pip install -r server/requirements.txt
  ...
  Successfully installed annotated-types-0.8.0 anyio-4.16.0 bcrypt-4.2.1 black-24.10.0 certifi-2026.10.23 click-8.5.1 colorama-0.4.6 fastapi-0.115.6 greenlet-3.5.6 h11-0.16.0 httpcore-1.0.9 httptools-0.9.0 httpx-0.28.1 idna-3.20 iniconfig-2.3.1 mypy-1.14.0 mypy-extensions-1.2.0 packaging-26.3 passlib-1.7.4 pathspec-1.1.1 platformdirs-4.14.7 pluggy-1.7.0 psycopg-3.2.3 psycopg-binary-3.2.3 pydantic-2.10.4 pydantic-core-2.27.2 pydantic-settings-2.7.0 pyjwt-2.10.1 pytest-8.3.4 pytest-asyncio-0.25.0 python-dotenv-1.0.1 python-multipart-0.0.20 pyyaml-6.0.3 ruff-0.8.4 sqlalchemy-2.0.36 starlette-0.41.3 typing-extensions-4.16.0 tzdata-2026.6 uvicorn-0.34.0 watchfiles-1.3.0 websockets-17.4
  .venv/Scripts/python.exe -m pip install -r client/requirements.txt
  ...
  Successfully installed MarkupSafe-3.0.4 jinja2-3.1.5
  ```
- **Mã thoát:** 0 (ĐẠT).

### (c) Kiểm tra chất lượng mã nguồn: `make lint` & `make typecheck`
- **Lệnh:**
  ```powershell
  mingw32-make lint
  mingw32-make typecheck
  ```
- **Kết quả thật:**
  ```text
  .venv/Scripts/black.exe --check .
  All done! ✨ 🍰 ✨
  26 files would be left unchanged.
  .venv/Scripts/ruff.exe check .
  All checks passed!

  .venv/Scripts/mypy.exe server client scripts
  Success: no issues found in 26 source files
  ```
- **Mã thoát:** 0 (ĐẠT).

### (d) Chạy kiểm thử: `make test` & `make ci`
- **Lệnh:**
  ```powershell
  mingw32-make ci
  ```
- **Kết quả thật:**
  ```text
  .venv/Scripts/black.exe --check .
  All done! ✨ 🍰 ✨
  26 files would be left unchanged.
  .venv/Scripts/ruff.exe check .
  All checks passed!
  .venv/Scripts/mypy.exe server client scripts
  Success: no issues found in 26 source files
  .venv/Scripts/pytest.exe server/tests
  ============================= test session starts =============================
  platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0
  rootdir: D:\abest-wms
  configfile: pyproject.toml
  plugins: anyio-4.16.0, platformdirs-4.14.7, asyncio-0.25.0
  asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
  collected 1 item

  server\tests\architecture\test_structure.py .                            [100%]

  ============================== 1 passed in 0.02s ==============================
  ```
- **Mã thoát:** 0 (ĐẠT).

## 5. Giả định đã đặt
- Sử dụng `make.bat` và cú pháp Makefile tương thích Windows để chạy mượt mà trên môi trường máy của nhóm (`mingw32-make` / `cmd` / `powershell`) cũng như CI Linux sau này.
- Cấu hình `explicit_package_bases = true` trong `pyproject.toml` để MyPy xử lý song song hai package `server.app` và `client.app` mà không bị trùng tên module `app`.
- Thêm `pythonpath = ["."]` vào cấu hình `[tool.pytest.ini_options]` để bài test kiến trúc có thể import trực tiếp từ thư mục `scripts`.

## 6. Chưa làm hoặc rủi ro
- Docker Compose CSDL PostgreSQL 16 và các kịch bản nạp schema/seed chưa triển khai (đây là nhiệm vụ của bước AG2).
- Các endpoint của module backend và client view mới chỉ ở dạng khung `GET /health` cơ bản, chưa có nghiệp vụ cụ thể.

## 7. Đề xuất bước tiếp
- Leader thực hiện nghiệm thu U5: chạy `make ci`, kiểm tra báo cáo và duyệt gộp PR vào nhánh `develop`.
- Tiếp tục giao việc bước **AG2: DB, seed và test DB** (`chore/ag2-database`).
