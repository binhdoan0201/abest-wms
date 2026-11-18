## Mô tả thay đổi

<!-- Tóm tắt ngắn gọn nội dung và mục đích của Pull Request -->

## Loại thay đổi
- [ ] `feat`: Tính năng mới
- [ ] `fix`: Sửa lỗi
- [ ] `refactor`: Tái cấu trúc mã nguồn
- [ ] `test`: Thêm hoặc cập nhật bài kiểm thử
- [ ] `docs`: Cập nhật tài liệu
- [ ] `chore`: Cấu hình, công cụ hoặc việc phụ trợ

## Checklist Definition of Done (Mục 9 Đặc tả)
- [ ] Tên file, hàm, biến theo mục 4; `ruff`, `black`, `mypy` không báo lỗi.
- [ ] Mỗi endpoint có khai báo mã quyền và đã thử với ít nhất một vai trò đúng và một vai trò sai.
- [ ] Hành động ghi có `audit_logs`; thay đổi tồn đi qua `apply_movement`.
- [ ] Có test đơn vị cho service (đặc biệt: sổ cái tồn, FEFO, tính tầng duyệt) và test tích hợp cho API chính.
- [ ] Cập nhật hợp đồng API trong `docs/api/<module>.md`.
- [ ] PR đã được review chéo, CI xanh, gộp vào `develop`.
- [ ] Chạy được đúng đoạn tương ứng trong kịch bản demo ở mục 6.2 đặc tả.
- [ ] Khi đổi schema hoặc hàm DB: nạp lại schema v4.1 và patch v4.2.1 trên DB trống, chạy patch lần 2, rồi chạy `wms_smoke_test_v4_2_1.sql` (cả 3 bước không lỗi).
- [ ] Nghiệp vụ hoàn tất chứng từ có ghi tồn phải có test rollback; đối tượng có `version_no` có test 409; không ghi token hay mật khẩu vào log (chuẩn API, mục 8 và 9).
