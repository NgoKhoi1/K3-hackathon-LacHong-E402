import os
import sys
import json

# Đảm bảo import được codebase
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from inference_stage1 import DentalStage1VisionPipeline
from inference_stage2 import DentalStage2AdvicePipeline

class DentalAIPipeline:
    """
    Toàn bộ Pipeline End-to-End: Kết nối Giai đoạn 1 (Vision YOLO) & Giai đoạn 2 (LLM Advice)
    """

    def __init__(self, model_path=None, api_key=None):
        print("🚀 Đang khởi tạo Hệ thống AI Tầm soát Nha khoa (End-to-End Pipeline)...")
        self.stage1 = DentalStage1VisionPipeline(model_path=model_path)
        self.stage2 = DentalStage2AdvicePipeline(api_key=api_key)

    def process_dental_image(self, image_path, user_question=""):
        print(f"\n📸 [Giai đoạn 1] Đang phân tích ảnh: {image_path}...")
        stage1_output = self.stage1.run_detection(image_path)
        
        print("\n📊 Kết quả JSON từ Giai đoạn 1:")
        print(json.dumps(stage1_output, ensure_ascii=False, indent=2))

        print("\n🧠 [Giai đoạn 2] Đang tạo báo cáo & lời khuyên y tế...")
        advice_report = self.stage2.generate_advice(stage1_output, user_question=user_question)

        return {
            "stage1_vision_json": stage1_output,
            "final_report_markdown": advice_report
        }

if __name__ == "__main__":
    pipeline = DentalAIPipeline()
    
    # Tạo một file ảnh test mẫu
    sample_image = os.path.join(current_dir, "sample_teeth.jpg")
    if not os.path.exists(sample_image):
        import cv2
        import numpy as np
        dummy_img = np.full((640, 640, 3), 200, dtype=np.uint8)
        cv2.putText(dummy_img, "Test Teeth Image", (150, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.imwrite(sample_image, dummy_img)

    result = pipeline.process_dental_image(sample_image, user_question="Tôi cảm thấy ê buốt khi uống nước lạnh")

    print("\n" + "="*60)
    print("🎉 KẾT QUẢ BÁO CÁO CUỐI CÙNG (END-TO-END DEMO):")
    print("="*60)
    print(result["final_report_markdown"])
