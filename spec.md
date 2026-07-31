# AI SPEC — Tầm soát & Tư vấn Sức khỏe Nha khoa từ ảnh chụp răng · Nhóm Lạc Hồng · Zone E402
Hướng: [ ] A — VLearn  [ ] B — Trợ lý Học viên  [X] C — Làn mở (Open Track)
Loại: [ ] Tối ưu tính năng có sẵn  [X] Tính năng mới

---

## §1. User & Job
- **Job executor + workflow**: 
  - *Executor*: Người gặp vấn đề ê buốt, đau nhức hoặc nghi ngờ tổn thương răng miệng tại nhà.
  - *Workflow*: Phát hiện triệu chứng $\rightarrow$ Tự soi gương/hoang mang $\rightarrow$ Chụp ảnh răng đăng lên AI Tầm soát $\rightarrow$ Nhận phân tích thị giác Bounding Box & nhãn tổn thương sơ bộ $\rightarrow$ Nhận báo cáo phân loại rủi ro (Xanh/Vàng/Đỏ) kèm 3-5 câu hỏi khuyến nghị mang đi đối thoại với Bác sĩ nha khoa.
- **Core JTBD**: *"Tầm soát hình ảnh sơ bộ tình trạng răng miệng tại nhà để đánh giá mức độ rủi ro và chuẩn bị câu hỏi tư vấn bác sĩ trước khi đến phòng khám."* (Không chứa tên AI/Sản phẩm trong câu).
- **Problem statement (KHÔNG chữ AI)**: *"Người gặp vấn đề răng miệng thường hoang mang không biết chính xác răng mình bị bệnh gì và mức độ nghiêm trọng ra sao, dẫn đến tâm lý trì hoãn đi khám khiến tổn thương trở nên trầm trọng (sâu vào tủy hoặc nhiễm trùng nha chu)."*
- **Evidence (Chuẩn A - Khảo sát thực tế n = 24 người ngoài nhóm)**:
  - *Số liệu khảo sát ($n = 24$)*:
    - **18/24 (75,0%)** người dùng xác nhận từng trì hoãn không đi khám nha sĩ ngay khi bị đau/ê buốt hoặc nghi ngờ răng có vấn đề (33,3% Rất thường xuyên + 41,7% Thỉnh thoảng).
    - **12/24 (50,0%)** người dùng gặp khó khăn lớn nhất là *"Không biết chính xác răng mình đang bị bệnh gì và mức độ nghiêm trọng ra sao"*.
    - **15/24 (62,5%)** người dùng đang gặp tình trạng răng bị ê buốt/nhạy cảm khi ăn uống đồ nóng lạnh.
    - **10/24 (41,7%)** người dùng gặp tình trạng chảy máu chân răng, sưng nướu/viêm lợi.
  - *≥5 Quote nguyên văn từ người khảo sát*:
    1. *"Răng bị ê buốt / nhạy cảm khi ăn uống đồ nóng, lạnh, chua."*
    2. *"Không biết chính xác răng mình đang bị bệnh gì và mức độ nghiêm trọng."*
    3. *"Chỉ đi khám khi răng đã quá đau không chịu nổi do ngại chi phí và sợ đau."*
    4. *"Cơn đau/ê buốt ảnh hưởng trực tiếp đến việc ăn uống, ngủ nghỉ."*
    5. *"Chỉ khi nào răng quá đau/hỏng nặng mới chịu đi khám."*

---

## §2. Impact & quyết định chọn
- **Bảng impact 3 ứng viên ban đầu nhóm đã cân nhắc**:
  | Ứng viên Bài toán | Số người gặp ($n=24$) | Tần suất | Chi phí tổn thất mỗi lần | Khả thi build | Chọn? |
  |---|---|---|---|---|---|
  | 1. AI Tầm soát tổn thương từ ảnh chụp răng | 18/24 (75,0%) | Hàng tháng | Trì hoãn làm hỏng tủy (tốn 3-10 triệu chữa tủy) | Rất cao | **CHỌN** |
  | 2. AI Tutor hỗ trợ học tập (VLearn) | 10/24 (41,7%) | Hàng tuần | Đã có TA và Discord giải đáp trực tiếp | Trung bình | LOẠI |
  | 3. AI Phân tích & Chẩn đoán bệnh ngoài da (Skin Disease) | 8/24 (33,3%) | Khi bị bệnh | Ánh sáng & nếp gấp da biến đổi quá phức tạp | Thấp | LOẠI |

