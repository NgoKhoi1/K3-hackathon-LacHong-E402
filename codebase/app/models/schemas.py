from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BoundingBox(BaseModel):
    """Normalized coordinates (0-1) relative to image width/height."""

    x_min: float = Field(..., ge=0, le=1)
    y_min: float = Field(..., ge=0, le=1)
    x_max: float = Field(..., ge=0, le=1)
    y_max: float = Field(..., ge=0, le=1)


class Finding(BaseModel):
    # Nhãn lớp thật (vd "Caries", "Calculus"...) đến từ classifier/detector —
    # KHÔNG ràng buộc bằng enum ở đây, vì source-of-truth là CLASSIFIER_CLASSES
    # trong vuong/1_dental_preprocess.py; ràng buộc cứng ở schema dễ lệch khi
    # model đổi lớp mà quên sửa API. Frontend tự map nhãn -> tiếng Việt để hiển thị.
    condition: str
    confidence: float = Field(..., ge=0, le=1)
    # Rỗng với các lớp chỉ có classifier toàn ảnh, không có bbox (Calculus,
    # Hypodontia). Có thể nhiều box nếu 1 điều kiện xuất hiện ở nhiều vùng
    # trong ảnh (vd 2 điểm sâu răng khác nhau).
    bboxes: list[BoundingBox] = Field(default_factory=list)


class DiagnosisResult(BaseModel):
    findings: list[Finding]
    model_version: str


class ConditionAssessment(BaseModel):
    """Đánh giá nguy cơ rule-based cho từng finding (từ TriageEngine), không
    phải do LLM tự suy diễn — xem vuong/5_chatbot_dental_agent.py."""

    condition: str
    severity: Urgency
    note: str


class Advice(BaseModel):
    # Đoạn văn LLM tổng hợp: nhận định chính + khả năng liên quan + mức độ
    # nguy cơ + khuyến nghị — KHÔNG tách rời thành list khuyến nghị vì LLM
    # sinh nó như một khối văn xuôi liền mạch (xem finalize() trong agent gốc).
    narrative: str
    urgency: Urgency
    per_condition: list[ConditionAssessment]
    disclaimer: str
    model_version: str


class DiagnoseRequest(BaseModel):
    image_base64: str = Field(..., description="Ảnh dạng base64, không kèm data URI prefix")
    image_format: str = Field(default="jpeg", description="jpeg | png")


class DiagnoseResponse(BaseModel):
    request_id: str
    diagnosis: DiagnosisResult
    advice: Advice


class StartSessionRequest(BaseModel):
    image_base64: str = Field(..., description="Ảnh dạng base64, không kèm data URI prefix")
    image_format: str = Field(default="jpeg", description="jpeg | png")
    initial_text: str = Field(default="", description="Mô tả triệu chứng ban đầu, có thể để trống")


class SessionMessageRequest(BaseModel):
    text: str


class SessionTurnResponse(BaseModel):
    session_id: str
    # Chỉ có giá trị ở response của POST /sessions (lần đầu) — các lượt
    # /sessions/{id}/messages sau đó không chạy lại vision nên không có.
    diagnosis: DiagnosisResult | None = None
    status: Literal["asking", "done"]
    question: str | None = None
    # Chỉ có giá trị đúng một lần — ở lượt đầu tiên đạt status="done" (khi
    # TriageEngine vừa chốt kết quả). Các lượt chat tự do sau đó không gửi lại.
    advice: Advice | None = None
    # Câu trả lời hội thoại tự do — có giá trị ở các lượt chat SAU KHI advice
    # đã được chốt (người dùng hỏi thêm để xin lời khuyên, không phải câu hỏi
    # sàng lọc triệu chứng nữa).
    reply: str | None = None
