"use client";

import { useState } from "react";
import { ApiError, diagnose, fileToBase64 } from "@/lib/api";
import {
  CONDITION_LABEL_VI,
  URGENCY_LABEL_VI,
  type DiagnoseResponse,
  type Urgency,
} from "@/lib/types";

const URGENCY_STYLE: Record<Urgency, string> = {
  low: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  high: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};

function formatFromMime(mime: string): string {
  const format = mime.split("/")[1]?.toLowerCase();
  return format === "jpg" ? "jpeg" : (format ?? "jpeg");
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DiagnoseResponse | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    setResult(null);
    setError(null);
    setPreviewUrl(selected ? URL.createObjectURL(selected) : null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const base64 = await fileToBase64(file);
      const response = await diagnose(base64, formatFromMime(file.type));
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không gọi được API — kiểm tra backend đã chạy chưa.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-1 justify-center bg-zinc-50 px-4 py-10 dark:bg-black">
      <main className="w-full max-w-2xl space-y-8">
        <header className="space-y-1">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
            Chẩn đoán tình trạng răng miệng
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Tải ảnh chụp răng miệng lên để nhận chẩn đoán và lời khuyên từ AI.
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <input
            type="file"
            accept="image/jpeg,image/png"
            onChange={handleFileChange}
            className="block w-full text-sm text-zinc-700 file:mr-4 file:rounded-md file:border-0 file:bg-zinc-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-zinc-700 dark:text-zinc-300 dark:file:bg-zinc-100 dark:file:text-zinc-900"
          />

          {previewUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="Ảnh xem trước" className="max-h-72 rounded-md border border-zinc-200 dark:border-zinc-800" />
          )}

          <button
            type="submit"
            disabled={!file || loading}
            className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {loading ? "Đang chẩn đoán…" : "Chẩn đoán"}
          </button>
        </form>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {result && (
          <section className="space-y-4">
            <div className="rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
              <h2 className="mb-3 font-medium text-zinc-900 dark:text-zinc-50">Kết quả phát hiện</h2>
              {result.diagnosis.findings.length === 0 ? (
                <p className="text-sm text-zinc-600 dark:text-zinc-400">Không phát hiện bất thường.</p>
              ) : (
                <ul className="space-y-2">
                  {result.diagnosis.findings.map((f, i) => (
                    <li key={i} className="flex items-center justify-between text-sm">
                      <span className="text-zinc-800 dark:text-zinc-200">{CONDITION_LABEL_VI[f.condition]}</span>
                      <span className="text-zinc-500 dark:text-zinc-400">{(f.confidence * 100).toFixed(0)}%</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-zinc-400">model: {result.diagnosis.model_version}</p>
            </div>

            <div className="rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-medium text-zinc-900 dark:text-zinc-50">Lời khuyên</h2>
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${URGENCY_STYLE[result.advice.urgency]}`}>
                  {URGENCY_LABEL_VI[result.advice.urgency]}
                </span>
              </div>
              <p className="text-sm text-zinc-800 dark:text-zinc-200">{result.advice.summary}</p>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-zinc-700 dark:text-zinc-300">
                {result.advice.recommendations.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
              <p className="mt-4 border-t border-zinc-100 pt-3 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-500">
                {result.advice.disclaimer}
              </p>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
