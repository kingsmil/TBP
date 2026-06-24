import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, KeyRound, Scale, Sparkles, RotateCcw } from "lucide-react";
import { getRecommendQuestions, getCompareOptions, postRecommend } from "../lib/api";
import type { RecommendResult } from "../types";

interface Props {
  onSelect: (product: "resale" | "bto") => void;
}

const VERDICT: Record<string, { label: string; cls: string; icon: typeof Building2 }> = {
  bto: { label: "New flat (BTO)", cls: "text-sky-700 bg-sky-50 border-sky-200", icon: Building2 },
  resale: { label: "Resale flat", cls: "text-amber-700 bg-amber-50 border-amber-200", icon: KeyRound },
  either: { label: "Either could work", cls: "text-foreground bg-muted border-border", icon: Scale },
};

export default function RecommendWizard({ onSelect }: Props) {
  const questions = useQuery({ queryKey: ["recommend-questions"], queryFn: getRecommendQuestions, staleTime: 6e5 });
  const options = useQuery({ queryKey: ["compare-options"], queryFn: getCompareOptions, staleTime: 6e5 });

  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [town, setTown] = useState("");
  const [flatType, setFlatType] = useState("");
  const [result, setResult] = useState<RecommendResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (options.data && !town) {
      setTown(options.data.towns.includes("Punggol") ? "Punggol" : options.data.towns[0] ?? "");
      setFlatType(options.data.flat_types.includes("4-room") ? "4-room" : options.data.flat_types[0] ?? "");
    }
  }, [options.data, town]);

  const answeredCount = Object.keys(answers).length;

  async function submit() {
    setLoading(true);
    try {
      setResult(await postRecommend({ answers, town: town || undefined, flat_type: flatType || undefined }));
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    const v = VERDICT[result.recommendation];
    const Icon = v.icon;
    const other = result.recommendation === "bto" ? "resale" : "bto";
    return (
      <div className="space-y-4">
        <div className={`rounded-xl border p-5 ${v.cls}`}>
          <div className="text-xs font-medium uppercase tracking-wide opacity-70">
            {result.confidence === "lean" ? "It's close — leaning" : `We'd suggest (${result.confidence})`}
          </div>
          <div className="mt-1 flex items-center gap-2 text-2xl font-bold">
            <Icon className="h-6 w-6" /> {v.label}
          </div>
          <ul className="mt-3 space-y-1.5 text-sm">
            {result.reasons.map((r, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: static reason list
              <li key={i} className="flex gap-2"><span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-current" />{r}</li>
            ))}
          </ul>
        </div>

        <div className="flex flex-wrap gap-2">
          {result.recommendation !== "either" && (
            <button type="button" onClick={() => onSelect(result.recommendation as "bto" | "resale")}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
              Explore {VERDICT[result.recommendation].label}
            </button>
          )}
          <button type="button" onClick={() => onSelect((result.recommendation === "either" ? "bto" : other) as "bto" | "resale")}
            className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-muted">
            Explore {VERDICT[result.recommendation === "either" ? "bto" : other].label}
          </button>
          <button type="button" onClick={() => { setResult(null); setAnswers({}); }}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted">
            <RotateCcw className="h-3.5 w-3.5" /> Start over
          </button>
        </div>
        <p className="text-[10px] text-muted-foreground">Indicative guidance from your answers and live prices — not financial advice.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Optional grounding */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-muted/30 p-3">
        <div className="text-xs text-muted-foreground">Optional — grounds the advice in real prices:</div>
        <select value={town} onChange={(e) => setTown(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs">
          {(options.data?.towns ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={flatType} onChange={(e) => setFlatType(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs">
          {(options.data?.flat_types ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {/* Questions */}
      <div className="space-y-4">
        {(questions.data?.questions ?? []).map((q) => (
          <div key={q.id}>
            <div className="mb-1.5 text-sm font-medium">{q.label}</div>
            <div className="flex flex-wrap gap-2">
              {q.options.map((o) => {
                const active = answers[q.id] === o.value;
                return (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => setAnswers((a) => ({ ...a, [q.id]: o.value }))}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                      active ? "bg-primary text-primary-foreground" : "border border-border bg-card hover:bg-muted"
                    }`}
                  >
                    {o.label}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <button type="button" onClick={() => void submit()} disabled={loading || answeredCount === 0}
        className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
        <Sparkles className="h-4 w-4" /> {loading ? "Thinking…" : "Get my recommendation"}
      </button>
      {answeredCount === 0 && <p className="text-[11px] text-muted-foreground">Answer at least one question to get a recommendation.</p>}
    </div>
  );
}
