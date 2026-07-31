"use client";

import { useRef, useState } from "react";
import { ApiError, diagnose, fileToBase64 } from "@/lib/api";
import {
  OVERVIEW_LABEL_VI,
  SEVERITY_LABEL_VI,
  SEVERITY_TAG_CLASS,
  labelForCondition,
  type DiagnoseResponse,
} from "@/lib/types";

type Step = "upload" | "analyzing" | "results";

function LogoIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" fill="none" stroke="var(--color-accent)" strokeWidth="2" />
      <rect x="7" y="9" width="4" height="14" fill="var(--color-accent)" />
      <rect x="14" y="3" width="4" height="20" fill="var(--color-accent)" />
      <rect x="21" y="9" width="4" height="14" fill="var(--color-accent)" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  );
}

function formatFromMime(mime: string): string {
  const format = mime.split("/")[1]?.toLowerCase();
  return format === "jpg" ? "jpeg" : (format ?? "jpeg");
}

export default function Home() {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiagnoseResponse | null>(null);

  function pickFile(f: File) {
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
    setError(null);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) pickFile(f);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  }

  async function handleAnalyze() {
    if (!file) return;
    setStep("analyzing");
    setError(null);
    try {
      const base64 = await fileToBase64(file);
      const response = await diagnose(base64, formatFromMime(file.type));
      setResult(response);
      setStep("results");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không gọi được API — kiểm tra backend đã chạy chưa.");
      setStep("upload");
    }
  }

  function reset() {
    setStep("upload");
    setFile(null);
    setPreviewUrl(null);
    setResult(null);
    setError(null);
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)", color: "var(--color-text)" }}>
      <nav className="nav">
        <span className="nav-brand" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <LogoIcon />
          Pocket&nbsp;Dentist
        </span>
        <span className="text-muted" style={{ fontSize: 12, marginLeft: "auto" }}>
          Kiểm tra bằng AI — không phải chẩn đoán y khoa
        </span>
      </nav>

      <div style={{ maxWidth: 720, margin: "0 auto", padding: "var(--space-8) var(--space-4)" }}>
        {step === "upload" && (
          <>
            <h1 style={{ marginBottom: "var(--space-2)" }}>Cùng xem qua nụ cười của bạn</h1>
            <p className="text-muted" style={{ maxWidth: "52ch" }}>
              Chụp hoặc tải lên một tấm ảnh rõ nét, đủ sáng về hàm răng của bạn — chụp thẳng mặt là tốt nhất.
            </p>

            <div className="card elev-sm" style={{ padding: "var(--space-6)", gap: "var(--space-4)", marginTop: "var(--space-6)" }}>
              <div
                className="dropzone"
                style={{ width: "100%", height: 320, overflow: "hidden" }}
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
              >
                {previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={previewUrl} alt="Ảnh răng đã chọn" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                ) : (
                  <span className="text-muted" style={{ fontSize: 14, padding: "var(--space-4)" }}>
                    Kéo thả ảnh răng của bạn vào đây, hoặc bấm để chọn file
                  </span>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png"
                onChange={handleInputChange}
                style={{ display: "none" }}
              />

              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", flexWrap: "wrap" }}>
                <button type="button" className="btn btn-primary" disabled={!file} onClick={handleAnalyze}>
                  Phân tích ảnh của tôi
                  <ArrowIcon />
                </button>
                <span className="text-muted" style={{ fontSize: 12 }}>
                  Khoảng 10 giây · Định dạng JPG hoặc PNG
                </span>
              </div>
            </div>

            {error && (
              <div className="tag tag-accent" style={{ display: "block", marginTop: "var(--space-4)", padding: "var(--space-3)", fontSize: 13 }}>
                {error}
              </div>
            )}
          </>
        )}

        {step === "analyzing" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-4)", padding: "var(--space-8) 0", textAlign: "center" }}>
            <h2 style={{ margin: 0 }}>Đợi một chút nhé…</h2>
            <p className="text-muted" style={{ maxWidth: "44ch", margin: 0 }}>
              Chúng tôi đang kiểm tra men răng, viền nướu và độ thẳng hàng trong ảnh của bạn.
            </p>
            <div className="pd-loadbar" style={{ width: "100%", maxWidth: 320, marginTop: "var(--space-2)" }}>
              <span />
            </div>
          </div>
        )}

        {step === "results" && result && (
          <>
            <h1 style={{ marginBottom: "var(--space-2)" }}>Ảnh đẹp đấy — đây là những gì chúng tôi tìm thấy</h1>
            <p className="text-muted" style={{ maxWidth: "56ch" }}>
              {result.diagnosis.findings.length === 0
                ? "Không phát hiện bất thường rõ rệt trong 6 nhóm đã khảo sát."
                : `Phát hiện ${result.diagnosis.findings.length} điểm cần lưu ý.`}
            </p>
            <span className={`tag ${SEVERITY_TAG_CLASS[result.advice.urgency]}`} style={{ marginTop: "var(--space-2)" }}>
              Tổng quan: {OVERVIEW_LABEL_VI[result.advice.urgency]}
            </span>

            <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: "var(--space-6)", marginTop: "var(--space-6)", alignItems: "start" }}>
              <figure>
                <div style={{ width: "100%", height: 220, overflow: "hidden" }}>
                  {previewUrl && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={previewUrl} alt="Ảnh răng đã phân tích" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  )}
                </div>
                <figcaption>model: {result.diagnosis.model_version}</figcaption>
              </figure>

              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                <h4 style={{ margin: 0 }}>Những điều chúng tôi nhận thấy</h4>

                {result.diagnosis.findings.length === 0 ? (
                  <p className="text-muted" style={{ fontSize: 14, margin: 0 }}>Không phát hiện bất thường trong ảnh.</p>
                ) : (
                  result.diagnosis.findings.map((f, i) => {
                    const assessment = result.advice.per_condition.find((pc) => pc.condition === f.condition);
                    const severity = assessment?.severity ?? "low";
                    return (
                      <div className="card" key={i}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-2)" }}>
                          <div className="card-title">{labelForCondition(f.condition)}</div>
                          <span className={`tag ${SEVERITY_TAG_CLASS[severity]}`}>{SEVERITY_LABEL_VI[severity]}</span>
                        </div>
                        <p className="card-body">{assessment?.note ?? `Độ tin cậy ${(f.confidence * 100).toFixed(0)}%.`}</p>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            <hr className="hr" style={{ marginTop: "var(--space-8)" }} />
            <h4 style={{ marginBottom: "var(--space-3)" }}>Nhận định từ AI</h4>
            <p style={{ fontSize: 14, whiteSpace: "pre-wrap", margin: "0 0 var(--space-6)" }}>{result.advice.narrative}</p>

            <hr className="hr" />
            <p className="text-muted" style={{ fontSize: 12, maxWidth: "64ch", margin: "var(--space-3) 0 var(--space-6)" }}>
              <em>{result.advice.disclaimer}</em>
            </p>

            <button type="button" className="btn btn-secondary" onClick={reset}>
              Quét ảnh khác
            </button>
          </>
        )}
      </div>
    </div>
  );
}
