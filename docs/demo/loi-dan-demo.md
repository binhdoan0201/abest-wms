# Lời dẫn buổi Demo Hệ thống ABEST WMS

Tài liệu này phân vai người thuyết trình, người thao tác và lời dẫn chi tiết tương ứng với từng bước trong [kich-ban-demo.md](kich-ban-demo.md).

## Phân vai trình bày
- **Người dẫn chính (A – Bình):** Giới thiệu tổng quan hệ thống, mở đầu vai trò Ban Giám đốc và tổng kết KPI cuối buổi.
- **Người thao tác Nhập & Kiểm kê (B – Phước):** Thực hiện đếm mù, xử lý đếm lại và kiểm kê kho.
- **Người thao tác Xuất kho (C – Cường):** Thực hiện cấp phát FEFO, soạn hàng, đóng gói và xuất kho tích hợp TMS.
- **Người thao tác Phê duyệt & Điều phối (D – Hiếu):** Xử lý hồ sơ lệch đa cấp và giám sát điều phối nhiệm vụ tự động.

---

## Phần 1 – Ban Giám đốc mở đầu (1 phút)
- **Người nói:** Bình (A) | **Người thao tác:** Bình (`bgd`)
- **Thao tác màn hình:** Đăng nhập tài khoản `bgd` → Màn hình **Tổng quan**.
- **Lời dẫn:**
  > "Xin chào thầy/cô và các bạn. Hôm nay nhóm xin trình bày hệ thống quản lý kho **ABEST WMS** với luồng vận hành khép kín từ tiếp nhận đơn hàng ERP, nhập kho, kiểm soát chênh lệch đa cấp, điều phối nhiệm vụ tự động đến xuất kho và kiểm kê.
  > Mở đầu ở góc nhìn Ban Giám đốc (`bgd`), ngay sau khi đăng nhập, màn hình **Tổng quan** hiển thị tức thời các cảnh báo vận hành trọng yếu: hệ thống đang phát hiện 1 lô hàng đã hết hạn còn tồn trong kho, 1 lô sữa sắp cận hạn sử dụng và các mã hàng dưới mức tồn tối thiểu để lãnh đạo nắm bắt ngay."

---

## Phần 2 – Nhập kho có chênh lệch, Phê duyệt đa cấp & Cất hàng (5 phút)
- **Người nói:** Phước (B) & Hiếu (D) | **Người thao tác:** `admin` (Swagger), `nv_nhan`, `thukho`, `nv_nhan2`, `nv_cat`
- **Thao tác & Lời dẫn chi tiết:**
  1. **Nhận đơn mua hàng từ ERP (`admin` – Swagger):**
     > "Đầu tiên, hệ thống ERP đẩy đơn mua hàng gồm 10 bộ sản phẩm `SKU-GEN-008` sang WMS qua API tích hợp. Nhật ký đồng bộ ghi nhận trạng thái thành công."
  2. **Đếm mù tại cửa nhận (`nv_nhan`):**
     > "Nhân viên nhận hàng (`nv_nhan`) mở phiếu nhập từ đơn mua hàng này. Để đảm bảo tính khách quan, hệ thống áp dụng cơ chế **đếm mù** — không hiển thị số lượng đặt trên đơn. Nhân viên đếm thực tế được 8 bộ đạt chuẩn và 1 bộ hư hỏng kèm mã lý do, sau đó nộp phiếu. Vì phát sinh chênh lệch thiếu 1 bộ, hệ thống tự động đưa hàng hư vào pallet cách ly và chuyển phiếu sang trạng thái chờ Thủ kho phê duyệt."
  3. **Thẩm định & Yêu cầu đếm lại (`thukho` — Hiếu nói & bấm):**
     > "Chuyển sang giao diện **Phê duyệt** của Thủ kho (`thukho`), các hồ sơ đang chờ xử lý luôn được ưu tiên xếp trên đầu danh sách. Khi mở hồ sơ, Thủ kho xem được trực tiếp bảng đối chiếu chi tiết từng dòng chênh lệch từ phiếu nhập mà không cần mở sang phân hệ khác. Nhận thấy có chênh lệch, Thủ kho nhập ghi chú và bấm **Yêu cầu đếm lại** — danh sách bên trái lập tức cập nhật trạng thái sang chờ bổ sung/đếm lại."
  4. **Kiểm soát chéo & Đếm lại lần 2 (`nv_nhan` → `nv_nhan2`):**
     > "Nếu chính nhân viên `nv_nhan` ban đầu bấm đếm lại, hệ thống sẽ chặn để đảm bảo nguyên tắc kiểm soát chéo. Nhân viên thứ hai (`nv_nhan2`) đăng nhập, thực hiện đếm lại mù và ghi nhận đủ 10 bộ đạt chuẩn, không hư hỏng. Khi nộp kết quả mới, hồ sơ duyệt cũ tự động chuyển sang trạng thái thay thế và phiếu nhập được thông qua."
  5. **Hoàn tất nhập kho & Tự động giao việc cất hàng (`nv_nhan` → `nv_cat` — Hiếu nhấn mạnh):**
     > "`nv_nhan` bấm hoàn tất phiếu nhập: tồn kho được ghi nhận tại cửa nhận, pallet chuyển sang trạng thái chờ cất và chứng từ tự động xếp vào hàng đợi đồng bộ ngược về ERP. Đồng thời, hệ thống tự sinh nhiệm vụ **Cất hàng** và giao thẳng cho nhân viên cất hàng (`nv_cat`). Trên màn hình **Nhiệm vụ** của `nv_cat`, task mới hiện sẵn người nhận; bấm **Mở** sẽ đi thẳng tới phiếu nhập để xem gợi ý vị trí cất hàng tối ưu và xác nhận cất lên kệ."

