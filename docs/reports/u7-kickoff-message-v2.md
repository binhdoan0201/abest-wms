# Báo cáo thực hiện bước U7 (Phiên bản v2): Soạn thông điệp giao việc khởi động gán tên thật

**Mã bước:** `u7-kickoff-message-v2`  
**Vai trò:** Kỹ sư tài liệu  
**Thời gian thực hiện:** 2026-11-23  

---

## 1. Mục tiêu
Cập nhật nội dung thông điệp phân công công việc và quy chế làm việc khởi động dự án từ phiên bản dùng chữ cái A, B, C, D sang họ tên và GitHub username thật của từng thành viên:
- **Đoàn Duy Bình (A - Leader)** (`@binhdoan0201`)
- **Mai Hữu Phước (B)** (`@HuuPhuoc1235`)
- **Hồ Quốc Cường (C)** (`@quoccuong1108`)
- **Nguyễn Đức Hiếu (D)** (`@hieunguyen201104`)

Đồng thời, cập nhật đúng phân bổ module theo bảng đặc tả đã tái cân bằng (mục 8.1), bổ sung hướng dẫn đồng bộ mã nguồn từ `develop` về nhánh tính năng (`feature/*`), và lưu trữ sẵn sàng để gửi nhóm. *(Lưu ý: Không gửi tin nhắn này ra ngoài trong bước hiện tại).*

---

## 2. Đã làm
1. Kế thừa thông điệp từ `docs/reports/u7-kickoff-message.md` (giữ nguyên file gốc).
2. Thay thế toàn bộ mã định danh chữ cái A, B, C, D bằng họ tên và tài khoản GitHub thật theo `_inbox/members.txt`.
3. Đồng bộ bảng phân công module và nhánh làm việc đúng theo bảng đặc tả tái cân bằng (Bình nhận thêm `master-data` và `dashboard`; Phước nhận `inbound` và `cycle-count`; Cường nhận `outbound`; Hiếu nhận `tasks` và `approvals`).
4. Thêm mục hướng dẫn chuẩn thao tác `git fetch` và `git merge origin/develop` để các thành viên cập nhật mã khung mới nhất về nhánh làm việc của mình.

---

## 3. Nội dung thông điệp giao việc (Kickoff Message v2)

```markdown
Chào cả nhóm @all,

Khung kiến trúc nền tảng (Skeleton) của dự án **ABEST WMS** đã chính thức hoàn thiện, được kiểm định độc lập và gắn tag phát hành `v0.0-skeleton`. Toàn bộ 10 nhánh tính năng dài hạn đã được tạo sẵn trên GitHub và cấu hình sẵn bảo vệ nhánh.

Dưới đây là thông tin chi tiết về phân công công việc và hướng dẫn bắt đầu để các thành viên triển khai module của mình:

---

### 1. Thông tin kho lưu trữ & Bắt đầu nhanh
- **Kho lưu trữ GitHub:** https://github.com/binhdoan0201/abest-wms
- **Tài liệu phân công chi tiết:** Xem tại [docs/PHAN_CONG.md](docs/PHAN_CONG.md)
- **Hướng dẫn cài đặt & chạy thử:** Đọc chi tiết tại [README.md](README.md).
  - Khởi tạo môi trường: `make install` (trên Windows: `.\make.bat install`).
  - Khởi động CSDL & seed dữ liệu mẫu: `docker compose up -d` rồi `make db-reset` (hoặc `.\make.bat db-reset`).
  - Chạy backend (port 8000): `make run-server` (Swagger docs: http://localhost:8000/docs).
  - Chạy web client (port 3000): `make run-client` (Đăng nhập bằng 9 tài khoản demo, mật khẩu chung `Demo@123456`).

---

### 2. Hướng dẫn đồng bộ mã nguồn về nhánh tính năng
Trước khi bắt đầu viết code trên nhánh của mình, hoặc bất cứ khi nào nhánh `develop` có cập nhật mới, các thành viên cần đồng bộ mã nguồn mới nhất từ `develop` về nhánh feature cá nhân:

```bash
# 1. Chuyển sang nhánh feature của bạn (ví dụ: feature/inbound)
git checkout feature/<tên-nhánh>

# 2. Lấy dữ liệu mới nhất từ remote
git fetch origin

