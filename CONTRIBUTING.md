# Quy định đóng góp và Quy trình Git cho ABEST WMS

Tài liệu này quy định chuẩn làm việc, quản lý nhánh, commit và review mã nguồn cho toàn bộ thành viên dự án ABEST WMS (chi tiết tại mục 7 của `docs/spec/dac-ta-du-an.md`).

---

## 1. Quy định về nhánh (Branches)

| Nhánh | Mục đích | Ai được ghi / gộp |
| :--- | :--- | :--- |
| `main` | Bản ổn định, chạy demo; gắn tag phát hành | Chỉ Leader Đoàn Duy Bình (`@binhdoan0201`) gộp (merge) |
| `develop` | Tích hợp công việc chung của cả nhóm | Gộp qua Pull Request (PR) |
| `feature/<module>` | Nhánh dài hạn của thành viên phụ trách module | Chủ module |
| `feature/<module>/<việc>` | Nhánh ngắn hạn cho một việc cụ thể | Chủ module |
| `fix/<mô-tả>` | Sửa lỗi cụ thể | Người sửa |

### Phân công nhánh theo thành viên:
- **Đoàn Duy Bình (Leader):** `feature/core-auth`, `feature/inventory`, `feature/integrations-mock`, `feature/master-data`, `feature/dashboard`
- **Mai Hữu Phước:** `feature/inbound`, `feature/cycle-count`
- **Hồ Quốc Cường:** `feature/outbound`
- **Nguyễn Đức Hiếu:** `feature/tasks`, `feature/approvals`

---

## 2. Quy tắc làm việc

1. **Tuyệt đối không push trực tiếp** lên nhánh `main` và `develop`. Mọi thay đổi đều phải thông qua Pull Request, cần ít nhất 1 người duyệt (approve) và toàn bộ CI kiểm tra pass (`green`), gộp theo phương thức `squash`.
2. **Rebase thường xuyên:** Đầu mỗi ngày làm việc, kéo nhánh `develop` mới nhất về và rebase nhánh feature của mình để phát hiện và giải quyết xung đột sớm nhất.
3. **Quy định Reviewer:**
   - PR của Mai Hữu Phước, Hồ Quốc Cường, Nguyễn Đức Hiếu do Đoàn Duy Bình duyệt.
   - PR của Đoàn Duy Bình do Mai Hữu Phước duyệt.
   - PR có ảnh hưởng hoặc gọi sang module khác phải gắn thêm chủ module liên quan.
4. **Phạm vi chỉnh sửa:** Chỉ sửa mã nguồn trong module được phân công. Giao tiếp giữa các module chỉ thực hiện qua hàm công khai của `services`.
5. **Các file dùng chung chỉ Leader Đoàn Duy Bình (`@binhdoan0201`) được sửa:**
   - `server/app/core/`
   - `server/app/shared/`
   - `server/app/main.py`
   - `database/` (schema, migrations, seeds)
   - `docker-compose.yml`
   - `.github/` (quy định tại `.github/CODEOWNERS`)
6. **Quy chuẩn thông điệp Commit (Conventional Commits):**
   - Cú pháp: `<loại>(<scope>): <mô tả ngắn bằng tiếng Việt>`
   - Scope là tên module hoặc thành phần: `auth`, `inventory`, `inbound`, `outbound`, `tasks`, `database`, `core`, `deps`.
   - Các loại hợp lệ: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
   - Ví dụ: `feat(inbound): thêm API tạo GRN`, `fix(inventory): chặn trừ tồn khả dụng âm`.
7. **Bảo mật:** Không bao giờ commit file `.env`, mật khẩu hoặc dữ liệu thật lên Git. Chỉ dùng `.env.example`.
