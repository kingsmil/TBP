import { useState, useMemo } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Download, Home, Loader2, MapPin, Smile, TrendingUp } from "lucide-react";
import AgentProgressRows from "./AgentProgressRows";
import { deriveAgentProgress, deriveBlockNarratives } from "../lib/agentProgress";
import type { AgentEvent, AgentKey, BlockNarrativeMap, HomeOSCase, HomeOSShortlistRow } from "../types";

const NARRATIVE_CONFIG: { key: AgentKey; label: string; Icon: React.ElementType }[] = [
  { key: "market", label: "Market", Icon: TrendingUp },
  { key: "location", label: "Location", Icon: MapPin },
  { key: "lifestyle", label: "Lifestyle", Icon: Smile },
  { key: "risk", label: "Risk", Icon: AlertTriangle },
];

interface Props {
  activeCase: HomeOSCase | null;
  streamingEvents: AgentEvent[];
  onSelectBlock: (blockId: number) => void;
  onSendMessage: (message: string) => void;
  chatChunks?: string;
  blockNarratives?: BlockNarrativeMap;
}

function ListingRow({
  row,
  index,
  onSelectBlock,
  narratives,
}: {
  row: HomeOSShortlistRow;
  index: number;
  onSelectBlock: (blockId: number) => void;
  narratives?: Map<AgentKey, string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasNarratives = narratives && narratives.size > 0;

  return (
    <div className="rounded-lg border border-border bg-card shadow-sm">
      <div className="flex items-start gap-2 p-3">
        {hasNarratives ? (
          <button
            type="button"
            aria-label={`Expand block ${row.block_id} agent logs`}
            onClick={() => setExpanded((v) => !v)}
            className="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
          >
            {expanded
              ? <ChevronDown className="h-3.5 w-3.5" />
              : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        ) : (
          <span className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        )}

        <button
          type="button"
          onClick={() => onSelectBlock(row.block_id)}
          className="min-w-0 flex-1 text-left"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">
                {index + 1}. Blk {row.block_number} {row.street_name}
              </p>
              <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                <MapPin className="h-3 w-3" />
                {row.town}
              </p>
            </div>
            <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-700">
              {row.worth_viewing_score}
            </span>
          </div>
          <p className="mt-3 text-xs font-medium text-foreground">{row.verdict}</p>
          {row.top_reasons.slice(0, 2).map((reason) => (
            <p key={reason.text} className="mt-1 text-xs leading-snug text-muted-foreground">
              {reason.text}
            </p>
          ))}
        </button>
      </div>

      {expanded && hasNarratives && (
        <div className="space-y-1.5 border-t border-border px-3 pb-3 pt-2">
          {NARRATIVE_CONFIG.map(({ key, label, Icon }) => {
            const narrative = narratives.get(key);
            if (!narrative) return null;
            return (
              <div key={key} className="flex items-start gap-1.5">
                <Icon className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{label}</span> — {narrative}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function PipelinePanel({
  activeCase,
  streamingEvents,
  onSelectBlock,
  blockNarratives: externalNarratives,
}: Props) {
  const caseDoneEvent = useMemo(
    () => [...streamingEvents].reverse().find((event) => event.event === "case_done"),
    [streamingEvents],
  );
  const streamedShortlist = caseDoneEvent?.shortlist ?? [];
  const shortlist = activeCase?.shortlist?.length ? activeCase.shortlist : streamedShortlist;
  const isWorking = activeCase?.status === "running" || (!activeCase && streamingEvents.length > 0);
  const isRefining = activeCase?.status === "refining";
  const isError = activeCase?.status === "error";
  const hasNoMatches = (activeCase?.status === "done" || caseDoneEvent != null) && shortlist.length === 0;

  const allEvents = useMemo(
    () => [...(activeCase?.pipeline ?? []), ...streamingEvents],
    [activeCase?.pipeline, streamingEvents],
  );

  const agentProgress = useMemo(() => deriveAgentProgress(allEvents), [allEvents]);
  const derivedNarratives = useMemo(() => deriveBlockNarratives(allEvents), [allEvents]);
  const blockNarratives = externalNarratives ?? derivedNarratives;

  const hasBlockEvents = useMemo(
    () => allEvents.some((e) => e.block_id != null),
    [allEvents],
  );

  const globalStatus = useMemo(() => {
    if (hasBlockEvents) return null;
    const last = [...allEvents].reverse().find(
      (e) => e.event === "agent_start" || e.event === "agent_done" || e.event === "agent_summary",
    );
    if (!last) return null;
    if (last.agent === "profile") return "Profiling requirements…";
    if (last.agent === "search") return "Searching for candidates…";
    return null;
  }, [allEvents, hasBlockEvents]);

  function handleDownloadCase() {
    if (!activeCase) return;
    const payload = JSON.stringify(activeCase, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `homeos-case-${activeCase.case_id.slice(0, 8)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  if (!activeCase && streamingEvents.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="text-center">
          <Home className="mx-auto h-6 w-6 text-muted-foreground" />
          <p className="mt-2 text-xs text-muted-foreground">
            Describe your requirements to receive recommended listings.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-border p-4">
        <div className="min-w-0">
          <p className="text-sm font-bold text-foreground">Recommended listings</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {hasNoMatches
              ? "No properties meet specified requirements. Please try with less strict requirements."
              : shortlist.length > 0
              ? `${shortlist.length} homes matched to your requirements.`
              : isRefining
                ? "Answer the question in the chat to refine your recommendations."
                : "HomeOS is matching homes to your requirements."}
          </p>
        </div>
        {activeCase && (
          <button
            type="button"
            onClick={handleDownloadCase}
            className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted"
            aria-label="Download case"
            title="Download case"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Download</span>
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {isWorking && shortlist.length === 0 && !hasBlockEvents && (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/60 p-3">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <p className="text-xs text-muted-foreground">
              {globalStatus ?? "Finding the best matching listings..."}
            </p>
          </div>
        )}

        {isWorking && shortlist.length === 0 && hasBlockEvents && (
          <AgentProgressRows agentProgress={agentProgress} globalStatus={null} />
        )}

        {isRefining && shortlist.length === 0 && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            More information is needed before recommendations can be prepared.
          </p>
        )}

        {isError && (
          <p className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive">
            Recommendations could not be prepared. Please try again.
          </p>
        )}

        {hasNoMatches && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            No properties meet specified requirements. Please try with less strict requirements.
          </p>
        )}

        {shortlist.length > 0 && (
          <div className="space-y-2">
            {shortlist.map((row, index) => (
              <ListingRow
                key={row.block_id}
                row={row}
                index={index}
                onSelectBlock={onSelectBlock}
                narratives={blockNarratives.get(row.block_id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
