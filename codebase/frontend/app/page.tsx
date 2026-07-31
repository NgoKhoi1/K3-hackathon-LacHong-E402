"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, fileToBase64, sendSessionAnswer, startSession } from "@/lib/api";
import {
  OVERVIEW_LABEL_VI,
  SEVERITY_LABEL_VI,
  SEVERITY_STROKE_COLOR,
  SEVERITY_TAG_CLASS,
  labelForCondition,
  type Advice,
  type ChatTurn,
  type DiagnosisResult,
  type Finding,
} from "@/lib/types";

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

function ToothIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3c-2.2 0-3.2 1.1-4.5 1.1C5.8 4.1 4 5.7 4 8.4c0 2.1.9 3.3 1.3 5.6.4 2.3.6 6 2.6 6 1.7 0 1.6-3.6 2.4-3.6.8 0 .7 3.6 2.4 3.6 2 0 2.2-3.7 2.6-6C15.8 11.7 16.7 10.5 16.7 8.4c0-2.7-1.8-4.3-3.5-4.3C11.9 4.1 10.9 3 12 3z"
        fill="var(--color-accent)"
      />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m3 3 18 9-18 9 4.5-9L3 3Z" />
    </svg>
  );
}

function TypingDots() {
  return (
    <span style={{ display: "inline-flex", gap: 3 }}>
      <span className="pd-dot" />
      <span className="pd-dot" style={{ animationDelay: "0.15s" }} />
      <span className="pd-dot" style={{ animationDelay: "0.3s" }} />
    </span>
  );
}

function BboxOverlay({ findings, advice }: { findings: Finding[]; advice: Advice | null }) {
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
    >
      {findings.flatMap((f, fi) => {
        const severity = advice?.per_condition.find((pc) => pc.condition === f.condition)?.severity ?? "low";
        const color = SEVERITY_STROKE_COLOR[severity];
        return f.bboxes.map((b, bi) => (
          <rect
            key={`${fi}-${bi}`}
            x={b.x_min * 100}
            y={b.y_min * 100}
            width={(b.x_max - b.x_min) * 100}
            height={(b.y_max - b.y_min) * 100}
            fill="none"
            stroke={color}
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
        ));
      })}
    </svg>
  );
}

function formatFromMime(mime: string): string {
  const format = mime.split("/")[1]?.toLowerCase();
  return format === "jpg" ? "jpeg" : (format ?? "jpeg");
}

// Hiển thị khả năng ở dạng định tính (không show số % cụ thể ra cho người
// dùng — con số thô dễ bị hiểu nhầm là "độ chính xác chẩn đoán y khoa").
function confidenceLabel(confidence: number): string {
  if (confidence >= 0.85) return "khả năng cao";
  if (confidence >= 0.65) return "khả năng khá rõ";
  return "có dấu hiệu, cần theo dõi thêm";
}

function summarizeFindings(diagnosis: DiagnosisResult, willAskMore: boolean): string {
  if (diagnosis.findings.length === 0) {
    return "Mình đã xem ảnh của bạn — không phát hiện bất thường rõ rệt trong 6 nhóm đã khảo sát (sâu răng, cao răng, viêm nướu, đổi màu răng, loét miệng, thiếu răng). Bạn có muốn hỏi thêm gì không?";
  }
  const list = diagnosis.findings.map((f) => `${labelForCondition(f.condition)} (${confidenceLabel(f.confidence)})`).join(", ");
  const tail = willAskMore
    ? " Mình sẽ hỏi thêm vài câu để đánh giá chính xác hơn nhé."
    : "";
  return `Mình đã xem ảnh của bạn, phát hiện ${diagnosis.findings.length} điểm cần lưu ý: ${list}.${tail}`;
}

// Render **đậm** trong một dòng — không cần kéo thêm thư viện markdown chỉ
// để xử lý một ký hiệu này.
function renderInline(text: string, keyPrefix: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g).filter((p) => p.length > 0);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={`${keyPrefix}-${i}`}>{part}</span>
    )
  );
}

