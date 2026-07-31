from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod

from app.models.schemas import Advice, ConditionAssessment, DiagnosisResult, Urgency


class LLMAdvisorService(ABC):
    """Contract cho bước đánh giá nguy cơ + sinh lời khuyên từ kết quả nhận diện."""

    @abstractmethod
    async def generate_advice(self, diagnosis: DiagnosisResult) -> Advice: ...


class RealAdvisorService(LLMAdvisorService):
    """Đánh giá nguy cơ bằng TriageEngine (rule-based, deterministic) rồi dùng
    OpenAI (qua DentalScreeningAgent.finalize) để diễn đạt lại thành văn bản
    tự nhiên — LLM KHÔNG được tự quyết định mức độ nguy cơ, chỉ diễn đạt kết
    quả đã tính sẵn (xem docstring gốc trong vuong/5_chatbot_dental_agent.py).

    Ở luồng 1-lượt này KHÔNG hỏi thêm triệu chứng (symptoms={}) — đánh giá
    nguy cơ vì vậy bảo thủ/kém chi tiết hơn so với agent hội thoại đầy đủ.
    """

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise RuntimeError("Thiếu DENTAL_OPENAI_API_KEY — cần để chạy RealAdvisorService.")
        from app.core.vuong_bridge import load_vuong_modules

        modules = load_vuong_modules()
        self._chatbot = modules.chatbot
        self._detect = modules.detect
        self._api_key = api_key
        self._model = model

    def _reconstruct_vision_findings(self, diagnosis: DiagnosisResult):
        conditions = {
            f.condition: self._detect.ConditionFinding(label=f.condition, present=True, confidence=f.confidence)
            for f in diagnosis.findings
        }
        return self._detect.VisionFindings(detections=[], classification_scores=[], conditions=conditions)

    def _run_sync(self, diagnosis: DiagnosisResult) -> Advice:
        vision_findings = self._reconstruct_vision_findings(diagnosis)
        assessment = self._chatbot.TriageEngine.assess(vision_findings, symptoms={})

        human_templates = getattr(self._detect, "_HUMAN_TEMPLATES", {})
        per_condition = []
        for label, info in assessment.per_condition.items():
            rationale = "; ".join(info["rationale"]) if info["rationale"] else human_templates.get(label, label)
            rank = info["risk"].rank()
            per_condition.append(
                ConditionAssessment(condition=label, severity=list(Urgency)[rank], note=rationale)
            )

        agent = self._chatbot.DentalScreeningAgent(
            detector=None, classifier=None, api_key=self._api_key, model=self._model
        )
        session_id = str(uuid.uuid4())
        agent.sessions[session_id] = self._chatbot.SessionState(
            session_id=session_id, findings=vision_findings, symptoms={}
        )
        full_text = agent.finalize(session_id)

        disclaimer = self._chatbot.DISCLAIMER
        narrative = full_text
        suffix = f"\n\n{disclaimer}"
        if narrative.endswith(suffix):
            narrative = narrative[: -len(suffix)]

        overall_rank = assessment.overall.rank()
        return Advice(
            narrative=narrative,
            urgency=list(Urgency)[overall_rank],
            per_condition=per_condition,
            disclaimer=disclaimer,
            model_version=f"openai:{self._model}",
        )

    async def generate_advice(self, diagnosis: DiagnosisResult) -> Advice:
        # DentalScreeningAgent._chat gọi OpenAI SDK đồng bộ — chạy trong thread
        # riêng để không chặn event loop khi chờ mạng.
        return await asyncio.to_thread(self._run_sync, diagnosis)
