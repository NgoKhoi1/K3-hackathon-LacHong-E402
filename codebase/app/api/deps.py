from functools import lru_cache

from app.core.config import settings
from app.services.llm_service import LLMAdvisorService, MockLLMAdvisorService
from app.services.yolo_service import (
    MockYoloDiagnosisService,
    RealYoloDiagnosisService,
    YoloDiagnosisService,
)


@lru_cache
def get_yolo_service() -> YoloDiagnosisService:
    if settings.use_mock_models:
        return MockYoloDiagnosisService()
    if not settings.yolo_model_path:
        raise RuntimeError("DENTAL_YOLO_MODEL_PATH chưa được set (đường dẫn file .pt)")
    return RealYoloDiagnosisService(
        model_path=settings.yolo_model_path,
        confidence_threshold=settings.yolo_confidence_threshold,
    )


@lru_cache
def get_llm_service() -> LLMAdvisorService:
    if settings.use_mock_models:
        return MockLLMAdvisorService()
    # TODO: tích hợp LLM thật ở đây (implement LLMAdvisorService).
    raise NotImplementedError("Real LLM service chưa được tích hợp")
