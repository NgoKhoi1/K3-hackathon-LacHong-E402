export type DentalCondition =
  | "cavity"
  | "gingivitis"
  | "tartar"
  | "enamel_erosion"
  | "impacted_tooth"
  | "discoloration"
  | "healthy";

export type Urgency = "low" | "medium" | "high";

export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface Finding {
  condition: DentalCondition;
  confidence: number;
  bbox: BoundingBox;
}

export interface DiagnosisResult {
  findings: Finding[];
  model_version: string;
}

export interface Advice {
  summary: string;
  recommendations: string[];
  urgency: Urgency;
  disclaimer: string;
  model_version: string;
}

export interface DiagnoseResponse {
  request_id: string;
  diagnosis: DiagnosisResult;
  advice: Advice;
}

export const CONDITION_LABEL_VI: Record<DentalCondition, string> = {
  cavity: "Sâu răng",
  gingivitis: "Viêm nướu",
  tartar: "Cao răng",
  enamel_erosion: "Mòn men răng",
  impacted_tooth: "Răng mọc lệch/ngầm",
  discoloration: "Đổi màu răng",
  healthy: "Không phát hiện bất thường",
};

export const URGENCY_LABEL_VI: Record<Urgency, string> = {
  low: "Không khẩn cấp",
  medium: "Nên khám sớm",
  high: "Cần khám ngay",
};