// Agent (đặc biệt ở chat tự do) hay trả lời bằng danh sách gạch đầu dòng/đánh
// số + **đậm** — parse nhẹ thành đoạn văn/danh sách thật để dễ đọc hơn là một
// khối text thô với ký tự markdown còn nguyên.
function renderRichText(text: string) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let listItems: string[] | null = null;
  let listTag: "ul" | "ol" | null = null;

  function flushList() {
    if (listItems && listTag) {
      const items = listItems;
      const ListTag = listTag;
      blocks.push(
        <ListTag key={blocks.length} style={{ margin: "4px 0 8px", paddingLeft: 20 }}>
          {items.map((item, i) => (
            <li key={i} style={{ marginBottom: 2 }}>
              {renderInline(item, `li-${blocks.length}-${i}`)}
            </li>
          ))}
        </ListTag>
      );
    }
    listItems = null;
    listTag = null;
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }
    const bulletMatch = line.match(/^[-•]\s+(.*)/);
    const numberedMatch = line.match(/^\d+[.)]\s+(.*)/);
    if (bulletMatch) {
      if (listTag !== "ul") flushList();
      listTag = "ul";
      listItems = [...(listItems ?? []), bulletMatch[1]];
    } else if (numberedMatch) {
      if (listTag !== "ol") flushList();
      listTag = "ol";
      listItems = [...(listItems ?? []), numberedMatch[1]];
    } else {
      flushList();
      blocks.push(
        <p key={blocks.length} style={{ margin: "0 0 8px" }}>
          {renderInline(line, `p-${blocks.length}`)}
        </p>
      );
    }
  }
  flushList();
  return blocks;
}

