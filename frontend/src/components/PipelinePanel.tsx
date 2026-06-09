import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  CircleDot,
  Loader2,
  MessageSquare,
  Send,
} from "lucide-react";
import type { AgentEvent, HomeOSCase, HomeOSShortlistRow } from "../types";

const AGENT_LABELS: Record<string, string> = {
  profile: "Parsing avatar",
  market: "Querying Market Evidence",
  location: "Querying Location Graph",
  risk: "Running Risk Evaluation",
  questions: "Preparing Agent Questions",
};

const DONE_LABELS: Record<string, string> = {
  profile: "Family profile detected",
  market: "Market evidence summarized",
  location: "Location graph cross-referenced",
  risk: "Risk signals evaluated",
  questions: "Viewing questions prepared",
};

const DETAIL_LABELS: Record<string, string> = {
  profile: "Profile Agent",
  market: "Market Agent",
  location: "Location Agent",
  risk: "Risk Agent",
  questions: "Questions Agent",
};

interface Props {
  activeCase: HomeOSCase | null;
  streamingEvents: AgentEvent[];
  onSelectBlock: (blockId: number) => void;
  onSendMessage: (message: string) => void;
  chatChunks?: string;
}

function agentKey(event: AgentEvent) {
  return `${event.agent ?? "case"}-${event.block_id ?? "profile"}`;
}

function StepRow({
  event,
  expanded,
  onToggle,
}: {
  event: AgentEvent;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isStart = event.event === "agent_start";
  const label = AGENT_LABELS[event.agent ?? ""] ?? event.agent ?? "Case";
  const done = DONE_LABELS[event.agent ?? ""] ?? "Completed";
  const detailLabel = DETAIL_LABELS[event.agent ?? ""] ?? label;
  const blockText = event.block_id != null ? `Blk ${event.block_id}` : "";
  const text = event.event === "agent_summary"
    ? event.narrative
    : isStart
      ? `${label}... ${blockText}`.trim()
      : `${label}... ${done}`;

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2 rounded-full bg-muted/70 px-3 py-2 text-left hover:bg-muted"
      >
        {isStart ? (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
        )}
        <p className="truncate font-mono text-xs text-muted-foreground">{text}</p>
      </button>
      {expanded && (
        <div className="mt-1 rounded-md border border-border bg-background p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-foreground">{detailLabel}</p>
            {event.block_id != null && (
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                Blk {event.block_id}
              </span>
            )}
          </div>
          {text && (
            <p className="mt-2 whitespace-pre-wrap text-xs leading-snug text-muted-foreground">
              {text}
            </p>
          )}
          {event.data && (
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-2 text-[10px] leading-relaxed text-muted-foreground">
              {JSON.stringify(event.data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function ListingRow({
  row,
  index,
  onSelectBlock,
}: {
  row: HomeOSShortlistRow;
  index: number;
  onSelectBlock: (blockId: number) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelectBlock(row.block_id)}
      className="w-full rounded-md border border-border bg-card p-3 text-left hover:bg-muted"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-foreground">
            {index + 1}. Blk {row.block_number} {row.street_name}
          </p>
          <p className="text-[11px] text-muted-foreground">{row.town}</p>
        </div>
        <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
          {row.worth_viewing_score}
        </span>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        {row.top_reasons[0] ?? row.verdict}
      </p>
    </button>
  );
}

export default function PipelinePanel({
  activeCase,
  streamingEvents,
  onSelectBlock,
  onSendMessage,
  chatChunks = "",
}: Props) {
  const [chatInput, setChatInput] = useState("");
  const [expandedEventKey, setExpandedEventKey] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const allEvents = useMemo(
    () => [...(activeCase?.pipeline ?? []), ...streamingEvents],
    [activeCase?.pipeline, streamingEvents],
  );

  const visibleEvents = useMemo(() => {
    const summaries = allEvents.filter((event) => event.event === "agent_summary");
    const latestStarts = new Map<string, AgentEvent>();
    const done = new Set(
      allEvents
        .filter((event) => event.event === "agent_done")
        .map(agentKey),
    );

    for (const event of allEvents) {
      if (event.event === "agent_start" && !done.has(agentKey(event))) {
        latestStarts.set(agentKey(event), event);
      }
    }

    return [...summaries, ...latestStarts.values()];
  }, [allEvents]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [visibleEvents.length, activeCase?.conversation.length, chatChunks]);

  function submitChat(event: React.FormEvent) {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message) return;
    onSendMessage(message);
    setChatInput("");
  }

  if (!activeCase && streamingEvents.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <p className="text-center text-xs text-muted-foreground">
          Start a case to see HomeOS agents work through profile, market,
          location, and risk evidence.
        </p>
      </div>
    );
  }

  const shortlist = activeCase?.shortlist ?? [];

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-bold text-foreground">
              {activeCase?.avatar?.label ?? "HomeOS Investigation"}
            </p>
            <p className="mt-1 text-xs leading-snug text-muted-foreground">
              {activeCase?.avatar?.summary ?? "Streaming case evidence..."}
            </p>
          </div>
          <span className="rounded bg-primary/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-primary">
            Case
          </span>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="space-y-2">
          {visibleEvents.length === 0 && (
            <div className="flex items-center gap-2 rounded-full bg-muted/70 px-3 py-2">
              <CircleDot className="h-3.5 w-3.5 text-primary" />
              <p className="font-mono text-xs text-muted-foreground">
                Waiting for agent pipeline...
              </p>
            </div>
          )}
          {visibleEvents.map((event, index) => (
            <StepRow
              key={`${event.event}-${agentKey(event)}-${index}`}
              event={event}
              expanded={expandedEventKey === `${event.event}-${agentKey(event)}-${index}`}
              onToggle={() => {
                const key = `${event.event}-${agentKey(event)}-${index}`;
                setExpandedEventKey((current) => current === key ? null : key);
              }}
            />
          ))}
        </div>

        {shortlist.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {shortlist.length} recommended listings
            </p>
            <div className="space-y-2">
              {shortlist.map((row, index) => (
                <ListingRow
                  key={row.block_id}
                  row={row}
                  index={index}
                  onSelectBlock={onSelectBlock}
                />
              ))}
            </div>
          </div>
        )}

        {(activeCase?.conversation ?? []).map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`mt-3 rounded-md px-3 py-2 text-xs ${
              message.role === "user"
                ? "ml-5 bg-primary/10 text-foreground"
                : "mr-5 bg-muted text-foreground"
            }`}
          >
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {message.role === "user" ? "You" : "HomeOS"}
            </p>
            {message.content}
          </div>
        ))}

        {chatChunks && (
          <div className="mr-5 mt-3 rounded-md bg-muted px-3 py-2 text-xs text-foreground">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              HomeOS
            </p>
            {chatChunks}
          </div>
        )}
        <div ref={endRef} />
      </div>

      {activeCase?.status === "done" && (
        <form
          role="form"
          onSubmit={submitChat}
          className="flex gap-2 border-t border-border p-3"
        >
          <div className="relative flex-1">
            <MessageSquare className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <input
              className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Ask HomeOS about this case..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
            />
          </div>
          <button
            type="submit"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground disabled:opacity-50"
            disabled={!chatInput.trim()}
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      )}
    </div>
  );
}
