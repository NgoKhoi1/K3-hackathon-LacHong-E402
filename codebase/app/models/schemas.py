from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DentalCondition(str, Enum):
    CAVITY = "cavity"
    GINGIVITIS = "gingivitis"
    TARTAR = "tartar"
    ENAMEL_EROSION = "enamel_erosion"
    IMPACTED_TOOTH = "impacted_tooth"
    DISCOLORATION = "discoloration"
    HEALTHY = "healthy"


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
    condition: DentalCondition
    confidence: float = Field(..., ge=0, le=1)
    bbox: BoundingBox


class DiagnosisResult(BaseModel):
    findings: list[Finding]
    model_version: str


class Advice(BaseModel):
    summary: str
    recommendations: list[str]
    urgency: Urgency
    disclaimer: str
    model_version: str


class DiagnoseRequest(BaseModel):
    image_base64: str = Field(..., description="Ảnh dạng base64, không kèm data URI prefix")
    image_format: str = Field(default="jpeg", description="jpeg | png")


class DiagnoseResponse(BaseModel):
    request_id: str
    diagnosis: DiagnosisResult
    advice: Advice