---

## Phần 3 – Xuất kho theo FEFO, Đóng gói & Tích hợp TMS (5 phút)
- **Người nói:** Cường (C) & Bình (A) | **Người thao tác:** `admin`, `thukho`, `nv_soan`, `nv_dongoi`, `quanly`, `bgd`
- **Thao tác & Lời dẫn chi tiết:**
  1. **Nhận đơn xuất từ ERP & Cấp phát tồn kho (`admin` → `thukho`):**
     > "Tiếp theo là quy trình xuất kho. ERP gửi đơn xuất 10 bộ `SKU-GEN-008`. Thủ kho thực hiện cấp phát tồn kho và tạo phiên soạn hàng giao cho `nv_soan` (ngoài ra với hàng có hạn sử dụng như sữa tươi `SKU-FOOD-001`, hệ thống tự động ưu tiên giữ lô có hạn dùng gần nhất theo nguyên tắc **FEFO** và chặn cấp phát nếu lô đã hết hạn)."
  2. **Soạn hàng thực tế (`nv_soan`):**
     > "Nhân viên soạn hàng (`nv_soan`) mở phiên soạn, thấy rõ vị trí kệ, mã lô và hạn sử dụng cần lấy, sau đó xác nhận hoàn tất từng dòng soạn."
  3. **Đóng gói, Gọi vận đơn TMS & Xác nhận xuất (`nv_dongoi`):**
     > "Tại khâu đóng gói (`nv_dongoi`), nhân viên tạo kiện hàng và lập phiếu xuất kho (GI). Hệ thống tự động gọi sang dịch vụ vận tải **TMS** để lấy mã vận đơn thật và chuyển đơn sang sẵn sàng giao. Sau khi tài xế ký xác nhận, nhân viên bấm **Xác nhận xuất kho**: tồn kho chính thức được trừ, đơn chuyển sang đã xuất và phiếu GI được đưa vào hàng đợi gửi về ERP."
  4. **Đồng bộ ERP & Cập nhật KPI Tổng quan (`quanly` → `bgd`):**
     > "Quản lý chạy xử lý hàng đợi tích hợp để đẩy toàn bộ dữ liệu nhập/xuất về ERP. Quay lại màn hình **Tổng quan** của Ban Giám đốc, các chỉ số hoàn thành nhiệm vụ trong ngày, phiếu nhập hoàn tất và phiếu xuất đã giao đều được cập nhật tức thời."

---

## Phần 4 – Kiểm kê định kỳ & Điều chỉnh tồn kho (3 phút)
- **Người nói:** Phước (B) & Hiếu (D) | **Người thao tác:** `thukho`, `nv_kiemke`
- **Thao tác & Lời dẫn chi tiết:**
  1. **Tạo phiếu kiểm kê & Khóa vị trí (`thukho`):**
     > "Cuối cùng là nghiệp vụ kiểm kê. Thủ kho tạo phiếu kiểm kê tại vị trí `LOC-A02-04`. Ngay lập tức, vị trí này được khóa giao dịch để tránh biến động tồn trong lúc đếm và sinh nhiệm vụ kiểm kê."
  2. **Đếm mù & Phê duyệt điều chỉnh (`nv_kiemke` → `thukho`):**
     > "Nhân viên kiểm kê (`nv_kiemke`) thực hiện đếm mù và ghi nhận thực tế 37 sản phẩm so với 40 sản phẩm trên sổ sách. Hệ thống tự động lập hồ sơ duyệt chênh lệch kiểm kê. Thủ kho mở danh sách **Phê duyệt**, kiểm tra chi tiết lệch -3 sản phẩm, bấm **Phê duyệt** — danh sách tự động cập nhật trạng thái, sau đó đóng phiếu kiểm kê để điều chỉnh tồn kho về đúng 37 và mở khóa lại vị trí."
