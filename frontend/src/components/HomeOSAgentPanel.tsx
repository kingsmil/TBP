import { useState } from "react";
import { getHomeOSCaseFile, investigateHomeOSProfile, scheduleHomeOSViewing } from "../lib/api";
import { formatPsf, formatSGD } from "../lib/format";
import type {
  HomeOSCaseFile,
  HomeOSInvestigationResponse,
  HomeOSScheduleViewingResponse,
  HomeOSShortlistRow,
} from "../types";

const DEFAULT_PROFILE =
  "Looking for a flat anywhere in Singapore, no specific requirements yet.";

interface Props {
  onShortlist?: (blockIds: number[]) => void;
  onSelectBlock?: (blockId: number) => void;
  profileText: string;
  onProfileChange: (text: string) => void;
}

export default function HomeOSAgentPanel({
  onShortlist,
  onSelectBlock,
  profileText,
  onProfileChange,
}: Props) {
  const [investigation, setInvestigation] = useState<HomeOSInvestigationResponse | null>(null);
  const [caseFile, setCaseFile] = useState<HomeOSCaseFile | null>(null);
  const [selected, setSelected] = useState<HomeOSShortlistRow | null>(null);
  const [contactName, setContactName] = useState("");
  const [availability, setAvailability] = useState("");
  const [outbox, setOutbox] = useState<HomeOSScheduleViewingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function investigate() {
    setLoading(true);
    setError(null);
    setOutbox(null);
    setCaseFile(null);
    setSelected(null);
    try {
      const next = await investigateHomeOSProfile(profileText, 5);
      setInvestigation(next);
      onShortlist?.(next.shortlist.map((r) => r.block_id));
    } catch {
      setError("Could not reach the API. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  async function openCaseFile(row: HomeOSShortlistRow) {
    setSelected(row);
    setOutbox(null);
    setLoading(true);
    try {
      const next = await getHomeOSCaseFile(row.block_id, profileText);
      setCaseFile(next);
      onSelectBlock?.(row.block_id);
    } catch {
      setError("Could not load case file.");
    } finally {
      setLoading(false);
    }
  }

  async function scheduleViewing() {
    if (!selected) return;
    const slots = availability.split(/\n|,/).map((s) => s.trim()).filter(Boolean);
    setLoading(true);
    try {
      const next = await scheduleHomeOSViewing({
        profile_text: profileText,
        block_id: selected.block_id,
        availability: slots,
        contact_name: contactName,
      });
      setOutbox(next);
    } catch {
      setError("Could not schedule viewing.");
    } finally {
      setLoading(false);
    }
  }

  const verdictColor = (v: string) =>
    v === "Worth viewing"
      ? "bg-emerald-100 text-emerald-700"
      : v === "Maybe view"
        ? "bg-amber-100 text-amber-700"
        : "bg-gray-100 text-gray-500";

  return (
    <div className="flex flex-col gap-3 p-4">
      <div>
        <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-1">
          HomeOS Agent
        </p>
      </div>

      <div>
        <label
          htmlFor="homeos-profile"
          className="block text-xs font-medium text-muted-foreground mb-1"
        >
          Household profile
        </label>
        <textarea
          id="homeos-profile"
          className="w-full min-h-20 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder={DEFAULT_PROFILE}
          value={profileText}
          onChange={(e) => onProfileChange(e.target.value)}
        />
      </div>

      <button
        type="button"
        className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
        disabled={loading || profileText.trim().length < 10}
        onClick={investigate}
      >
        {loading && !investigation ? "Investigating…" : "Investigate homes"}
      </button>

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}

      {investigation && (
        <div className="rounded-md border border-border bg-muted/40 px-3 py-2">
          <p className="text-sm font-semibold text-foreground">{investigation.avatar.label}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{investigation.avatar.summary}</p>
        </div>
      )}

      {investigation?.shortlist.map((row) => (
        <div key={row.block_id} className="rounded-md border border-border bg-card p-3 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-foreground leading-tight">
                Blk {row.block_number} {row.street_name}
              </p>
              <p className="text-xs text-muted-foreground">{row.town}</p>
            </div>
            <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-semibold ${verdictColor(row.verdict)}`}>
              {row.worth_viewing_score}
            </span>
          </div>

          <div className="space-y-0.5">
            {row.top_reasons.map((r) => (
              <p key={r} className="text-xs text-muted-foreground">✓ {r}</p>
            ))}
            {row.top_watchouts[0] && (
              <p className="text-xs text-amber-600">⚠ {row.top_watchouts[0]}</p>
            )}
          </div>

          <button
            type="button"
            className="w-full rounded border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
            onClick={() => openCaseFile(row)}
          >
            Open case file
          </button>
        </div>
      ))}

      {caseFile && (
        <div className="rounded-md border border-border bg-muted/40 p-3 space-y-3">
          <p className="text-sm font-semibold text-foreground">
            Case file: Blk {caseFile.block_number} {caseFile.street_name}
          </p>

          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">{caseFile.evidence.recent_sales.summary}</p>
            <p className="text-xs text-muted-foreground">
              {formatSGD(caseFile.evidence.recent_sales.median_price)} ·{" "}
              {formatPsf(caseFile.evidence.recent_sales.median_psf)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Questions for agent
            </p>
            <ul className="space-y-1">
              {caseFile.evidence.agent_questions.map((q) => (
                <li key={q} className="text-xs text-muted-foreground">• {q}</li>
              ))}
            </ul>
          </div>

          {!outbox && (
            <>
              <div>
                <label
                  htmlFor="contact-name"
                  className="block text-xs font-medium text-muted-foreground mb-1"
                >
                  Your name
                </label>
                <input
                  id="contact-name"
                  className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                />
              </div>

              <div>
                <label
                  htmlFor="availability"
                  className="block text-xs font-medium text-muted-foreground mb-1"
                >
                  Availability (one slot per line)
                </label>
                <textarea
                  id="availability"
                  className="w-full min-h-16 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  placeholder="e.g. Sat 10–12am, Sun 3–5pm"
                  value={availability}
                  onChange={(e) => setAvailability(e.target.value)}
                />
              </div>

              <button
                type="button"
                className="w-full rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                disabled={loading || !contactName.trim() || !availability.trim()}
                onClick={scheduleViewing}
              >
                {loading ? "Scheduling…" : "Schedule viewing"}
              </button>
            </>
          )}

          {outbox && (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 space-y-1">
              <p className="text-sm font-semibold text-emerald-800">Scheduling outbox</p>
              <p className="text-xs text-emerald-700">{outbox.confirmation}</p>
              <p className="mt-2 text-xs text-emerald-900 bg-white border border-emerald-100 rounded p-2 leading-relaxed">
                {outbox.outbox.message}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
