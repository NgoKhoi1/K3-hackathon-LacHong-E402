from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.schemas import Advice, DentalCondition, DiagnosisResult, Urgency

_CONDITION_ADVICE: dict[DentalCondition, tuple[str, Urgency]] = {
    DentalCondition.CAVITY: ("Có dấu hiệu sâu răng, nên trám sớm để tránh lan tủy.", Urgency.MEDIUM),
    DentalCondition.GINGIVITIS: ("Nướu có dấu hiệu viêm, nên cạo vôi và vệ sinh kỹ hơn.", Urgency.LOW),
    DentalCondition.TARTAR: ("Có mảng bám/cao răng, nên lấy cao răng định kỳ.", Urgency.LOW),
    DentalCondition.ENAMEL_EROSION: ("Men răng có dấu hiệu mòn, hạn chế đồ ăn/uống có tính axit.", Urgency.MEDIUM),
    DentalCondition.IMPACTED_TOOTH: ("Nghi ngờ răng mọc lệch/ngầm, cần chụp X-quang để xác nhận.", Urgency.HIGH),
    DentalCondition.DISCOLORATION: ("Răng có đổi màu, phần lớn là thẩm mỹ, không khẩn cấp.", Urgency.LOW),
    DentalCondition.HEALTHY: ("Không phát hiện bất thường rõ rệt.", Urgency.LOW),
}

_URGENCY_ORDER = {Urgency.LOW: 0, Urgency.MEDIUM: 1, Urgency.HIGH: 2}

_DISCLAIMER = (
    "Đây là gợi ý tham khảo từ AI, không thay thế chẩn đoán của nha sĩ. "
    "Vui lòng đến phòng khám để được thăm khám trực tiếp."
)


class LLMAdvisorService(ABC):
    """Contract cho LLM sinh lời khuyên từ kết quả chẩn đoán YOLO.

    Model thật (đã phát triển ngoài repo này) sẽ implement lại interface này
    và được wire vào get_llm_service() trong dependencies.py.
    """

    @abstractmethod
    async def generate_advice(self, diagnosis: DiagnosisResult) -> Advice: ...


class MockLLMAdvisorService(LLMAdvisorService):
    """Sinh lời khuyên rule-based từ danh sách finding, dùng để phát triển
    và test luồng chính trước khi LLM thật sẵn sàng tích hợp."""

    async def generate_advice(self, diagnosis: DiagnosisResult) -> Advice:
        if not diagnosis.findings:
            return Advice(
                summary="Không phát hiện bất thường rõ rệt trong ảnh.",
                recommendations=["Duy trì vệ sinh răng miệng và khám định kỳ 6 tháng/lần."],
                urgency=Urgency.LOW,
                disclaimer=_DISCLAIMER,
                model_version="mock-llm-0.0",
            )

        lines: list[str] = []
        recommendations: list[str] = []
        worst_urgency = Urgency.LOW
        for finding in diagnosis.findings:
            text, urgency = _CONDITION_ADVICE[finding.condition]
            lines.append(f"{finding.condition.value} ({finding.confidence:.0%}): {text}")
            recommendations.append(text)
            if _URGENCY_ORDER[urgency] > _URGENCY_ORDER[worst_urgency]:
                worst_urgency = urgency

        summary = "Phát hiện " + ", ".join(f.condition.value for f in diagnosis.findings) + "."
        return Advice(
            summary=summary,
            recommendations=recommendations,
            urgency=worst_urgency,
            disclaimer=_DISCLAIMER,
            model_version="mock-llm-0.0",
        )
