import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Loader2, MapPin, Smile, TrendingUp } from "lucide-react";
import type { AgentKey, AgentProgressMap } from "../types";

const AGENT_CONFIG: { key: AgentKey; label: string; Icon: React.ElementType }[] = [
  { key: "market", label: "Market", Icon: TrendingUp },
  { key: "location", label: "Location", Icon: MapPin },
  { key: "lifestyle", label: "Lifestyle", Icon: Smile },
  { key: "risk", label: "Risk", Icon: AlertTriangle },
];

interface Props {
  agentProgress: AgentProgressMap;
  globalStatus: string | null;
}

export default function AgentProgressRows({ agentProgress, globalStatus }: Props) {
  const [expanded, setExpanded] = useState<Set<AgentKey>>(new Set());

  function toggle(key: AgentKey) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  return (
    <div className="space-y-1">
      {globalStatus && (
        <p className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          {globalStatus}
        </p>
      )}

      {AGENT_CONFIG.map(({ key, label, Icon }) => {
        const entry = agentProgress.get(key) ?? { status: "idle", blocksDone: 0, snippets: [] };
        const isExpanded = expanded.has(key);
        const hasSnippets = entry.snippets.length > 0;

        return (
          <div key={key} className="rounded-lg border border-border bg-muted/40">
            <button
              type="button"
              onClick={() => toggle(key)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left"
            >
              {hasSnippets ? (
                isExpanded ? (
                  <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                )
              ) : (
                <span className="h-3 w-3 shrink-0" />
              )}
              <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="text-xs font-medium text-foreground">{label}</span>
              {entry.status === "running" && (
                <Loader2 className="ml-1 h-3 w-3 animate-spin text-primary" />
              )}
              {entry.blocksDone > 0 && (
                <span className="ml-auto text-xs text-muted-foreground">
                  {entry.blocksDone} {entry.blocksDone === 1 ? "block" : "blocks"}
                </span>
              )}
            </button>

            {isExpanded && hasSnippets && (
              <div className="space-y-1 border-t border-border px-3 pb-2 pt-1">
                {entry.snippets.map(({ block_id, narrative }) => (
                  <p key={block_id} className="text-xs text-muted-foreground">
                    <span className="font-medium">Block {block_id}</span> — {narrative}
                  </p>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
