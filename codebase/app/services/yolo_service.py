from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from app.models.schemas import BoundingBox, DiagnosisResult, Finding


class YoloDiagnosisService(ABC):
    """Contract cho bước nhận diện (detector + classifier) chạy trên ảnh."""

    @abstractmethod
    async def detect(self, image_bytes: bytes) -> DiagnosisResult: ...


class RealVisionService(YoloDiagnosisService):
    """Bọc detector (YOLOv8) + classifier (EfficientNet-B1) thật từ vuong/.

    Model được load MỘT LẦN lúc khởi tạo (singleton qua app/api/deps.py), vì
    load checkpoint mỗi request sẽ rất chậm.
    """

    def __init__(
        self,
        detector_weights: str,
        classifier_checkpoint: str,
        detector_conf_threshold: float,
        classifier_conf_threshold: float,
        device: str = "cpu",
    ) -> None:
        from app.core.vuong_bridge import load_vuong_modules

        modules = load_vuong_modules()
        self._prep = modules.prep
        self._detect = modules.detect
        self._detector = modules.detect.DentalDetector(detector_weights, detector_conf_threshold)
        self._classifier = modules.detect.DentalClassifier(classifier_checkpoint, device=device)
        self._detector_conf_threshold = detector_conf_threshold
        self._classifier_conf_threshold = classifier_conf_threshold
        detector_name = Path(detector_weights).name
        classifier_name = Path(classifier_checkpoint).name
        self._model_version = f"detector={detector_name}; classifier={classifier_name}"

    def _decode_image(self, image_bytes: bytes):
        import cv2
        import numpy as np

        data = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Không đọc được ảnh — dữ liệu ảnh có thể bị hỏng.")
        return image

    def _run_sync(self, image_bytes: bytes) -> DiagnosisResult:
        image = self._decode_image(image_bytes)
        height, width = image.shape[:2]

        quality = self._prep.check_image_quality(image)
        if not quality.is_acceptable:
            raise ValueError("Ảnh không đạt chất lượng tối thiểu: " + " ".join(quality.issues))

        processed = self._prep.preprocess_for_inference(image)
        detections = self._detector.predict(processed["detector_input_bgr"])
        classification_scores = self._classifier.predict(processed["classifier_input_rgb"])
        vision_findings = self._detect.merge_findings(
            detections,
            classification_scores,
            detector_conf_th=self._detector_conf_threshold,
            classifier_conf_th=self._classifier_conf_threshold,
        )

        findings = [
            Finding(
                condition=c.label,
                confidence=round(c.confidence, 4),
                bboxes=[self._normalize_bbox(b, width, height) for b in c.bboxes],
            )
            for c in vision_findings.flagged()
        ]
        return DiagnosisResult(findings=findings, model_version=self._model_version)

    @staticmethod
    def _normalize_bbox(bbox_xyxy: tuple[float, float, float, float], width: int, height: int) -> BoundingBox:
        x1, y1, x2, y2 = bbox_xyxy
        clamp = lambda v: max(0.0, min(1.0, v))  # noqa: E731 — rounding có thể đẩy nhẹ ra ngoài [0,1]
        return BoundingBox(
            x_min=clamp(x1 / width), y_min=clamp(y1 / height), x_max=clamp(x2 / width), y_max=clamp(y2 / height)
        )

    async def detect(self, image_bytes: bytes) -> DiagnosisResult:
        # detector/classifier là các lời gọi sync, tốn CPU/GPU — chạy trong
        # thread riêng để không chặn event loop khi có nhiều request đồng thời.
        return await asyncio.to_thread(self._run_sync, image_bytes)
