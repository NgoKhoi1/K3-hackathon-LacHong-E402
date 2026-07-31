export type Urgency = "low" | "medium" | "high";

export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface Finding {
  // Nhãn thật từ classifier (vd "Caries") — không ràng buộc union type ở
  // frontend, vì API cũng không ràng buộc enum (xem app/models/schemas.py).
  condition: string;
  confidence: number;
  // Rỗng với các lớp chỉ có classifier toàn ảnh, không có bbox (Calculus, Hypodontia).
  bboxes: BoundingBox[];
}

export interface DiagnosisResult {
  findings: Finding[];
  model_version: string;
}

export interface ConditionAssessment {
  condition: string;
  severity: Urgency;
  note: string;
}

export interface Advice {
  narrative: string;
  urgency: Urgency;
  per_condition: ConditionAssessment[];
  disclaimer: string;
  model_version: string;
}

export interface DiagnoseResponse {
  request_id: string;
  diagnosis: DiagnosisResult;
  advice: Advice;
}

export interface SessionTurnResponse {
  session_id: string;
  diagnosis: DiagnosisResult | null;
  status: "asking" | "done";
  question: string | null;
  advice: Advice | null;
}

export type ChatTurn = { role: "agent" | "user"; text: string };

// Nhãn hiển thị tiếng Việt — thuần trình bày. Nếu model sau này có thêm lớp
// mới chưa kịp thêm vào đây, fallback về nguyên văn nhãn tiếng Anh (xem
// labelForCondition) thay vì hiện sai tên bệnh.
export const CONDITION_LABEL_VI: Record<string, string> = {
  Caries: "Sâu răng",
  Calculus: "Cao răng",
  Gingivitis: "Viêm nướu",
  "Tooth Discoloration": "Đổi màu răng",
  Ulcers: "Loét miệng",
  Hypodontia: "Thiếu răng",
};

export function labelForCondition(condition: string): string {
  return CONDITION_LABEL_VI[condition] ?? condition;
}

export const SEVERITY_LABEL_VI: Record<Urgency, string> = {
  low: "Thấp",
  medium: "Trung bình",
  high: "Cao",
};

export const SEVERITY_TAG_CLASS: Record<Urgency, string> = {
  low: "tag-neutral",
  medium: "tag-outline",
  high: "tag-accent",
};

// Màu viền bbox theo mức độ — dùng token màu đã có trong globals.css.
export const SEVERITY_STROKE_COLOR: Record<Urgency, string> = {
  low: "var(--color-neutral-800)",
  medium: "var(--color-accent-2)",
  high: "var(--color-accent)",
};

export const OVERVIEW_LABEL_VI: Record<Urgency, string> = {
  low: "Tốt, có vài lưu ý nhỏ",
  medium: "Cần lưu ý thêm một chút",
  high: "Nên đi khám sớm",
};
