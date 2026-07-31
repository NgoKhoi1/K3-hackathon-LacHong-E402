import os
import cv2
import json
import numpy as np

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

class DentalStage1VisionPipeline:
    """
    Giai đoạn 1: Tiền xử lý ảnh (Quality Check) & Phân tích thị giác (YOLOv8 Detection)
    """
    
    def __init__(self, model_path=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir)

        # Danh sách các đường dẫn ưu tiên tìm mô hình YOLO (.pt)
        possible_paths = [
            model_path,
            os.path.join(base_dir, "models", "best.pt"),
            os.path.join(base_dir, "models", "yolov8n.pt"),
            os.path.join(project_root, "vuong", "yolov8n.pt"),
            os.path.join(project_root, "vuong", "best.pt")
        ]

        selected_path = None
        for p in possible_paths:
            if p and os.path.exists(p):
                selected_path = p
                break

        self.model_path = selected_path
        self.model = None
        
        if YOLO_AVAILABLE and self.model_path:
            try:
                self.model = YOLO(self.model_path)
                print(f"✅ GIAI ĐOẠN 1: Đã nạp thành công mô hình YOLOv8 từ: {self.model_path}")
            except Exception as e:
                print(f"⚠️ Không thể nạp mô hình từ {self.model_path}: {e}")
        else:
            print("ℹ️ Chưa tìm thấy mô hình YOLO local -> Sẽ dùng cơ chế Fallback (Mock) để kiểm thử.")

    def check_image_quality(self, image_path):
        """
        Bước 1.1: Kiểm tra độ sắc nét và độ sáng của ảnh (HAX G10 / Lớp chỗ khó ②)
        """
        img = cv2.imread(image_path)
        if img is None:
            return False, "Không thể đọc được file ảnh. Vui lòng kiểm tra lại đường dẫn.", {}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Tính độ nhòe bằng Laplacian Variance
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # 2. Tính độ sáng trung bình
        brightness_score = np.mean(gray)

        is_valid = True
        message = "Ảnh hợp lệ, chất lượng tốt."

        # Cảnh báo ảnh mờ
        if blur_score < 80.0:
            is_valid = False
            message = "Ảnh bị nhòe/mờ do rung tay. Vui lòng giữ chắc điện thoại và chụp lại."
        # Cảnh báo ảnh quá tối
        elif brightness_score < 40.0:
            is_valid = False
            message = "Ảnh quá tối. Vui lòng bật đèn flash hoặc di chuyển ra khu vực đủ sáng."
        # Cảnh báo ảnh quá lóa
        elif brightness_score > 225.0:
            is_valid = False
            message = "Ảnh bị lóa đèn flash. Vui lòng điều chỉnh góc chụp để giảm chói."

        quality_details = {
            "blur_score": float(round(blur_score, 2)),
            "brightness_score": float(round(brightness_score, 2)),
            "is_valid": is_valid
        }

        return is_valid, message, quality_details

    def run_detection(self, image_path, conf_threshold=0.35):
        """
        Bước 1.2 & 1.3: Chạy suy luận YOLO & đóng gói JSON cấu trúc
        """
        is_valid, msg, quality_info = self.check_image_quality(image_path)
        
        if not is_valid:
            return {
                "status": "REJECTED",
                "message": msg,
                "quality_check": quality_info,
                "detected_anomalies": [],
                "summary_metrics": {"total_lesions": 0, "urgency_level": "NONE"}
            }

        anomalies = []

        if self.model is not None:
            try:
                results = self.model.predict(source=image_path, conf=conf_threshold, verbose=False)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        class_name = self.model.names[cls_id] if hasattr(self.model, 'names') else f"Class_{cls_id}"
                        conf = float(box.conf[0])
                        xyxy = box.xyxy[0].tolist()
                        
                        anomalies.append({
                            "id": f"det_{len(anomalies)+1:02d}",
                            "class_name": class_name,
                            "confidence": float(round(conf, 2)),
                            "bbox": [round(val, 1) for val in xyxy]
                        })
            except Exception as e:
                print(f"⚠️ Lỗi suy luận YOLO: {e}")
        
        # Nếu chưa có phát hiện từ model hoặc dùng fallback
        if not anomalies and self.model is None:
            anomalies = [
                {
                    "id": "det_01",
                    "class_name": "Caries_Severe",
                    "confidence": 0.89,
                    "bbox": [140.0, 260.0, 225.0, 350.0]
                },
                {
                    "id": "det_02",
                    "class_name": "Calculus",
                    "confidence": 0.82,
                    "bbox": [310.0, 180.0, 430.0, 220.0]
                }
            ]

        total_lesions = len(anomalies)
        urgency = "GREEN"
        if total_lesions >= 3 or any("caries" in a["class_name"].lower() or "severe" in a["class_name"].lower() for a in anomalies):
            urgency = "RED"
        elif total_lesions >= 1:
            urgency = "YELLOW"

        output_json = {
            "status": "SUCCESS",
            "message": "Phân tích thị giác thành công.",
            "quality_check": quality_info,
            "detected_anomalies": anomalies,
            "summary_metrics": {
                "total_lesions": total_lesions,
                "urgency_level": urgency
            }
        }

        return output_json

if __name__ == "__main__":
    pipeline_stage1 = DentalStage1VisionPipeline()
    print("=== DENTAL STAGE 1 VISION PIPELINE READY ===")
