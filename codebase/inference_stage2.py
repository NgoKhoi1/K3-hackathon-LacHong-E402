import os
import json

def load_dotenv_custom():
    """Tự động đọc file .env ở gốc dự án mà không cần cài thư viện ngoài"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    env_file = os.path.join(project_root, ".env")
    
    if not os.path.exists(env_file):
        env_file = os.path.join(current_dir, ".env")

    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")
        except Exception:
            pass

# Tự động nạp môi trường khi import
load_dotenv_custom()

class DentalStage2AdvicePipeline:
    """
    Giai đoạn 2: Tích hợp LLM sinh Báo cáo & Lời khuyên kèm Chốt chặn An toàn Y tế (Safety Guardrails)
    Hỗ trợ cả OpenAI API (GPT-4o / GPT-4o-mini) lẫn Gemini API.
    """

    def __init__(self, api_key=None, provider="openai"):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.api_key = api_key or self.openai_key or self.gemini_key

    def build_system_prompt(self):
        prompt = """
Bạn là "Trợ lý Tầm soát Sức khỏe Nha khoa sơ bộ" phục vụ người dùng tại nhà.

QUY TẮC AN TOÀN Y TẾ BẮT BUỘC (SAFETY GUARDRAILS):
1. KHÔNG PHẢN ĐOÁN XÁC ĐỊNH: Bạn không phải bác sĩ y khoa. Tuyệt đối KHÔNG dùng các từ khẳng định như "Bạn bị ung thư", "Bạn chắc chắn bị viêm quanh răng". Luôn dùng thuật ngữ tầm soát sơ bộ: "Phát hiện dấu hiệu nghi ngờ...", "Quan sát thị giác cho thấy...".
2. KHÔNG KÊ ĐƠN THUỐC: Tuyệt đối KHÔNG chỉ định, kê đơn hay tư vấn bất kỳ tên thuốc nào (kháng sinh, giảm đau, chống viêm...). Nếu người dùng đòi kê đơn, kiên quyết từ chối và khuyên đi khám bác sĩ.
3. KHÔNG NÓI XUÔNG: Mỗi khuyến nghị phải gắn liền với kết quả phát hiện thị giác từ Giai đoạn 1.
4. MIỄN TRỪ TRÁCH NHIỆM: Luôn hiển thị thông điệp miễn trừ trách nhiệm y khoa ở đầu và cuối báo cáo.

ĐỊNH DẠNG ĐẦU RA YÊU CẦU:
Trả về phản hồi theo định dạng Markdown đẹp mắt gồm 4 phần:
- 🔴/🟡/🟢 **ĐÁNH GIÁ MỨC ĐỘ RỦI RO**: (Xanh: Thấp · Vàng: Trung bình · Đỏ: Cao - Khẩn cấp)
- 📋 **TÓM TẮT PHÁT HIỆN THỊ GIÁC**: Diễn giải ngắn gọn các tổn thương bằng ngôn ngữ bình dân.
- 🪥 **HƯỚNG DẪN CHĂM SÓC TẠI NHÀ**: 3-4 lời khuyên vệ sinh răng miệng phù hợp.
- 🩺 **DANH SÁCH CÂU HỎI KHI GẶP BÁC SĨ NHA KHOA**: 3-5 câu hỏi cụ thể để người dùng cầm đi hỏi bác sĩ khi tới phòng khám.
        """
        return prompt.strip()

    def generate_advice(self, stage1_json, user_question=""):
        if stage1_json.get("status") == "REJECTED":
            return f"⚠️ **TỪ CHỐI XỬ LÝ**: {stage1_json.get('message')}"

        anomalies = stage1_json.get("detected_anomalies", [])
        metrics = stage1_json.get("summary_metrics", {})
        urgency = metrics.get("urgency_level", "GREEN")

        urgency_map = {
          "GREEN": "🟢 RỦI RO THẤP - Tình trạng bình thường / Mảng bám nhẹ",
          "YELLOW": "🟡 RỦI RO TRUNG BÌNH - Cần theo dõi & đi lấy vôi răng / trám sớm",
          "RED": "🔴 RỦI RO CAO - Cần sắp xếp gặp Bác sĩ Nha khoa sớm!"
        }

        # Kiểm tra từ khóa cấm kê đơn thuốc
        forbidden_keywords = ["kê đơn", "thuốc kháng sinh", "uống thuốc gì", "cho tôi đơn thuốc", "uống amoxicillin", "uống efferalgan", "uống paracetamol"]
        if any(kw in user_question.lower() for kw in forbidden_keywords):
            return f"""
