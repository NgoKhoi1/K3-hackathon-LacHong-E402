from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod

from app.models.schemas import Advice, ConditionAssessment, DiagnosisResult, Urgency


class LLMAdvisorService(ABC):
    """Contract cho bước đánh giá nguy cơ + sinh lời khuyên từ kết quả nhận diện."""

    @abstractmethod
    async def generate_advice(self, diagnosis: DiagnosisResult) -> Advice:
        """Luồng 1-lượt: đánh giá nguy cơ ngay, không hỏi thêm triệu chứng."""
        ...

    @abstractmethod
    async def start_conversation(
        self, diagnosis: DiagnosisResult, initial_text: str
    ) -> tuple[str, str | None, Advice | None]:
        """Bắt đầu phiên hỏi-đáp. Trả (session_id, question, advice) — đúng
        một trong hai của (question, advice) khác None."""
        ...

    @abstractmethod
    async def continue_conversation(self, session_id: str, answer_text: str) -> tuple[str | None, Advice | None]:
        """Trả lời câu hỏi hiện tại của phiên. Trả (question, advice) — đúng
        một trong hai khác None. Raise KeyError nếu session_id không tồn tại."""
        ...


class RealAdvisorService(LLMAdvisorService):
    """Đánh giá nguy cơ bằng TriageEngine (rule-based, deterministic) rồi dùng
    OpenAI (qua DentalScreeningAgent) để hỏi thêm triệu chứng và diễn đạt kết
    quả cuối thành văn bản tự nhiên — LLM KHÔNG được tự quyết định mức độ nguy
    cơ, chỉ hỏi/diễn đạt (xem docstring gốc trong vuong/5_chatbot_dental_agent.py).

    Dùng CHUNG một DentalScreeningAgent cho cả vòng đời service (không tạo mới
    mỗi lần gọi), vì agent.sessions là dict lưu trạng thái hội thoại phải sống
    xuyên suốt nhiều request HTTP (giống CLI gốc dùng agent.sessions["cli-session"]
    qua nhiều lượt input()). Session chỉ lưu in-memory — mất khi backend restart,
    chấp nhận được ở quy mô demo/hackathon.

    Không gọi thẳng agent.start_session()/submit_answer(): (1) start_session
    tự chạy lại vision qua _detect.run_full_pipeline(), hàm này tự load
    detector/classifier từ vuong/artifacts/inference_config.json — file đó
    chứa path tuyệt đối của máy dev gốc, không khớp máy này; (2) cả hai hàm
    trả về một chuỗi text duy nhất (ẩn việc có gọi finalize() bên trong hay
    không) — muốn lấy thêm dữ liệu có cấu trúc (urgency, per_condition) thì
    phải gọi finalize() lần 2, tốn gấp đôi lời gọi OpenAI thật. Thay vào đó
    _advance_session() dưới đây chỉ điều phối lại phần rất ngắn đó, còn mọi
    hàm lõi thật (_build_question_queue, _extract_symptoms, next_question,
    finalize, TriageEngine.assess) đều được tái dùng nguyên bản.
    """

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise RuntimeError("Thiếu DENTAL_OPENAI_API_KEY — cần để chạy RealAdvisorService.")
        from app.core.vuong_bridge import load_vuong_modules

        modules = load_vuong_modules()
        self._chatbot = modules.chatbot
        self._detect = modules.detect
        self._model = model
        self._agent = modules.chatbot.DentalScreeningAgent(
            detector=None, classifier=None, api_key=api_key, model=model
        )

    def _reconstruct_vision_findings(self, diagnosis: DiagnosisResult):
        conditions = {
            f.condition: self._detect.ConditionFinding(label=f.condition, present=True, confidence=f.confidence)
            for f in diagnosis.findings
        }
        return self._detect.VisionFindings(detections=[], classification_scores=[], conditions=conditions)

    def _finalize_to_advice(self, session) -> Advice:
        """Gọi self._agent.finalize() ĐÚNG MỘT LẦN — nơi duy nhất được gọi
        finalize(), để tránh gọi OpenAI 2 lần cho cùng một kết quả."""
        assessment = self._chatbot.TriageEngine.assess(session.findings, session.symptoms)

        human_templates = getattr(self._detect, "_HUMAN_TEMPLATES", {})
        per_condition = []
        for label, info in assessment.per_condition.items():
            rationale = "; ".join(info["rationale"]) if info["rationale"] else human_templates.get(label, label)
            rank = info["risk"].rank()
            per_condition.append(
                ConditionAssessment(condition=label, severity=list(Urgency)[rank], note=rationale)
            )

        full_text = self._agent.finalize(session.session_id)

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

    def _advance_session(self, session, answer_text: str | None) -> tuple[str | None, Advice | None]:
        if answer_text is not None:
            if session.question_queue:
                _, question = session.question_queue.pop(0)
                session.asked_log.append((question, answer_text))
            session.raw_notes.append(answer_text)
            self._agent._extract_symptoms(session, answer_text)

        question = self._agent.next_question(session.session_id)
        if question:
            return question, None
        return None, self._finalize_to_advice(session)

    # -- Luồng 1-lượt (giữ để tương thích /diagnose) --

    def _run_sync(self, diagnosis: DiagnosisResult) -> Advice:
        vision_findings = self._reconstruct_vision_findings(diagnosis)
        session_id = str(uuid.uuid4())
        session = self._chatbot.SessionState(session_id=session_id, findings=vision_findings, symptoms={})
        self._agent.sessions[session_id] = session
        return self._finalize_to_advice(session)

    async def generate_advice(self, diagnosis: DiagnosisResult) -> Advice:
        return await asyncio.to_thread(self._run_sync, diagnosis)

    # -- Luồng nhiều lượt (hỏi thêm triệu chứng) --

    def _start_conversation_sync(
        self, diagnosis: DiagnosisResult, initial_text: str
    ) -> tuple[str, str | None, Advice | None]:
        vision_findings = self._reconstruct_vision_findings(diagnosis)
        session_id = str(uuid.uuid4())
        session = self._chatbot.SessionState(session_id=session_id, findings=vision_findings)
        session.question_queue = self._agent._build_question_queue(vision_findings)
        self._agent.sessions[session_id] = session

        if initial_text.strip():
            session.raw_notes.append(initial_text)
            self._agent._extract_symptoms(session, initial_text)

        question, advice = self._advance_session(session, answer_text=None)
        return session_id, question, advice

    async def start_conversation(
        self, diagnosis: DiagnosisResult, initial_text: str
    ) -> tuple[str, str | None, Advice | None]:
        return await asyncio.to_thread(self._start_conversation_sync, diagnosis, initial_text)

    def _continue_conversation_sync(self, session_id: str, answer_text: str) -> tuple[str | None, Advice | None]:
        session = self._agent.sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return self._advance_session(session, answer_text=answer_text)

    async def continue_conversation(self, session_id: str, answer_text: str) -> tuple[str | None, Advice | None]:
        return await asyncio.to_thread(self._continue_conversation_sync, session_id, answer_text)
