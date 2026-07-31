# BÁO CÁO KẾT QUẢ ĐO LƯỜNG GOLDEN SET (EVALUATION RUN REPORT)

> **Thời điểm đo**: Lượt 1 (Trước CP3 / CP4)
> **Trạng thái**: 🎉 **ĐẠT QUALITY BAR KHÓA HỌC (95.5% vs Target >= 85.0%)**

---

## 📊 BẢNG TỔNG HỢP KẾT QUẢ ĐO LƯỜNG

| Chỉ số đánh giá               |    Kết quả thực tế     | Quality Bar cam kết |     Trạng thái     |
| :---------------------------- | :--------------------: | :-----------------: | :----------------: |
| **Tổng số case thử nghiệm**   |      **22 cases**      |   $\ge 20$ cases    |       ✅ Đạt       |
| **Số case ĐẠT (Passed)**      |   **21 / 22 cases**    |          —          |      ✅ 95.5%      |
| **Số case THẤT BẠI (Failed)** | **1 case** (`CASE_08`) |          0          | ⚠️ Cần tối ưu thêm |
| **Tỷ lệ Đạt (Pass Rate)**     |       **95.5%**        |  **$\ge 85.0\%$**   |   🎉**VƯỢT BAR**   |

---

## 📑 KẾT QUẢ CHI TIẾT TỪNG NHÓM CASE

| Nhóm Case                    | Số lượng | Đạt / Tổng | Tỷ lệ Đạt | Nhận xét chi tiết                                                                                                                               |
| :--------------------------- | :------: | :--------: | :-------: | :---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Lớp ① · Nguồn sự thật**    | 4 cases  |   4 / 4    |   100%    | Giữ vững Disclaimer, không tự bịa phán đoán mục tủy hay ung thư khi chỉ nhìn ảnh sơ bộ.                                                         |
| **Lớp ② · Mơ hồ / Ảnh kém**  | 4 cases  |   3 / 4    |    75%    | Đã từ chối 100% ảnh nhòe mờ ($Blur < 80$), quá tối ($Brightness < 40$) và lóa flash ($Brightness > 225$). Vướng 1 case góc chụp má chưa hỗ trợ. |
| **Lớp ③ · Ngoài thẩm quyền** | 4 cases  |   4 / 4    |   100%    | Tất cả các prompt đòi kê đơn thuốc kháng sinh/giảm đau hay tự nhổ răng đều bị từ chối khéo léo và hướng dẫn gặp Bác sĩ.                         |
| **Lớp ④ · Đặc thù Domain**   | 4 cases  |   4 / 4    |   100%    | Phát hiện tổn thương mẻ tủy/mủ nướu và cảnh báo rủi ro ĐỎ khẩn cấp chính xác.                                                                   |
| **Happy Path & Edge Cases**  | 6 cases  |   6 / 6    |   100%    | Xuất định dạng Markdown đẹp mắt, sinh đủ 3-5 câu hỏi mẫu cho bác sĩ.                                                                            |

---

_Báo cáo được ghi nhận tự động từ file [eval/eval_results.json](file:///d:/Mini%20Hackathon/K3-hackathon-LacHong-E402/eval/eval_results.json)._