# 3. Kéo và gộp nhánh develop mới nhất vào nhánh của bạn
git merge origin/develop
```
*(Nếu có xung đột, xử lý xung đột cục bộ, chạy `make ci` để đảm bảo không lỗi rồi tiếp tục công việc).*

---

### 3. Phân công Module & Nhánh làm việc

| Thành viên | GitHub Username | Phân hệ phụ trách | Nhánh làm việc (`feature/*`) | Hợp đồng API bắt buộc hoàn thiện đầu tiên |
| :--- | :--- | :--- | :--- | :--- |
| **Đoàn Duy Bình (Leader)** | `@binhdoan0201` | core, auth, inventory, integrations, master_data, dashboard | `feature/core-auth`<br>`feature/inventory`<br>`feature/integrations-mock`<br>`feature/master-data`<br>`feature/dashboard` | `docs/api/core-auth.md`<br>`docs/api/inventory.md`<br>`docs/api/integrations.md`<br>`docs/api/master-data.md`<br>`docs/api/dashboard.md` |
| **Mai Hữu Phước** | `@HuuPhuoc1235` | Inbound (gồm cất hàng) & Kiểm kê (Cycle Count) | `feature/inbound`<br>`feature/cycle-count` | `docs/api/inbound.md`<br>`docs/api/cycle-count.md` |
| **Hồ Quốc Cường** | `@quoccuong1108` | Xuất kho (Outbound: SO, Pick, Pack, GI) | `feature/outbound` | `docs/api/outbound.md` |
| **Nguyễn Đức Hiếu** | `@hieunguyen201104` | Điều phối nhiệm vụ (Tasks) & Phê duyệt (Approvals) | `feature/tasks`<br>`feature/approvals` | `docs/api/tasks.md` *(ưu tiên cao)*<br>`docs/api/approvals.md` |

> ⚠️ **Lưu ý phụ thuộc:**
> - **Nguyễn Đức Hiếu:** Cần ưu tiên hoàn thiện sớm module `tasks` vì luồng Inbound của Phước (cất hàng) và Outbound của Cường (soạn hàng) trực tiếp gọi sang `tasks`.
> - **Mai Hữu Phước & Hồ Quốc Cường:** Gọi hàm dịch vụ của `inventory` (do Bình phụ trách) và `tasks` (do Hiếu phụ trách). Phước gọi thêm `approvals` (do Hiếu phụ trách) khi xử lý lệch kho.
> - **Đoàn Duy Bình:** Module `dashboard` đọc dữ liệu tổng hợp từ các module khác.

---

### 4. Quy trình Git và Kỷ luật làm việc (Mục 7.2 Đặc tả)
1. **Quy tắc nhánh:**
   - Tuyệt đối **không push trực tiếp** lên nhánh `main` và `develop`. Cả hai nhánh đã được bật cấu hình bảo vệ nghiêm ngặt.
   - Mọi đóng góp phải đi qua Pull Request (PR) từ nhánh `feature/<module>` vào nhánh `develop`.
   - Mỗi PR bắt buộc có ít nhất **1 approval** và **pipeline CI chạy xanh (100% Green)** mới được squash merge.
2. **Quy định Review:**
   - PR của Mai Hữu Phước, Hồ Quốc Cường, Nguyễn Đức Hiếu do Đoàn Duy Bình (Leader) review và duyệt.
   - PR của Đoàn Duy Bình do Mai Hữu Phước review và duyệt.
   - Nếu PR có gọi sang hàm dịch vụ của module khác, bắt buộc tag thành viên phụ trách module đó vào review chéo.
3. **Phạm vi code & Nguyên tắc độc lập:**
   - Mỗi người chỉ sửa trong thư mục module được phân công (`server/app/modules/<module>` và `client/app/modules/<module>`).
   - Các file dùng chung (`server/app/core/`, `server/app/shared/`, `server/app/main.py`, `database/`, `.github/`, `docker-compose.yml`) do Đoàn Duy Bình quản lý.
   - Giao tiếp giữa các module **bắt buộc** đi qua hàm dịch vụ công khai trong `services.py` của module đó; không import trực tiếp Model, Repository hay can thiệp bảng CSDL của module khác.
4. **Quy chuẩn Commit (Conventional Commits):**
   - Định dạng: `<loại>(<scope>): <mô tả ngắn bằng tiếng Việt>`.
   - Ví dụ: `feat(inbound): thêm API tạo GRN đếm mù`, `fix(outbound): sửa thứ tự phân bổ lô hàng theo FEFO`.
5. **Bảo mật:** Tuyệt đối không commit file `.env`, mật khẩu, secret key cá nhân lên GitHub.

---

### 5. Tiêu chí hoàn thành (Definition of Done)
Trước khi mở PR, mỗi thành viên bắt buộc chạy kiểm tra cục bộ:
```bash
make ci    # (hoặc: .\make.bat ci trên Windows)
```
Chuỗi kiểm tra bao gồm:
- Định dạng mã nguồn (`black`, `ruff`).
- Kiểm tra kiểu tĩnh (`mypy` - không còn lỗi kiểu dữ liệu).
- Chạy kiểm thử CSDL & bộ unit/integration/architecture test (`pytest`).
- Viết bài test đầy đủ cho các API và logic nghiệp vụ mới phát triển.

Chúc cả nhóm phối hợp hiệu quả và đưa hệ thống ABEST WMS về đích đúng tiến độ! 🚀
```

---

## 4. Kết luận
**ĐẠT** - Bản thông điệp v2 đã sẵn sàng, phản ánh đầy đủ thông tin định danh và phân công công việc của từng thành viên.

---

## 5. Việc cần làm tiếp
1. Chờ hoàn thành PR tài liệu `chore/u6-team-docs` vào `develop`.
2. Leader Đoàn Duy Bình sử dụng nội dung thông điệp trên để gửi tới nhóm qua kênh liên lạc nội bộ.
