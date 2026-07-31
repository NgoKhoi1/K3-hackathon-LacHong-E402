from __future__ import annotations

import io
import random
from abc import ABC, abstractmethod

from app.models.schemas import BoundingBox, DentalCondition, DiagnosisResult, Finding

# TODO: thay bằng tên class thật mà model .pt được train (xem model.names sau
# khi load, hoặc data.yaml lúc train) — sai mapping ở đây là lỗi domain-nghiêm
# trọng (④ trong taxonomy: model nói đúng, app hiển thị sai bệnh).
YOLO_CLASS_NAME_MAP: dict[str, DentalCondition] = {
    "caries": DentalCondition.CAVITY,
    "gingivitis": DentalCondition.GINGIVITIS,
    "calculus": DentalCondition.TARTAR,
    "erosion": DentalCondition.ENAMEL_EROSION,
    "impacted_tooth": DentalCondition.IMPACTED_TOOTH,
    "discoloration": DentalCondition.DISCOLORATION,
    "healthy": DentalCondition.HEALTHY,
}


class YoloDiagnosisService(ABC):
    """Contract cho model YOLO chẩn đoán tình trạng răng miệng từ ảnh.

    Model thật (train sẵn, phát triển ngoài repo này) sẽ implement lại
    interface này và được wire vào get_yolo_service() trong dependencies.py —
    route /diagnose không cần đổi gì khi tích hợp.
    """

    @abstractmethod
    async def detect(self, image_bytes: bytes) -> DiagnosisResult: ...


class MockYoloDiagnosisService(YoloDiagnosisService):
    """Trả kết quả giả lập có cấu trúc giống output YOLO thật, dùng để phát
    triển và test luồng chính trước khi model thật sẵn sàng."""

    _MOCK_POOL = [
        (DentalCondition.CAVITY, (0.32, 0.41, 0.48, 0.58)),
        (DentalCondition.GINGIVITIS, (0.10, 0.62, 0.35, 0.80)),
        (DentalCondition.TARTAR, (0.55, 0.20, 0.72, 0.38)),
        (DentalCondition.ENAMEL_EROSION, (0.60, 0.55, 0.78, 0.70)),
        (DentalCondition.DISCOLORATION, (0.15, 0.15, 0.30, 0.30)),
    ]

    async def detect(self, image_bytes: bytes) -> DiagnosisResult:
        del image_bytes  # mock: không xử lý ảnh thật
        sample_size = random.randint(1, 3)
        picks = random.sample(self._MOCK_POOL, k=sample_size)
        findings = [
            Finding(
                condition=condition,
                confidence=round(random.uniform(0.62, 0.95), 2),
                bbox=BoundingBox(x_min=x1, y_min=y1, x_max=x2, y_max=y2),
            )
            for condition, (x1, y1, x2, y2) in picks
        ]
        return DiagnosisResult(findings=findings, model_version="mock-yolo-0.0")


class RealYoloDiagnosisService(YoloDiagnosisService):
    """Chạy model YOLO thật (file .pt) qua ultralytics.

    Cần `pip install -r requirements-yolo.txt` (torch + ultralytics khá nặng,
    tách riêng khỏi requirements.txt để dev luồng API không cần cài).
    """

    def __init__(self, model_path: str, confidence_threshold: float = 0.5) -> None:
        self._model_path = model_path
        self._confidence_threshold = confidence_threshold
        self._model = None  # lazy-load, tránh cost lúc import module

    def _load_model(self):
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise RuntimeError(
                    "Thiếu ultralytics. Cài: pip install -r requirements-yolo.txt"
                ) from exc
            self._model = YOLO(self._model_path)
        return self._model

    async def detect(self, image_bytes: bytes) -> DiagnosisResult:
        from PIL import Image

        model = self._load_model()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # ultralytics chạy sync/CPU-bound; nếu route bị nghẽn khi nhiều request
        # đồng thời, chuyển sang asyncio.to_thread(model.predict, ...).
        results = model.predict(image, conf=self._confidence_threshold, verbose=False)
        result = results[0]

        findings: list[Finding] = []
        for box in result.boxes:
            class_name = result.names[int(box.cls[0])]
            condition = YOLO_CLASS_NAME_MAP.get(class_name)
            if condition is None:
                raise RuntimeError(
                    f"Model trả class '{class_name}' chưa có trong YOLO_CLASS_NAME_MAP — "
                    "cập nhật mapping thay vì bỏ qua âm thầm."
                )
            x_min, y_min, x_max, y_max = box.xyxyn[0].tolist()
            findings.append(
                Finding(
                    condition=condition,
                    confidence=round(float(box.conf[0]), 4),
                    bbox=BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max),
                )
            )

        return DiagnosisResult(findings=findings, model_version=self._model_path)