> ⚠️ **CẢNH BÁO MIỄN TRỪ TRÁCH NHIỆM Y KHOA**: AI chỉ hỗ trợ tầm soát hình ảnh thị giác sơ bộ, không có giá trị chẩn đoán hoặc kê đơn thuốc.

### 🚫 TỪ CHỐI KÊ ĐƠN THUỐC
Hệ thống **KHÔNG KÊ ĐƠN THUỐC** hoặc chỉ định tên bất kỳ loại thuốc nào (kháng sinh, giảm đau...). Việc tự ý mua và sử dụng thuốc không qua thăm khám bác sĩ có thể gây ra nhiều biến chứng nguy hiểm.

### 🩺 KHUYẾN NGHỊ HÀNH ĐỘNG
1. Bạn vui lòng liên hệ phòng khám hoặc bệnh viện nha khoa gần nhất để được bác sĩ thăm khám và kê đơn chuẩn xác.
2. Nếu bị đau/sưng, bạn có thể súc miệng bằng nước muối sinh lý 0.9% hoặc chườm đá lạnh ngoài má để giảm cảm giác khó chịu tạm thời.
            """.strip()

        # Re-check API keys từ môi trường
        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")

        user_prompt = f"""
Dữ liệu phân tích thị giác từ Giai đoạn 1:
{json.dumps(stage1_json, ensure_ascii=False, indent=2)}

Câu hỏi bổ sung từ người dùng (nếu có): "{user_question}"

Hãy sinh báo cáo tư vấn theo đúng quy tắc và định dạng bắt buộc.
        """

        # 1. Thử dùng OPENAI API nếu có key
        if openai_key:
            try:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",  # Nhanh & Rẻ tối ưu cho Hackathon
                    messages=[
                        {"role": "system", "content": self.build_system_prompt()},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"⚠️ Lỗi OpenAI API ({e}) -> Thử chuyển sang Gemini hoặc Fallback.")

        # 2. Thử dùng GEMINI API nếu có key
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                res = model.generate_content([self.build_system_prompt(), user_prompt])
                return res.text
            except Exception as e:
                print(f"⚠️ Lỗi Gemini API ({e}) -> Dùng phản hồi dự phòng.")

        # 3. Phản hồi dự phòng (Fallback) khi chưa có API Key
        return self._generate_fallback_advice(anomalies, urgency_map.get(urgency, "GREEN"), user_question)

    def _generate_fallback_advice(self, anomalies, urgency_text, user_question):
        anom_text = "\n".join([f"- **{a['class_name']}** (Độ tin cậy: {int(a['confidence']*100)}%): Phát hiện tại khu vực răng hàm" for a in anomalies]) if anomalies else "- Không phát hiện tổn thương bất thường lớn."

        report = f"""
> ⚠️ **CẢNH BÁO MIỄN TRỪ TRÁCH NHIỆM Y KHOA**: Kết quả dưới đây chỉ mang tính chất tầm soát hình ảnh thị giác sơ bộ bằng AI, không có giá trị chẩn đoán y khoa thay thế Bác sĩ Nha khoa.

### 🚦 ĐÁNH GIÁ MỨC ĐỘ RỦI RO
**{urgency_text}**

### 📋 TÓM TẮT PHÁT HIỆN THỊ GIÁC
{anom_text}

### 🪥 HƯỚNG DẪN CHĂM SÓC TẠI NHÀ
1. **Đánh răng đúng cách**: Sử dụng bàn chải lông mềm, chải nhẹ nhàng theo chiều dọc 2 lần/ngày.
2. **Sử dụng chỉ nha khoa**: Làm sạch kẽ răng sau mỗi bữa ăn thay vì dùng tăm xỉa răng.
3. **Nước súc miệng**: Dùng nước súc miệng chứa Fluoride hoặc nước muối sinh lý 0.9%.

### 🩺 DANH SÁCH CÂU HỎI THAM KHẢO KHI ĐẾN PHÒNG KHÁM NHA KHOA
1. *"Bác sĩ kiểm tra giúp tôi vị trí phát hiện đốm nâu/vệt đen này có cần xử lý trám răng ngay không?"*
2. *"Tình trạng mảng bám vôi răng của tôi có cần tiến hành cạo vôi răng chuyên sâu không?"*
3. *"Tôi nên thay đổi thói quen vệ sinh răng miệng như thế nào để tránh nguy cơ tái phát?"*

---
*Báo cáo được khởi tạo tự động bởi Hệ thống AI Tầm soát Nha khoa Sơ bộ.*
        """
        return report.strip()

if __name__ == "__main__":
    advice_pipeline = DentalStage2AdvicePipeline()
    print("=== DENTAL STAGE 2 ADVICE PIPELINE READY (OPENAI & GEMINI SUPPORTED) ===")