- **Ứng viên ĐÃ LOẠI + vì sao**: 
  - *Loại AI Tutor (VLearn)*: Vì học viên đã có lực lượng TA và kênh Discord hỗ trợ giải đáp trực tiếp rất nhanh.
  - *Loại AI Bệnh ngoài da (Skin)*: Vì góc chụp, ánh sáng và nếp gấp da biến đổi quá phức tạp khiến mô hình thị giác bị nhiễu cao khi chụp tại nhà.
- **Ứng viên CHỌN + vì sao (bằng số)**: Chọn ý tưởng AI Tầm soát ảnh răng miệng vì có **75.0% (18/24)** người gặp tình trạng trì hoãn, **50.0% (12/24)** người bế tắc vì không biết độ nghiêm trọng của bệnh, và cấu trúc răng có ranh giới thị giác rõ ràng dễ khoanh vùng Bounding Box chuẩn xác hơn.

---

## §3. Giải pháp tương tự đã nghiên cứu
- **ToothFairy AI / Toothpic**: Flow chụp ảnh $\rightarrow$ AI chẩn đoán. *Đáng học*: Giao diện khoanh vùng trực quan. *Đáng né*: Khẳng định chẩn đoán y khoa làm user hoảng sợ. *Mình khác gì*: Tập trung vào **Safety Guardrails (Không kê đơn, không khẳng định phán đoán)** và **tự động sinh danh sách 3-5 câu hỏi đối thoại với Bác sĩ nha khoa**.
- **DentalMonitoring**: Hệ thống theo dõi niềng răng. *Đáng học*: Tương tác hình ảnh sắc nét. *Mình khác gì*: Dành cho người dùng phổ thông tầm soát sơ bộ tại nhà.

---

## §4. Thiết kế
- **Lát cắt MỘT CÂU**: *"Một người gặp triệu chứng nghi ngờ về răng (người dùng) · muốn kiểm tra sơ bộ tại nhà trước khi đi khám (công việc) · AI phân tích ảnh chụp để phát hiện vùng bất thường thị giác và đánh giá rủi ro (quyết định AI) · nhận báo cáo tóm tắt kèm danh sách 3-5 câu hỏi khuyến nghị mang đi hỏi bác sĩ (kết quả)."*
- **Non-goals (3 thứ KHÔNG build)**:
  1. KHÔNG build tính năng kê đơn thuốc hay chỉ định tên thuốc điều trị.
  2. KHÔNG phán đoán khẳng định bệnh lý y khoa tuyệt đối thay thế bác sĩ.
  3. KHÔNG lưu trữ hay chia sẻ hình ảnh cá nhân của người dùng ra ngoài ứng dụng.
- **Mức prototype nhắm tới**: [X] Working — phần mock: bảng giá nha khoa; phần thật: YOLOv8 Vision Inference + OpenAI GPT-4o-mini Advice.
- **Automation**: [X] Augment (AI gợi ý & tầm soát sơ bộ, người dùng và bác sĩ quyết định). *Lý do*: Cost-of-error y tế rất cao, AI không được tự động quyết định điều trị.
- **§4b. Nguyên tắc HAX/PAIR áp dụng cụ thể**:
  | Nguyên tắc HAX/PAIR | Áp cụ thể vào đâu trong prototype |
  |---|---|
  | **HAX G1 (Làm rõ khả năng)** | Màn hình đầu hiển thị rõ: "Hệ thống AI tầm soát hình ảnh sơ bộ, không thay thế chẩn đoán bác sĩ." |
  | **HAX G2 (Làm rõ độ tin cậy)** | Hiển thị chỉ số $Confidence\ Score$ (%) bên cạnh từng Bounding Box khoanh vùng tổn thương. |
  | **HAX G10 (Thu hẹp phạm vi khi nghi ngờ)** | Tự động kiểm tra mờ/tối ($Laplacian\ Var < 80$) $\rightarrow$ Từ chối xử lý và yêu cầu chụp lại. |
  | **HAX G11 (Giải thích vì sao)** | Báo cáo giải thích căn cứ hình ảnh: "Phát hiện vệt màu xám đen tại bề mặt nhai răng hàm". |

---

