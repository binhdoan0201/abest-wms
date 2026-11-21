# Báo cáo thực hiện bước U7: Soạn thông điệp giao việc khởi động (Kickoff Message)

**Mã bước:** `u7-kickoff-message`  
**Vai trò:** Trợ lý DevOps  
**Thời gian thực hiện:** 2026-11-21  

---

## 1. Mục tiêu
Soạn thảo nội dung thông điệp phân công công việc và quy chế làm việc để Leader @A (Bình) gửi cho toàn bộ nhóm phát triển (Bình, Phước, Cường, Hiếu), bảo đảm mọi người nắm rõ phạm vi module, nhánh làm việc, hợp đồng API và kỷ luật Git trước khi bắt đầu code.

---

## 2. Đã làm
1. Tổng hợp dữ liệu từ Mục 8 (Bảng phân công công việc) và Mục 7 (Quy trình Git & Kỷ luật phối hợp) của tài liệu đặc tả `docs/spec/dac-ta-du-an.md`.
2. Đối chiếu danh mục nhánh `feature/*` và cấu trúc khung module đã được scaffold ở bước AG7.
3. Soạn thông điệp hoàn chỉnh sẵn sàng để gửi nhóm (qua Slack, Zalo, Teams hoặc Email).

---

## 3. Nội dung thông điệp giao việc (Kickoff Message)

```markdown
Chào cả nhóm @all,

Khung kiến trúc nền tảng (Skeleton) của dự án **ABEST WMS** đã chính thức hoàn thiện, được kiểm định độc lập và gắn tag phát hành `v0.0-skeleton`. Toàn bộ 10 nhánh tính năng dài hạn đã được tạo sẵn trên GitHub và cấu hình sẵn bảo vệ nhánh.

Dưới đây là thông tin quan trọng để mọi người bắt đầu triển khai module của mình:

---

### 1. Thông tin kho lưu trữ & Hướng dẫn bắt đầu
- **Kho lưu trữ GitHub:** https://github.com/binhdoan0201/abest-wms
- **Hướng dẫn cài đặt & chạy thử:** Đọc chi tiết tại [README.md](https://github.com/binhdoan0201/abest-wms/blob/develop/README.md).
  - Khởi tạo môi trường: `make install` (trên Windows: `.\make.bat install`).
  - Khởi động CSDL & seed dữ liệu mẫu: `docker compose up -d` rồi `make db-reset` (hoặc `.\make.bat db-reset`).
  - Chạy backend (port 8000): `make run-server` (Swagger docs: http://localhost:8000/docs).
  - Chạy web client (port 3000): `make run-client` (Đăng nhập bằng 9 tài khoản demo, mật khẩu chung `Demo@123456`).

---

### 2. Phân công Module & Nhánh làm việc

| Thành viên | GitHub Username | Phân hệ phụ trách | Nhánh làm việc (`feature/*`) | File Hợp đồng API bắt buộc hoàn thiện đầu tiên |
| :--- | :--- | :--- | :--- | :--- |
| **A (Bình - Leader)** | `binhdoan0201` | Lõi Auth & RBAC, Tồn kho (Inventory), Mock ERP | `feature/core-auth`<br>`feature/inventory`<br>`feature/integrations-mock` | `docs/api/core-auth.md`<br>`docs/api/inventory.md`<br>`docs/api/integrations.md` |
| **B (Phước)** | `HuuPhuoc1235` | Dữ liệu nguồn (Master Data) & Nhập kho (Inbound) | `feature/master-data`<br>`feature/inbound` | `docs/api/master-data.md`<br>`docs/api/inbound.md` |
| **C (Cường)** | `quoccuong1108` | Xuất kho (Outbound: SO, Pick, Pack, GI) | `feature/outbound` | `docs/api/outbound.md` |
| **D (Hiếu)** | `hieunguyen201104` | Nhiệm vụ (Tasks), Phê duyệt (Approvals), Kiểm kê (Cycle Count), Dashboard | `feature/tasks`<br>`feature/approvals`<br>`feature/cycle-count`<br>`feature/dashboard` | `docs/api/tasks.md` *(ưu tiên cao)*<br>`docs/api/approvals.md`<br>`docs/api/cycle-count.md`<br>`docs/api/dashboard.md` |

> ⚠️ **Lưu ý đặc biệt cho D:** Module `tasks` và giao diện hàm điều phối cần được tập trung hoàn thiện sớm vì luồng Inbound của B (cất hàng) và Outbound của C (soạn hàng) trực tiếp phụ thuộc vào nhiệm vụ kho.

---

### 3. Quy trình Git và Kỷ luật làm việc (Mục 7.2 Đặc tả)
1. **Quy tắc nhánh:**
   - Tuyệt đối **không push trực tiếp** lên nhánh `main` và `develop`. Cả hai nhánh đã được bật bảo vệ nghiêm ngặt.
   - Mọi đóng góp phải đi qua Pull Request (PR) từ nhánh `feature/<module>` vào nhánh `develop`.
   - Mỗi PR bắt buộc có ít nhất **1 approval** và **pipeline CI chạy xanh (100% Green)** mới được squash merge.
2. **Quy định Review:**
   - PR của B, C, D do A (Leader) review và duyệt.
   - PR của A do B review và duyệt.
   - Nếu PR có gọi sang hàm dịch vụ của module khác, bắt buộc tag thành viên phụ trách module đó vào review chéo.
3. **Phạm vi code:**
   - Mỗi người chỉ sửa trong thư mục module được phân công (`server/app/modules/<module>` và `client/app/modules/<module>`).
   - Các file dùng chung (`server/app/core/`, `database/`, `.github/`, `docker-compose.yml`) chỉ do Leader @A chỉnh sửa.
   - Tương tác giữa các module **bắt buộc** gọi qua hàm công khai của `services.py`, không gọi trực tiếp Model/Repository hay bảng CSDL của module khác.
4. **Quy chuẩn Commit (Conventional Commits):**
   - Định dạng: `<loại>(<scope>): <mô tả ngắn bằng tiếng Việt>`.
   - Ví dụ: `feat(inbound): thêm API tạo GRN đếm mù`, `fix(outbound): sửa thứ tự phân bổ lô hàng theo FEFO`.
5. **Bảo mật:** Tuyệt đối không commit file `.env`, mật khẩu, secret key cá nhân lên GitHub.

---

### 4. Tiêu chí hoàn thành (Definition of Done)
Trước khi mở PR, mỗi thành viên bắt buộc chạy kiểm tra cục bộ:
```bash
make ci    # (hoặc: .\make.bat ci trên Windows)
```
Chuỗi kiểm tra bao gồm:
- Định dạng mã nguồn (`black`, `ruff`).
- Kiểm tra kiểu tĩnh (`mypy` - không còn lỗi gõ type).
- Chạy kiểm thử CSDL & bộ unit/integration/architecture test (`pytest`).
- Viết bài test đầy đủ cho các API và logic nghiệp vụ mới viết.

Chúc cả nhóm phối hợp hiệu quả và xây dựng hệ thống ABEST WMS thành công rực rỡ! 🚀
```

---

## 4. Kết luận
**ĐẠT**

---

## 5. Việc cần làm tiếp
1. Thực hiện bước **U6d: Kiểm tra CI và gắn tag `v0.0-skeleton`**.
2. Leader sao chép nội dung thông điệp trên để gửi tới nhóm phát triển.
