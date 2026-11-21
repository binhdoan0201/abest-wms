#!/usr/bin/env bash
# ABEST WMS - Tạo và đẩy 10 nhánh tính năng từ nhánh develop lên remote origin
set -euo pipefail

BRANCHES=(
    "feature/core-auth"
    "feature/inventory"
    "feature/integrations-mock"
    "feature/master-data"
    "feature/inbound"
    "feature/outbound"
    "feature/tasks"
    "feature/approvals"
    "feature/cycle-count"
    "feature/dashboard"
)

BASE_BRANCH="develop"
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        *)
            ;;
    esac
done

echo "=========================================================="
echo "ABEST WMS - Khởi tạo 10 nhánh tính năng từ '$BASE_BRANCH'"
echo "=========================================================="

if [ "$DRY_RUN" = true ]; then
    echo "[DRY-RUN] Chế độ mô phỏng - KHÔNG thực hiện thay đổi trên Git/Remote."
    echo "Danh sách 10 nhánh tính năng dự kiến tạo từ '$BASE_BRANCH':"
    for b in "${BRANCHES[@]}"; do
        echo "  - $b -> git branch $b $BASE_BRANCH && git push -u origin $b"
    done
    echo "[DRY-RUN] Hoàn tất mô phỏng kiểm tra danh sách nhánh."
    exit 0
fi

# Chạy thật (khi được duyệt ở bước U6b)
echo "Đảm bảo đã đồng bộ nhánh cơ sở '$BASE_BRANCH'..."
git fetch origin "$BASE_BRANCH"
git checkout "$BASE_BRANCH"
git pull origin "$BASE_BRANCH"

for b in "${BRANCHES[@]}"; do
    echo "Khởi tạo nhánh '$b' từ '$BASE_BRANCH'..."
    if git show-ref --verify --quiet "refs/heads/$b"; then
        echo "  Nhánh cục bộ '$b' đã tồn tại."
    else
        git branch "$b" "$BASE_BRANCH"
        echo "  Đã tạo nhánh cục bộ '$b'."
    fi
    echo "  Đẩy '$b' lên origin..."
    git push -u origin "$b"
done

echo "Tất cả 10 nhánh tính năng đã được khởi tạo và đẩy lên remote thành công!"