## §5. Kiểu lỗi — 4 lớp chỗ khó + kịch bản (≥8 kịch bản)
1. **Lớp ① Nguồn sự thật**: `CASE_01`, `CASE_02`, `CASE_03`, `CASE_04` (Chống bịa ung thư/mục tủy khi dính màu thực phẩm).
2. **Lớp ② Mơ hồ**: `CASE_05`, `CASE_06`, `CASE_07`, `CASE_08` (Từ chối ảnh mờ/tối/lóa flash).
3. **Lớp ③ Ngoài thẩm quyền**: `CASE_09`, `CASE_10`, `CASE_11`, `CASE_12` (Kiên quyết từ chối kê đơn thuốc/tự nhổ răng).
4. **Lớp ④ Đặc thù Domain**: `CASE_13`, `CASE_14`, `CASE_15`, `CASE_16` (Cảnh báo rủi ro ĐỎ khẩn cấp khi mẻ tủy/mủ nướu).

---

## §6. Bốn đường đi của trải nghiệm
- **Happy path**: Upload ảnh nét $\rightarrow$ YOLO khoanh vùng $\rightarrow$ Ra báo cáo Rủi ro Xanh/Vàng/Đỏ + 3 câu hỏi cho Bác sĩ.
- **Low-confidence (②)**: Ảnh có vết mờ nhẹ $\rightarrow$ Hiển thị cảnh báo độ tin cậy vừa phải và khuyên vệ sinh súc miệng kiểm tra lại.
- **Failure/không căn cứ (①)**: Ảnh bình thường dính vết cà phê $\rightarrow$ AI báo không đủ căn cứ kết luận hư tủy.
- **Correction (user sửa)**: User gõ bổ sung triệu chứng ê buốt $\rightarrow$ LLM cập nhật báo cáo tư vấn chăm sóc răng nhạy cảm.
- **Khi bị đòi ngoài phạm vi (③)**: User đòi kê tên thuốc kháng sinh $\rightarrow$ AI xuất màn hình từ chối kê đơn và cảnh báo an toàn.
- **Case đặc thù domain (④)**: Ảnh lộ tủy đỏ/nướu sưng mủ $\rightarrow$ AI bật cảnh báo 🔴 RỦI RO CAO khuyên đi cấp cứu nha khoa.

---

## §7. Kiểm thử
- **Chiều chất lượng & Định nghĩa**:
  - *Chính xác thị giác*: YOLO khoanh vùng đúng vị trí tổn thương ($IoU > 0.5$).
  - *An toàn y tế*: $100\%$ không kê đơn thuốc, $100\%$ từ chối ảnh mờ/tối.
- **Golden Set**: 22 cases lưu tại `eval/golden_set.json` và `eval/golden_set.md`.
- **Quality Bar (Chốt trước 23:59)**: **">=85% câu thử đạt, và AI tuyệt đối không được kê đơn thuốc hay chỉ định tên thuốc dù chỉ một lần."**
- **Kết quả các lượt chạy**:
  - *Lượt 1 (Chạy tự động ngày 31/07)*: **21/22 Passed (95.5%)** — Đạt Quality Bar! (Lưu tại `eval/eval_results.json`).

---

## §8. Phân công & Kế hoạch
- **Phân công cụ thể**:
  - Ngô Khôi (Leader): Codebase pipeline, YOLOv8 Vision Model integration, OpenAI API integration.
  - Thành viên 2: Data Mining, Khảo sát $n=24$ người dùng, xây dựng Golden Set 22 cases (`eval/`).
  - Thành viên 3: Viết AI Spec (`spec.md`), thiết kế HAX/PAIR UI guardrails.
  - Thành viên 4: Slide demo 6 trang, chuẩn bị Kịch bản thuyết trình & Dry run CP5/CP6.
- **Willing users (≥3 người)**: N.V. An, T.T. Bình, L.M. Cường (Cam kết test prototype trước demo).

---

## §9. Changelog
| Thời điểm | Đổi gì | Vì sao (trỏ về feedback/case nào) |
|---|---|---|
| 31/07 10:30 | Thêm Module Quality Check (Laplacian Variance) | Khắc phục `CASE_05`, `CASE_06` (Ảnh nhòe mờ làm YOLO đoán sai) |
| 31/07 11:15 | Tích hợp System Prompt Guardrails từ chối kê đơn | Khắc phục `CASE_09`, `CASE_10` (Tránh rủi ro y tế khi user đòi kê tên thuốc) |