// advice.narrative theo đúng 4 phần cố định do vuong/5_chatbot_dental_agent.py
// yêu cầu LLM tuân theo: "(1) nhận định chính (2) khả năng liên quan (3) mức
// độ nguy cơ (4) khuyến nghị hành động" — parse thành các mục có tiêu đề rõ
// ràng thay vì một đoạn văn liền, để người dùng dễ quét thông tin hơn. Nếu
// LLM lỡ không theo đúng định dạng (không parse được >= 2 mục), fallback về
// renderRichText nguyên văn — không được để mất nội dung.
function NarrativeReport({ text, disclaimer }: { text: string; disclaimer?: string }) {
  const parts = text.split(/\(([1-4])\)\s*/).filter((p) => p.length > 0);
  const sections: { label: string; body: string }[] = [];
  for (let i = 0; i + 1 < parts.length; i += 2) {
    if (!/^[1-4]$/.test(parts[i])) continue;
    const chunk = parts[i + 1].trim();
    const colonIdx = chunk.indexOf(":");
    if (colonIdx > 0 && colonIdx < 60) {
      sections.push({ label: chunk.slice(0, colonIdx).trim(), body: chunk.slice(colonIdx + 1).trim() });
    } else {
      sections.push({ label: "", body: chunk });
    }
  }

  return (
    <div>
      <div className="card-kicker" style={{ marginBottom: 6 }}>Nhận định từ AI</div>
      {sections.length >= 2 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {sections.map((s, i) => (
            <div key={i}>
              {s.label && <div style={{ fontWeight: "var(--font-heading-weight)", fontSize: 13, marginBottom: 2 }}>{s.label}</div>}
              <div style={{ fontSize: 14 }}>{renderRichText(s.body)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div>{renderRichText(text)}</div>
      )}
      {disclaimer && (
        <p className="text-muted" style={{ fontSize: 11, margin: "var(--space-3) 0 0" }}>
          <em>{disclaimer}</em>
        </p>
      )}
    </div>
  );
}

export default function Home() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [initialText, setInitialText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResult | null>(null);
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  useEffect(() => {
    chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chatTurns, isSending, isAnalyzing]);

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
    setIsAnalyzing(true);
    setError(null);
    try {
      const base64 = await fileToBase64(file);
      const response = await startSession(base64, formatFromMime(file.type), initialText);
      setSessionId(response.session_id);
      setDiagnosis(response.diagnosis);

      const willAskMore = response.status === "asking" && !!response.question;
      const turns: ChatTurn[] = [{ role: "agent", text: summarizeFindings(response.diagnosis!, willAskMore) }];
      if (willAskMore) {
        turns.push({ role: "agent", text: response.question! });
        setAdvice(null);
      } else {
        setAdvice(response.advice);
        if (response.advice) turns.push({ role: "agent", text: response.advice.narrative, kind: "narrative" });
      }
      setChatTurns(turns);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không gọi được API — kiểm tra backend đã chạy chưa.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  function reset() {
    setFile(null);
    setPreviewUrl(null);
    setInitialText("");
    setError(null);
    setIsAnalyzing(false);
    setSessionId(null);
    setDiagnosis(null);
    setAdvice(null);
    setChatTurns([]);
    setDraft("");
    setChatError(null);
  }

  async function sendAnswer() {
    const text = draft.trim();
    if (!text || !sessionId || isSending) return;
    setChatTurns((t) => [...t, { role: "user", text }]);
    setDraft("");
    setIsSending(true);
    setChatError(null);
    try {
      const response = await sendSessionAnswer(sessionId, text);
      if (response.status === "asking" && response.question) {
        setChatTurns((t) => [...t, { role: "agent", text: response.question! }]);
      } else if (response.advice) {
        setAdvice(response.advice);
        setChatTurns((t) => [...t, { role: "agent", text: response.advice!.narrative, kind: "narrative" }]);
      } else if (response.reply) {
        setChatTurns((t) => [...t, { role: "agent", text: response.reply! }]);
      }
    } catch (err) {
      setChatError(err instanceof ApiError ? err.message : "Không gửi được câu trả lời — thử lại nhé.");
    } finally {
      setIsSending(false);
    }
  }

  const chatDisabled = !sessionId || isAnalyzing;

  return (
    <div style={{ height: "100dvh", display: "flex", flexDirection: "column", background: "var(--color-bg)", color: "var(--color-text)" }}>
      <nav className="nav">
        <span className="nav-brand" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <LogoIcon />
          Smart&nbsp;Smile
        </span>
        <span className="text-muted" style={{ fontSize: 12, marginLeft: "auto" }}>
          Kiểm tra bằng AI — không phải chẩn đoán y khoa
        </span>
      </nav>

      <main className="workspace">
        <aside className="panel-photo">
          {!diagnosis && !isAnalyzing && (
            <>
              <h2 style={{ marginBottom: "var(--space-1)" }}>Cùng xem qua nụ cười của bạn</h2>
              <p className="text-muted" style={{ fontSize: 13 }}>
                Chụp hoặc tải lên một tấm ảnh rõ nét, đủ sáng về hàm răng — chụp thẳng mặt là tốt nhất.
              </p>
            </>
          )}

          <div
            className="dropzone"
            style={{ width: "100%", aspectRatio: diagnosis ? undefined : "4 / 3", overflow: "hidden", position: "relative" }}
            onClick={() => !diagnosis && fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
          >
            {previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={previewUrl}
                alt="Ảnh răng đã chọn"
                style={diagnosis ? { width: "100%", height: "auto", display: "block" } : { width: "100%", height: "100%", objectFit: "cover" }}
              />
            ) : (
              <span className="text-muted" style={{ fontSize: 14, padding: "var(--space-4)" }}>
                Kéo thả ảnh răng của bạn vào đây, hoặc bấm để chọn file
              </span>
            )}
            {diagnosis && diagnosis.findings.some((f) => f.bboxes.length > 0) && (
              <BboxOverlay findings={diagnosis.findings} advice={advice} />
            )}
            {isAnalyzing && (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: "color-mix(in srgb, var(--color-bg) 55%, transparent)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <span className="tag tag-outline" style={{ background: "var(--color-bg)" }}>
                  Đang quét ảnh…
                </span>
              </div>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png"
            onChange={handleInputChange}
            style={{ display: "none" }}
          />

          {!diagnosis && !isAnalyzing && (
            <>
              <div className="field">
                <label htmlFor="initial-text" style={{ display: "block", fontSize: 12, marginBottom: 5, color: "color-mix(in srgb, var(--color-text) 70%, transparent)" }}>
                  Mô tả triệu chứng (không bắt buộc)
                </label>
                <textarea
                  id="initial-text"
                  className="input"
                  placeholder="Ví dụ: ê buốt khi uống nước lạnh, chảy máu nướu khi đánh răng..."
                  value={initialText}
                  onChange={(e) => setInitialText(e.target.value)}
                />
              </div>

              <button type="button" className="btn btn-primary" disabled={!file} onClick={handleAnalyze} style={{ width: "100%" }}>
                Phân tích ảnh của tôi
                <ArrowIcon />
              </button>
              <span className="text-muted" style={{ fontSize: 12 }}>
                Khoảng 10 giây · Định dạng JPG hoặc PNG
              </span>
            </>
          )}

          {error && (
            <div className="tag tag-accent" style={{ display: "block", padding: "var(--space-3)", fontSize: 13 }}>
              {error}
            </div>
          )}

          {diagnosis && (
            <>
              {advice ? (
                <span className={`tag ${SEVERITY_TAG_CLASS[advice.urgency]}`}>Tổng quan: {OVERVIEW_LABEL_VI[advice.urgency]}</span>
              ) : (
                <span className="tag tag-outline">Đang hỏi thêm để đánh giá chính xác hơn…</span>
              )}

              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                {diagnosis.findings.length === 0 ? (
                  <p className="text-muted" style={{ fontSize: 13, margin: 0 }}>Không phát hiện bất thường trong ảnh.</p>
                ) : (
                  diagnosis.findings.map((f, i) => {
                    const assessment = advice?.per_condition.find((pc) => pc.condition === f.condition);
                    return (
                      <div className="card" key={i} style={{ padding: "var(--space-2) var(--space-3)" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-2)" }}>
                          <span className="card-title" style={{ fontSize: 13 }}>{labelForCondition(f.condition)}</span>
                          {assessment && (
                            <span className={`tag ${SEVERITY_TAG_CLASS[assessment.severity]}`}>{SEVERITY_LABEL_VI[assessment.severity]}</span>
                          )}
                        </div>
                        {assessment && <p className="card-body" style={{ fontSize: 12 }}>{assessment.note}</p>}
                      </div>
                    );
                  })
                )}
              </div>

              <button type="button" className="btn btn-secondary" onClick={reset} style={{ marginTop: "auto" }}>
                Quét ảnh khác
              </button>
            </>
          )}
        </aside>

        <section className="panel-chat">
          <div className="chat-header">
            <ToothIcon />
            <span>Trò chuyện với Smart Smile</span>
          </div>

          <div className="chat-scroll" ref={chatScrollRef}>
            {chatTurns.length === 0 && !isAnalyzing && (
              <div className="chat-row">
                <span className="chat-avatar chat-avatar-agent"><ToothIcon /></span>
                <div className="chat-bubble">
                  Chào bạn! Mình là trợ lý sàng lọc răng miệng Smart Smile. Tải một tấm ảnh răng miệng lên
                  bên trái (kèm mô tả triệu chứng nếu có) để mình bắt đầu kiểm tra nhé.
                </div>
              </div>
            )}

            {chatTurns.map((t, i) => (
              <div className={`chat-row ${t.role === "user" ? "user" : ""}`} key={i}>
                <span className={`chat-avatar ${t.role === "user" ? "chat-avatar-user" : "chat-avatar-agent"}`}>
                  {t.role === "user" ? "B" : <ToothIcon />}
                </span>
                <div className={`chat-bubble ${t.kind === "narrative" ? "chat-bubble-narrative" : ""}`}>
                  {t.kind === "narrative" ? (
                    <NarrativeReport text={t.text} disclaimer={advice?.disclaimer} />
                  ) : (
                    renderRichText(t.text)
                  )}
                </div>
              </div>
            ))}

            {(isAnalyzing || isSending) && (
              <div className="chat-row">
                <span className="chat-avatar chat-avatar-agent"><ToothIcon /></span>
                <div className="chat-bubble">
                  <TypingDots />
                </div>
              </div>
            )}
          </div>

          <div className="chat-inputbar">
            {chatError && (
              <div className="tag tag-accent" style={{ display: "block", marginBottom: "var(--space-2)", padding: "var(--space-3)", fontSize: 13 }}>
                {chatError}
              </div>
            )}
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder={chatDisabled ? "Tải ảnh lên bên trái để bắt đầu…" : "Nhập câu hỏi hoặc câu trả lời của bạn..."}
                value={draft}
                disabled={chatDisabled || isSending}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendAnswer()}
              />
              <button type="button" className="btn btn-primary" disabled={chatDisabled || isSending || !draft.trim()} onClick={sendAnswer}>
                <SendIcon />
              </button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
