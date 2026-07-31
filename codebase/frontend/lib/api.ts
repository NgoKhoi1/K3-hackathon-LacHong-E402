import type { DiagnoseResponse, SessionTurnResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new ApiError(errBody?.detail ?? `Lỗi ${res.status} từ server`);
  }

  return res.json();
}

export function diagnose(imageBase64: string, imageFormat: string): Promise<DiagnoseResponse> {
  return postJson("/api/v1/diagnose", { image_base64: imageBase64, image_format: imageFormat });
}

export function startSession(
  imageBase64: string,
  imageFormat: string,
  initialText: string
): Promise<SessionTurnResponse> {
  return postJson("/api/v1/sessions", {
    image_base64: imageBase64,
    image_format: imageFormat,
    initial_text: initialText,
  });
}

export function sendSessionAnswer(sessionId: string, text: string): Promise<SessionTurnResponse> {
  return postJson(`/api/v1/sessions/${sessionId}/messages`, { text });
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      resolve(dataUrl.substring(dataUrl.indexOf(",") + 1));
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}
