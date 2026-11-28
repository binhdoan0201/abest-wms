# Phân công sửa lỗi sau tổng duyệt – 28/11/2026

Căn cứ: [tong-duyet-2026-11-28.md](tong-duyet-2026-11-28.md). C1, C2, C3 (chí mạng) đã sửa ở bản làm việc của Bình,
**chưa commit**. Lỗi còn lại chia theo module trong `docs/PHAN_CONG.md`.

## 0. Trước khi giao (Bình làm ngay)

1. Commit C1–C3 lên nhánh `fix/demo-c1-c3`, mở PR vào `develop`, merge.
   Các bản sửa này chạm cả file của Phước, Cường, Hiếu (template nhập kho, kiểm kê, soạn hàng, phê duyệt),
   nên **mọi người phải `git pull origin develop` trước khi bắt đầu**, tránh xung đột.
2. Gửi tin nhắn ở mục 5 cho từng người.
3. Hạn đề xuất: PR trước **20:00 hôm nay**; 21:00 Bình merge, tổng duyệt lại, gắn tag `v0.1.1-demo`.

Mỗi người làm một nhánh `fix/<tên-ngắn>`, PR vào `develop`, CI xanh (black, ruff, mypy, pytest), có test cho
phần sửa. Nhớ `reset_db.sh` + `load_demo` rồi tự bấm thử phần mình trên giao diện, không chỉ chạy test.

## 1. Cường (C) – Xuất kho · ưu tiên cao nhất

Lý do: Phần 3 là phần dài nhất của demo, và hiện **không thấy được FEFO trên giao diện**.

| # | Việc | Ở đâu | Xong khi |
|---|---|---|---|
| H1 | Dòng soạn hiện **vị trí lấy, lô, hạn dùng, tên SKU** (allocation đã có `location_id`, `lot_id`) | `client/app/templates/outbound/_pick_panel.html`, view `/outbound/picking` | nv_soan thấy «LOC-A02-01 · Lô DEMO-SUA-A · HSD 04/12/2026 · Sữa tươi…» trên dòng soạn SO 10 `SKU-FOOD-001` |
| H2 | Cấp phát **đọc response**: thiếu hàng (`has_shortage`, đơn `ON_HOLD`) thì cảnh báo vàng thay cho «thành công»; đủ thì hiện lô/vị trí đã giữ | `client/app/modules/outbound/views.py:537` (`outbound_allocate_htmx`) | SO `SKU-FOOD-002` báo thiếu (lô duy nhất đã hết hạn); SO `SKU-FOOD-001` hiện «Giữ 10 tại LOC-A02-01, lô DEMO-SUA-A» |
| H5 | Sau «Xác nhận xuất kho», thẻ thông tin hiện **số GI, `SHIPPED`, mã vận đơn thật** (đang hiện «Phiếu GI: fbce2043 — Trạng thái đơn: *trống* — chờ vận đơn») | `client/app/templates/outbound/_pack_ship_panel.html:7`, view `pack-and-ship` | Xuất xong thấy «GI-… — SHIPPED — TMS…» |
| L | (thấp) Đơn đã `READY_TO_SHIP` ngay khi tạo kiện, trước khi lập GI. Hoặc sửa luồng, hoặc báo Bình sửa lời dẫn kịch bản | outbound services | Thống nhất với Bình |

## 2. Phước (B) – Nhập kho, cất hàng, kiểm kê

| # | Việc | Ở đâu | Xong khi |
|---|---|---|---|
| H3 | Form «Yêu cầu đếm lại» chỉ hiện khi hồ sơ duyệt đang `NEED_INFO` **và** có `REQUEST_RECOUNT` (hiện lộ ngay khi phiếu `PENDING_D1`). Ô nhập **không điền sẵn số đếm cũ** (đang điền 8 và 1, làm lần đếm lại không còn mù) | `client/app/templates/inbound/index.html:164` và các ô `qty_actual`, `qty_damaged` trong form đếm lại | Nộp phiếu xong chưa thấy form; thủ kho bấm «Yêu cầu đếm lại» mới thấy, ô trống |
| H4 | Gợi ý cất hàng **không đưa ô đang chứa SKU khác lên đầu** (đang gợi ý cất bộ dao kéo vào ô sữa cận date) | `server/app/modules/inbound/repositories.py:419`, `ORDER BY has_same_sku DESC, current_capacity_pct DESC` | Thứ tự: ô cùng SKU → ô trống → ô đầy một phần; có test |
| L1 | Đếm lại hết hư (0) thì **dọn pallet `…-DMG`** rỗng, không để `DAMAGED_HOLD` ở `LOC-RCV-01` | `server/app/modules/inbound/services.py:799`, `:1090` | Sau kịch bản Phần 2 không còn pallet DMG |
| L2 | Trạng thái tiếng Việt trên Nhập kho, Kiểm kê (`COUNTING`, `PENDING_D1`, `CLOSED`…): dùng filter `vi_label` có sẵn trong `client/app/core/formatting.py`, thêm mã còn thiếu vào `VI_LABELS` | `inbound/index.html`, `cycle_count/index.html` | Không còn mã tiếng Anh trên 2 trang |
| L3 | Ô «ASN ID (nếu có)» đổi thành dropdown ASN; ô chọn PO giữ lựa chọn sau khi mở phiếu (đang tự quay về «Nhận không PO», dễ lỡ tay mở GRN thứ hai) | `inbound/index.html`, view `/inbound` | Không còn ô gõ UUID |

## 3. Hiếu (D) – Phê duyệt, nhiệm vụ

