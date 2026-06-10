import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import ActiveListingsSection from "./ActiveListingsSection";
import AgentChip from "./AgentChip";
import AgentTraceSection from "./AgentTraceSection";
import { getHomeOSCaseFile, scheduleHomeOSViewing } from "../lib/api";
import { formatDistance, formatPsf, formatSGD } from "../lib/format";
import type { BlockSummary, HomeOSCaseFile, HomeOSScheduleViewingResponse, HomeOSShortlistRow } from "../types";

interface Props {
  block: BlockSummary | null;
  profileText?: string;
  caseId?: string;
  recommendation?: HomeOSShortlistRow | null;
  onClose: () => void;
  onBack?: () => void;
}

export default function HomeOSDetailPanel({ block, profileText, caseId, recommendation, onClose, onBack }: Props) {
  const [caseFile, setCaseFile] = useState<HomeOSCaseFile | null>(null);
  const [caseFileLoading, setCaseFileLoading] = useState(false);
  const [contactName, setContactName] = useState("");
  const [availability, setAvailability] = useState("");
  const [outbox, setOutbox] = useState<HomeOSScheduleViewingResponse | null>(null);
  const [scheduling, setScheduling] = useState(false);

  useEffect(() => {
    if (!block || !profileText) {
      setCaseFile(null);
      setOutbox(null);
      return;
    }
    setCaseFile(null);
    setOutbox(null);
    setCaseFileLoading(true);
    getHomeOSCaseFile(block.block_id, profileText, caseId)
      .then(setCaseFile)
      .catch(() => setCaseFile(null))
      .finally(() => setCaseFileLoading(false));
  }, [block?.block_id, profileText]);

  async function handleSchedule() {
    if (!block || !profileText) return;
    const slots = availability.split(/\n|,/).map((s) => s.trim()).filter(Boolean);
    setScheduling(true);
    try {
      const res = await scheduleHomeOSViewing({
        profile_text: profileText,
        block_id: block.block_id,
        availability: slots,
        contact_name: contactName,
      });
      setOutbox(res);
    } finally {
      setScheduling(false);
    }
  }

  function handleDownloadCase() {
    if (!caseFile) return;
    const payload = JSON.stringify(caseFile, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const casePart = caseId ? `-${caseId.slice(0, 8)}` : "";
    anchor.href = url;
    anchor.download = `homeos-case-${caseFile.block_id}${casePart}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  if (!block) return null;

  const displayedVerdict = recommendation?.verdict ?? caseFile?.verdict;
  const displayedScore = recommendation?.worth_viewing_score ?? caseFile?.worth_viewing_score;
  const displayedReasons = recommendation?.top_reasons ?? caseFile?.top_reasons ?? [];
  const displayedWatchouts = recommendation?.top_watchouts ?? caseFile?.top_watchouts ?? [];
  const verdictColor =
    displayedVerdict === "Worth viewing"
      ? "bg-emerald-100 text-emerald-700"
      : displayedVerdict === "Maybe view"
        ? "bg-amber-100 text-amber-700"
        : "bg-muted text-muted-foreground";

  return (
    <div className="absolute top-0 right-0 z-[1000] h-full w-80 overflow-y-auto border-l border-border bg-card shadow-xl flex flex-col">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 p-4 border-b border-border">
        <div>
          <p className="text-sm font-bold text-foreground leading-tight">
            Blk {block.block_number} {block.street_name}
          </p>
          <p className="text-xs text-muted-foreground">{block.town}</p>
          {displayedVerdict && displayedScore != null && (
            <span className={`mt-1 inline-block rounded px-2 py-0.5 text-xs font-semibold ${verdictColor}`}>
              {displayedVerdict} · {displayedScore}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {caseFile && (
            <button
              type="button"
              onClick={handleDownloadCase}
              className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
              aria-label="Download case"
              title="Download case"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Download</span>
            </button>
          )}
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
            >
              Pipeline
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-muted"
            aria-label="Close panel"
          >
            x
          </button>
        </div>
      </div>

      {/* Key numbers */}
      <div className="p-4 border-b border-border space-y-1.5">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
          Key numbers
        </p>
        <Row label="Median price" value={formatSGD(block.median_price)} />
        <Row label="Median PSF" value={formatPsf(block.median_psf)} />
        <Row label="MRT distance" value={formatDistance(block.nearest_mrt_distance_m)} />
        <Row label="Schools (1km)" value={String(block.schools_within_1km ?? "—")} />
        <Row label="Transactions" value={String(block.txn_count)} />
      </div>

      <ActiveListingsSection blockId={block.block_id} caseId={caseId} />

      {/* HomeOS evidence */}
      {profileText && (
        <div className="p-4 border-b border-border">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            HomeOS evidence
          </p>
          {caseFileLoading && (
            <p className="text-xs text-muted-foreground">Loading case file…</p>
          )}
          {caseFile && !caseFileLoading && (
            <div className="space-y-3">
              <div>
                <p className="text-xs text-muted-foreground">{caseFile.evidence.recent_sales.summary}</p>
              </div>

              {displayedReasons.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-emerald-700">Why it fits</p>
                  {displayedReasons.map((r) => (
                    <p key={r.text} className="text-xs text-muted-foreground">
                      ✓ {r.text}
                      <AgentChip source={r.source} />
                    </p>
                  ))}
                </div>
              )}

              {displayedWatchouts.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-amber-600">Watchouts</p>
                  {displayedWatchouts.map((w) => (
                    <p key={w.text} className="text-xs text-muted-foreground">
                      ⚠ {w.text}
                      <AgentChip source={w.source} />
                    </p>
                  ))}
                </div>
              )}

              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">
                  Questions for agent
                  <span className="ml-1 text-[10px] font-normal text-muted-foreground/70">
                    · synthesised from all agents
                  </span>
                </p>
                <ul className="space-y-1">
                  {caseFile.evidence.agent_questions.map((q) => (
                    <li key={q} className="text-xs text-muted-foreground">• {q}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          {!profileText && (
            <p className="text-xs text-muted-foreground">
              Switch to AI Mode to see HomeOS evidence for this block.
            </p>
          )}
        </div>
      )}

      {profileText && caseFile && <AgentTraceSection trace={caseFile.trace} />}

      {/* Schedule viewing */}
      {profileText && caseFile && !outbox && (
        <div className="p-4 border-b border-border space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Schedule a viewing
          </p>
          <div>
            <label htmlFor="detail-contact" className="block text-xs text-muted-foreground mb-1">
              Your name
            </label>
            <input
              id="detail-contact"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="detail-avail" className="block text-xs text-muted-foreground mb-1">
              Availability (one slot per line)
            </label>
            <textarea
              id="detail-avail"
              className="w-full min-h-16 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="e.g. Sat 10–12am"
              value={availability}
              onChange={(e) => setAvailability(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            disabled={scheduling || !contactName.trim() || !availability.trim()}
            onClick={handleSchedule}
          >
            {scheduling ? "Scheduling…" : "Schedule viewing"}
          </button>
        </div>
      )}

      {/* Outbox */}
      {outbox && (
        <div className="p-4 space-y-2">
          <p className="text-sm font-semibold text-emerald-800">Scheduling outbox</p>
          <p className="text-xs text-emerald-700">{outbox.confirmation}</p>
          <p className="text-xs text-emerald-900 bg-emerald-50 border border-emerald-100 rounded p-2 leading-relaxed">
            {outbox.outbox.message}
          </p>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-medium text-foreground">{value}</span>
    </div>
  );
}
