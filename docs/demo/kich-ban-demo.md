# Kịch bản demo ABEST WMS

Kịch bản này trùng với test e2e `server/tests/e2e/test_demo_flow.py`: test xanh thì kịch bản chạy được.

## Chuẩn bị (khoảng 2 phút)

```bash
docker compose up -d
bash scripts/reset_db.sh
python -m scripts.load_demo
uvicorn server.app.main:app --port 8000      # cửa sổ 1
uvicorn client.app.main:app --port 3000      # cửa sổ 2
```

- Mật khẩu mọi tài khoản: `Demo@123456`.
- «ERP đẩy chứng từ» làm trên Swagger `http://localhost:8000/docs` bằng tài khoản `admin`
  (nút *Authorize*, dán token từ `POST /api/v1/auth/login`).
- Mở sẵn các tab trình duyệt `http://localhost:3000` cho từng vai trò (cửa sổ ẩn danh riêng).

Dữ liệu demo đã nạp: tồn trên kệ dãy A02 gồm sữa `SKU-FOOD-001` (lô hết hạn sau 6 ngày và lô sau
90 ngày), bánh mì `SKU-FOOD-002` (lô đã hết hạn), bàn ủi `SKU-ELEC-003`, hộp thủy tinh `SKU-GEN-006`.

## Phần 1 – BGĐ mở đầu (1 phút)

| Ai | Làm gì | Thấy gì |
|---|---|---|
| `bgd` | Đăng nhập | Vào thẳng **Tổng quan**: cảnh báo 1 lô đã hết hạn còn trong kho, 1 lô cận date, SKU dưới mức tối thiểu |

## Phần 2 – Nhập kho có lệch (5 phút)

| # | Ai | Làm gì | Thấy gì |
|---|---|---|---|
| 1 | ERP (`admin`, Swagger) | `POST /api/v1/integrations/erp/purchase-orders`: PO 10 `SKU-GEN-008` đơn vị `SET` | 201, nhật ký đồng bộ `SUCCESS` |
| 2 | `nv_nhan` | **Nhập kho** → mở phiếu nhận từ PO → đếm 8, hư 1 (chọn mã lý do) → nộp | Không thấy số lượng đặt (đếm mù); phiếu chờ duyệt D1, pallet cách ly |
| 3 | `thukho` | **Phê duyệt** → mở hồ sơ → *Yêu cầu đếm lại* | Hồ sơ chuyển `NEED_INFO` |
| 4 | `nv_nhan` | Thử đếm lại | Bị chặn: đếm lại phải người khác |
| 5 | `nv_nhan2` | Đếm lại đủ 10, không hư → nộp | Hồ sơ cũ `SUPERSEDED`; khớp đủ thì phiếu tự duyệt, còn lệch thì thukho duyệt lại |
| 6 | `nv_nhan` | Hoàn tất phiếu | Nhập tồn tại cửa nhận, pallet `STAGED`, sinh task cất hàng, GRN vào hàng đợi gửi ERP |
| 7 | `nv_cat` | Gợi ý vị trí → quét mã vị trí → cất | Pallet `STORED`, task cất hàng hoàn tất |

## Phần 3 – Xuất kho (5 phút)

| # | Ai | Làm gì | Thấy gì |
|---|---|---|---|
| 1 | ERP (`admin`, Swagger) | `POST /api/v1/integrations/erp/outbound-orders`: SO 10 `SKU-GEN-008`, khách hàng mẫu | 201, đơn `NEW` |
| 2 | `thukho` | **Xuất kho** → cấp phát → tạo phiên soạn giao `nv_soan` | Hàng chuyển sang «đã giữ»; task soạn hàng giao cho nv_soan |
| 3 | `nv_soan` | **Soạn hàng** → xác nhận từng dòng | Đơn `PICKED`, task soạn hoàn tất |
| 4 | `nv_dongoi` | **Đóng gói** → tạo kiện → lập GI | TMS cấp vận đơn, đơn `READY_TO_SHIP` |
| 5 | `nv_dongoi` | Xác nhận xuất (có chữ ký tài xế) | Đơn `SHIPPED`, trừ tồn, GI vào hàng đợi gửi ERP |
| 6 | `quanly` | Swagger `POST /api/v1/integrations/sync-logs/process` | GRN, GI gửi ERP `SUCCESS` |
| 7 | `bgd` | Tải lại **Tổng quan** | Task xong hôm nay tăng; có 1 GI đã xuất, 1 phiếu nhận đã hoàn tất |

**Biến thể nếu còn thời gian**
- *TMS lỗi:* `POST /api/v1/integrations/mock/failures` `{"system": "TMS", "error_category": "TECHNICAL_ERROR", "times": 3}` trước bước 4: đơn chờ vận đơn, xác nhận xuất bị chặn 409; `quanly` chạy hàng đợi rồi xác nhận lại.
- *FEFO:* SO 10 `SKU-FOOD-001`: cấp phát lấy lô DEMO-SUA-A (gần hết hạn) trước; SO cho `SKU-FOOD-002` báo thiếu vì lô duy nhất đã hết hạn.

## Phần 4 – Kiểm kê (3 phút)

| # | Ai | Làm gì | Thấy gì |
|---|---|---|---|
| 1 | `thukho` | **Kiểm kê** → tạo phiếu cho `LOC-A02-04` | Vị trí khóa `COUNTING_LOCKED`, sinh task kiểm kê |
| 2 | `nv_kiemke` | Đếm mù 37 (hệ thống 40) | Không thấy số hệ thống; lệch tạo hồ sơ duyệt |
| 3 | `thukho` | Duyệt hồ sơ → đóng phiếu | Tồn điều chỉnh 40 → 37, vị trí mở khóa |
