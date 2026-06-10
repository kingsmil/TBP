import { useMemo } from "react";
import { Home, Loader2, MapPin } from "lucide-react";
import type { AgentEvent, HomeOSCase, HomeOSShortlistRow } from "../types";

interface Props {
  activeCase: HomeOSCase | null;
  streamingEvents: AgentEvent[];
  onSelectBlock: (blockId: number) => void;
  onSendMessage: (message: string) => void;
  chatChunks?: string;
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
      className="w-full rounded-lg border border-border bg-card p-3 text-left shadow-sm transition-colors hover:bg-muted"
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
        <p key={reason} className="mt-1 text-xs leading-snug text-muted-foreground">
          {reason}
        </p>
      ))}
    </button>
  );
}

export default function PipelinePanel({
  activeCase,
  streamingEvents,
  onSelectBlock,
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
      <div className="border-b border-border p-4">
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

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {isWorking && shortlist.length === 0 && (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/60 p-3">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <p className="text-xs text-muted-foreground">Finding the best matching listings...</p>
          </div>
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
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