C1, C2 (module của Hiếu) đã sửa; Hiếu **review PR `fix/demo-c1-c3`** trước, rồi làm tiếp:

| # | Việc | Ở đâu | Xong khi |
|---|---|---|---|
| D1 | Danh sách phê duyệt: mặc định **ẩn hoặc đẩy xuống cuối** hồ sơ đã xong (`SUPERSEDED`, `APPROVED`, `REJECTED`); hồ sơ chờ xử lý lên đầu | `server/app/modules/approvals/repositories.py:188` (đang `created_at ASC`) hoặc lọc mặc định ở client | Mở trang thấy ngay hồ sơ đang chờ |
| D2 | Sau khi duyệt, từ chối hoặc yêu cầu đếm lại, **danh sách bên trái tự tải lại** (đang vẫn hiện trạng thái cũ) | `client/app/templates/approvals/index.html`, `_detail_panel.html` (htmx `HX-Trigger` hoặc `hx-swap-oob`) | Bấm duyệt xong, trạng thái ở danh sách đổi theo |
| D3 | Task cất hàng sinh ra `UNASSIGNED` nên trang Nhiệm vụ của nv_cat trống. **Tự giao luôn khi tạo task** nếu kho bật giao tự động (dùng lại `auto_assign_queue`) | `server/app/modules/tasks/services.py:234` (`create_task`), `:283`; nơi gọi `inbound/services.py:1136` | Hoàn tất GRN xong, nv_cat thấy task cất hàng ngay |
| D4 | Bộ lọc trạng thái phê duyệt bỏ mã tiếng Anh («PENDING_D1 (Chờ Thủ kho)» → «Chờ thủ kho») | `approvals/index.html:12-20` | |
| D5 | Lời dẫn cho buổi demo (việc D4 cũ, chưa có): ai nói, ai bấm, mỗi phần nói gì | `docs/demo/` | Có file lời dẫn |

## 4. Bình (A) – Dashboard, dữ liệu demo, kịch bản, phát hành

| # | Việc | Ở đâu |
|---|---|---|
| A1 | Commit, merge C1–C3 (mục 0); review và merge PR của mọi người; gắn tag `v0.1.1-demo` | |
| A2 | Kịch bản: thêm **JSON dán sẵn** cho 2 lệnh Swagger (`SUPP-001`, `CUST-001`, `cutoff_time` trong tương lai); thêm bước thủ kho «Tự động giao» nếu D3 chưa xong; sửa câu `READY_TO_SHIP` theo kết quả mục 1-L | `docs/demo/kich-ban-demo.md` |
| A3 | Tải Tailwind, htmx về `client/app/static/` để chạy được khi mất mạng | template layout gốc của client |
| A4 | Tổng quan: «Tồn khả dụng» **loại lô đã hết hạn** (đang tính cả 6 bánh mì hết hạn); tỷ lệ `16.7%` → `16,7%` | `server/app/modules/dashboard/repositories.py:142`, `dashboard/_panels.html` (`pct`) |
| A5 | Trang đầu sau đăng nhập: thukho → Phê duyệt hoặc Nhiệm vụ, quanly → Tổng quan (đang vào Tồn kho) | `client/app/core/auth_guard.py` (`HOME_BY_ROLE`) |
| A6 | Seed: đổi «Siêu thị VinMart Central» sang tên hư cấu | `database/seeds/02_master_demo.sql:142` |
| A7 | Tổng duyệt lại toàn bộ bằng tay sau khi merge hết, cập nhật báo cáo | |

## 5. Tin nhắn soạn sẵn

**Gửi Cường**
> Cường ơi, tổng duyệt 28/11 còn 3 lỗi ở Xuất kho, ảnh hưởng trực tiếp Phần 3 demo:
> (H1) dòng soạn chưa có vị trí, lô, HSD, tên SKU nên không thấy FEFO;
> (H2) cấp phát luôn báo «thành công», kể cả khi thiếu hàng;
> (H5) xuất xong thẻ thông tin hiện sai số GI, trạng thái, vận đơn.
> Chi tiết, vị trí code, tiêu chí xong: `docs/reports/phan-cong-sua-loi-2026-11-28.md` mục 1.
> Pull `develop` trước (có bản sửa định dạng số chạm `_pick_panel.html`). PR trước 20:00 nhé.

**Gửi Phước**
> Phước ơi, phần Nhập kho còn 2 lỗi chính:
> (H3) form đếm lại hiện sớm và điền sẵn số đếm cũ, nên lần đếm lại không còn mù;
> (H4) gợi ý cất hàng đưa ô đang chứa SKU khác lên đầu (cất dao kéo vào ô sữa).
> Thêm 3 việc nhỏ L1–L3 nếu kịp. Chi tiết: `docs/reports/phan-cong-sua-loi-2026-11-28.md` mục 2.
> Pull `develop` trước (template nhập kho, kiểm kê đã đổi định dạng số). PR trước 20:00 nhé.

**Gửi Hiếu**
> Hiếu ơi, mình đã sửa 2 lỗi chí mạng ở Phê duyệt: nút đếm lại làm kẹt hồ sơ, và hồ sơ không hiện bảng lệch.
> Nhờ Hiếu review PR `fix/demo-c1-c3` trước, rồi làm tiếp D1–D5:
> danh sách ưu tiên hồ sơ đang chờ, tự tải lại danh sách sau khi duyệt, tự giao task cất hàng, bỏ mã tiếng Anh ở bộ lọc,
> viết lời dẫn demo. Chi tiết: `docs/reports/phan-cong-sua-loi-2026-11-28.md` mục 3. PR trước 20:00 nhé.
