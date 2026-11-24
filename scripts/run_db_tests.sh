#!/usr/bin/env bash
set -euo pipefail

# Chuyển về thư mục gốc của repository
cd "$(dirname "$0")/.."

# Nạp biến môi trường từ .env nếu tồn tại
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-abest_wms}"
DB_TEMP_NAME="abest_wms_test_temp"
DB_USER="${DB_USER:-wms_admin}"
DB_PASSWORD="${DB_PASSWORD:-wms_secret_pass}"

echo "============================================================"
echo "ABEST WMS: Chạy kiểm thử CSDL (run_db_tests.sh)"
echo "============================================================"

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
  echo "--> Đang chạy: $file_path trên CSDL $target_db"
  exec_psql "$target_db" < "$file_path"
}

cleanup() {
  echo "Dọn dẹp CSDL tạm: $DB_TEMP_NAME..."
  exec_psql "postgres" <<EOF || true
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_TEMP_NAME' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$DB_TEMP_NAME";
EOF
}
trap cleanup EXIT

# 1. Tạo CSDL tạm riêng biệt cho smoke test
echo "1. Tạo CSDL tạm riêng: $DB_TEMP_NAME"
cleanup
exec_psql "postgres" <<EOF
CREATE DATABASE "$DB_TEMP_NAME" OWNER "$DB_USER";
EOF

# 2. Nạp schema và patch vào CSDL tạm
echo "2. Nạp schema.sql và patch_v4_2_1.sql vào $DB_TEMP_NAME"
exec_sql_file "$DB_TEMP_NAME" "database/schema.sql"
exec_sql_file "$DB_TEMP_NAME" "database/patch_v4_2_1.sql"
for migration_file in $(ls database/migrations/*.sql 2>/dev/null | sort); do
  exec_sql_file "$DB_TEMP_NAME" "$migration_file"
done

# 3. Chạy smoke_test.sql trên CSDL tạm
echo "3. Chạy wms_smoke_test_v4_2_1.sql"
exec_sql_file "$DB_TEMP_NAME" "database/tests/smoke_test.sql"

# 4. Chạy patch_v4_2_1.sql lần 2 trên CSDL tạm để chứng minh tính idempotent
echo "4. Chạy patch_v4_2_1.sql và các migration lần 2 để kiểm tra idempotent"
exec_sql_file "$DB_TEMP_NAME" "database/patch_v4_2_1.sql"
for migration_file in $(ls database/migrations/*.sql 2>/dev/null | sort); do
  exec_sql_file "$DB_TEMP_NAME" "$migration_file"
done

# 5. Chạy test_seed.sql trên CSDL chính đã seed
echo "5. Chạy test_seed.sql trên CSDL chính ($DB_NAME)"
exec_sql_file "$DB_NAME" "database/tests/test_seed.sql"

echo "============================================================"
echo "[THÀNH CÔNG] TẤT CẢ BÀI KIỂM THỬ ĐẠT (smoke test, patch lần 2, test_seed)"
echo "============================================================"
