"use client";

import { useRef, useState, useCallback } from "react";
import { Upload, Receipt, AlertCircle, Loader2, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

interface ReceiptItem {
  name: string;
  quantity: number | null;
  unit_price: number | null;
  total_price: number | null;
}

interface ReceiptData {
  store_name: string | null;
  date: string | null;
  items: ReceiptItem[];
  subtotal: number | null;
  tax: number | null;
  total: number | null;
  currency: string | null;
  raw_text: string | null;
}

interface ParseResult {
  receipt: ReceiptData;
  model: string;
  confidence: string;
}

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "done"; result: ParseResult; preview: string }
  | { status: "error"; message: string };

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "text-green-400",
  medium: "text-yellow-400",
  low: "text-red-400",
};

function fmt(n: number | null, currency?: string | null) {
  if (n === null) return "—";
  return currency ? `${n.toFixed(2)} ${currency}` : n.toFixed(2);
}

function Row({ label, value, bold }: { label: string; value: string | null | undefined; bold?: boolean }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className={bold ? "text-white font-semibold" : "text-gray-300"}>{value || "—"}</span>
    </div>
  );
}

export default function Home() {
  const [state, setState] = useState<State>({ status: "idle" });
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function processFile(file: File) {
    if (!file.type.startsWith("image/")) {
      setState({ status: "error", message: "Upload a JPEG, PNG, or WEBP image." });
      return;
    }

    const preview = URL.createObjectURL(file);
    setState({ status: "loading" });

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${API}/parse`, { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `${res.status} ${res.statusText}`);
      }
      const result: ParseResult = await res.json();
      setState({ status: "done", result, preview });
    } catch (e: unknown) {
      setState({ status: "error", message: e instanceof Error ? e.message : "Unknown error" });
    }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
    e.target.value = "";
  };

  function reset() {
    if (state.status === "done") URL.revokeObjectURL(state.preview);
    setState({ status: "idle" });
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <div className="mb-10">
        <h1 className="text-3xl font-semibold text-white flex items-center gap-3">
          <Receipt className="w-8 h-8 text-indigo-400" />
          receipt-lens
        </h1>
        <p className="text-gray-500 mt-2 text-sm">
          Drop in a receipt photo, get back structured data. Runs locally with Ollama.
        </p>
      </div>

      {state.status !== "done" && (
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={
            "border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-colors " +
            (dragging ? "border-indigo-500 bg-indigo-950/30" : "border-gray-700 hover:border-gray-500")
          }
        >
          {state.status === "loading" ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
              <p className="text-gray-400 text-sm">Parsing receipt...</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Upload className="w-10 h-10 text-gray-600" />
              <p className="text-gray-400 text-sm">
                Drag and drop a receipt image, or{" "}
                <span className="text-indigo-400">click to browse</span>
              </p>
              <p className="text-gray-600 text-xs">JPEG, PNG, WEBP — max 10 MB</p>
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={onFileChange}
            className="hidden"
          />
        </div>
      )}

      {state.status === "error" && (
        <div className="mt-4 flex items-start gap-3 bg-red-950 border border-red-800 rounded-xl p-4">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <p className="text-red-300 text-sm">{state.message}</p>
        </div>
      )}

      {state.status === "done" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">Model: {state.result.model}</span>
              <span className={"text-xs font-medium " + (CONFIDENCE_COLOR[state.result.confidence] || "text-gray-400")}>
                {state.result.confidence} confidence
              </span>
            </div>
            <button
              onClick={reset}
              className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
              Parse another
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="border border-gray-800 rounded-xl overflow-hidden bg-gray-900">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={state.preview} alt="Receipt" className="w-full object-contain max-h-96" />
            </div>

            <div className="space-y-4">
              <div className="border border-gray-800 rounded-xl p-4 bg-gray-900 space-y-2">
                <Row label="Store" value={state.result.receipt.store_name} />
                <Row label="Date" value={state.result.receipt.date} />
                <Row label="Currency" value={state.result.receipt.currency} />
              </div>

              {state.result.receipt.items.length > 0 && (
                <div className="border border-gray-800 rounded-xl overflow-hidden">
                  <div className="bg-gray-900 px-4 py-2 text-xs font-medium text-gray-400 border-b border-gray-800">
                    Items
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-800 bg-gray-900/50">
                        <th className="text-left px-4 py-2 text-gray-500 font-normal text-xs">Name</th>
                        <th className="text-right px-4 py-2 text-gray-500 font-normal text-xs">Qty</th>
                        <th className="text-right px-4 py-2 text-gray-500 font-normal text-xs">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {state.result.receipt.items.map((item, i) => (
                        <tr key={i} className="border-b border-gray-800 last:border-0">
                          <td className="px-4 py-2 text-gray-200">{item.name}</td>
                          <td className="px-4 py-2 text-right text-gray-400">{item.quantity ?? "—"}</td>
                          <td className="px-4 py-2 text-right text-gray-300">
                            {fmt(item.total_price, state.result.receipt.currency)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="border border-gray-800 rounded-xl p-4 bg-gray-900 space-y-2">
                <Row label="Subtotal" value={fmt(state.result.receipt.subtotal, state.result.receipt.currency)} />
                <Row label="Tax" value={fmt(state.result.receipt.tax, state.result.receipt.currency)} />
                <div className="border-t border-gray-700 pt-2 mt-1">
                  <Row
                    label="Total"
                    value={fmt(state.result.receipt.total, state.result.receipt.currency)}
                    bold
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
