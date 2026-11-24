#!/usr/bin/env bash
set -euo pipefail

# Chuyển về thư mục gốc của repository
cd "$(dirname "$0")/.."

# Nạp biến môi trường từ .env nếu tồn tại
if [ -f .env ]; then
  # export các biến không chứa dấu # comment
  export $(grep -v '^#' .env | xargs)
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-abest_wms}"
DB_USER="${DB_USER:-wms_admin}"
DB_PASSWORD="${DB_PASSWORD:-wms_secret_pass}"

echo "============================================================"
echo "ABEST WMS: Reset & Seed CSDL ($DB_NAME)"
echo "============================================================"

# Hàm thực thi psql (hỗ trợ Docker compose exec hoặc psql trực tiếp)
exec_psql() {
  local target_db="$1"
  if command -v docker >/dev/null 2>&1 && [ -n "$(docker compose ps -q db 2>/dev/null)" ]; then
    docker compose exec -T -e PGPASSWORD="$DB_PASSWORD" db psql -U "$DB_USER" -d "$target_db" -v ON_ERROR_STOP=1
  elif command -v psql >/dev/null 2>&1; then
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$target_db" -v ON_ERROR_STOP=1
  else
    echo "[LỖI] Không tìm thấy psql và container Docker db không chạy!"
    exit 1
  fi
}

exec_sql_file() {
  local target_db="$1"
  local file_path="$2"
  echo "--> Đang nạp: $file_path"
  exec_psql "$target_db" < "$file_path"
}

# 1. Chờ Postgres sẵn sàng
echo "1. Đang kiểm tra kết nối Postgres..."
MAX_RETRIES=30
RETRY_COUNT=0
until (
  if command -v docker >/dev/null 2>&1 && [ -n "$(docker compose ps -q db 2>/dev/null)" ]; then
    docker compose exec -T db pg_isready -U "$DB_USER" -d postgres >/dev/null 2>&1
  else
    command -v pg_isready >/dev/null 2>&1 && pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1
  fi
); do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
    echo "[LỖI] Quá thời gian chờ Postgres sẵn sàng!"
    exit 1
  fi
  sleep 1
done
echo "Postgres đã sẵn sàng!"

# 2. DROP và CREATE database
echo "2. Khởi tạo lại CSDL: $DB_NAME"
exec_psql "postgres" <<EOF
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$DB_NAME";
CREATE DATABASE "$DB_NAME" OWNER "$DB_USER";
EOF

# 3. Nạp schema.sql
echo "3. Nạp database/schema.sql"
exec_sql_file "$DB_NAME" "database/schema.sql"

# 4. Nạp patch_v4_2_1.sql
echo "4. Nạp database/patch_v4_2_1.sql"
exec_sql_file "$DB_NAME" "database/patch_v4_2_1.sql"

# 4b. Nạp các migration theo số thứ tự (A cấp số, đặc tả 7.2.6)
echo "4b. Nạp các file database/migrations/*.sql"
for migration_file in $(ls database/migrations/*.sql 2>/dev/null | sort); do
  exec_sql_file "$DB_NAME" "$migration_file"
done

# 5. Nạp mọi file seed theo thứ tự
echo "5. Nạp các file database/seeds/*.sql"
for seed_file in $(ls database/seeds/*.sql 2>/dev/null | sort); do
  exec_sql_file "$DB_NAME" "$seed_file"
done

echo "============================================================"
echo "[THÀNH CÔNG] Đã reset và seed dữ liệu CSDL $DB_NAME thành công!"
echo "============================================================"
