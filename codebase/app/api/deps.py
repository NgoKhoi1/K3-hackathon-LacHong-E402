from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.services.llm_service import LLMAdvisorService, RealAdvisorService
from app.services.yolo_service import RealVisionService, YoloDiagnosisService

# Không đọc vuong/artifacts/inference_config.json — file đó chứa đường dẫn
# tuyệt đối của máy dev gốc (C:\lab-hackathon\...), không khớp vị trí repo ở
# đây. Tự suy đường dẫn weight từ vuong_dir + cấu trúc artifacts/ đã biết.
def _detector_weights_path() -> str:
    return str(Path(settings.vuong_dir) / "artifacts" / "detector_runs" / "weights" / "best.pt")


def _classifier_checkpoint_path() -> str:
    return str(Path(settings.vuong_dir) / "artifacts" / "classifier_best.pt")


@lru_cache
def get_yolo_service() -> YoloDiagnosisService:
    return RealVisionService(
        detector_weights=_detector_weights_path(),
        classifier_checkpoint=_classifier_checkpoint_path(),
        detector_conf_threshold=settings.detector_conf_threshold,
        classifier_conf_threshold=settings.classifier_conf_threshold,
        device=settings.inference_device,
    )


@lru_cache
def get_llm_service() -> LLMAdvisorService:
    if not settings.openai_api_key:
        raise RuntimeError("DENTAL_OPENAI_API_KEY chưa được set")
    return RealAdvisorService(api_key=settings.openai_api_key, model=settings.openai_model)
