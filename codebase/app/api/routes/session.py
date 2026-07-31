from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_llm_service, get_yolo_service
from app.core.image_utils import decode_and_validate_image
from app.models.schemas import SessionMessageRequest, SessionTurnResponse, StartSessionRequest
from app.services.llm_service import LLMAdvisorService
from app.services.yolo_service import YoloDiagnosisService

router = APIRouter(tags=["session"])


@router.post("/sessions", response_model=SessionTurnResponse)
async def start_session(
    payload: StartSessionRequest,
    yolo_service: YoloDiagnosisService = Depends(get_yolo_service),
    llm_service: LLMAdvisorService = Depends(get_llm_service),
) -> SessionTurnResponse:
    image_bytes = decode_and_validate_image(payload.image_base64, payload.image_format)

    try:
        diagnosis = await yolo_service.detect(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_id, question, advice = await llm_service.start_conversation(diagnosis, payload.initial_text)

    return SessionTurnResponse(
        session_id=session_id,
        diagnosis=diagnosis,
        status="asking" if question else "done",
        question=question,
        advice=advice,
    )


@router.post("/sessions/{session_id}/messages", response_model=SessionTurnResponse)
async def send_session_message(
    session_id: str,
    payload: SessionMessageRequest,
    llm_service: LLMAdvisorService = Depends(get_llm_service),
) -> SessionTurnResponse:
    try:
        question, advice = await llm_service.continue_conversation(session_id, payload.text)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên hoặc phiên đã hết hạn") from exc

    return SessionTurnResponse(
        session_id=session_id,
        status="asking" if question else "done",
        question=question,
        advice=advice,
    )
