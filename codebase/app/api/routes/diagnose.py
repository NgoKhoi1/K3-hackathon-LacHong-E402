import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_llm_service, get_yolo_service
from app.core.image_utils import decode_and_validate_image
from app.models.schemas import DiagnoseRequest, DiagnoseResponse
from app.services.llm_service import LLMAdvisorService
from app.services.yolo_service import YoloDiagnosisService

router = APIRouter(tags=["diagnose"])


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    payload: DiagnoseRequest,
    yolo_service: YoloDiagnosisService = Depends(get_yolo_service),
    llm_service: LLMAdvisorService = Depends(get_llm_service),
) -> DiagnoseResponse:
    image_bytes = decode_and_validate_image(payload.image_base64, payload.image_format)

    diagnosis = await yolo_service.detect(image_bytes)
    advice = await llm_service.generate_advice(diagnosis)

    return DiagnoseResponse(
        request_id=str(uuid.uuid4()),
        diagnosis=diagnosis,
        advice=advice,
    )
