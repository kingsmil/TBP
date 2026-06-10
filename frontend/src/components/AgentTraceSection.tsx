import { useState } from "react";
import type { AgentTrace, AgentSource, TraceToolCall } from "../types";

const LABELS: Record<AgentSource, string> = {
  market: "Market",
  location: "Lifestyle",
  risk: "Risk",
};

function summarize(result: unknown): string {
  if (result == null) return "—";
  if (Array.isArray(result)) return `${result.length} items`;
  if (typeof result === "object") {
    const keys = Object.keys(result as Record<string, unknown>);
    return keys.slice(0, 3).join(", ") || "{}";
  }
  return String(result);
}

function ToolCallRow({ call }: { call: TraceToolCall }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-border/50 py-1">
      <p className="text-xs font-medium text-foreground">{call.tool_name}</p>
      <p className="text-[10px] text-muted-foreground break-all">
        args: {JSON.stringify(call.args)}
      </p>
      <button
        type="button"
        className="text-[10px] text-sky-700 hover:underline"
        onClick={() => setOpen((v) => !v)}
      >
        result: {summarize(call.result)} {open ? "▲" : "⤢"}
      </button>
      {open && (
        <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted p-1 text-[10px] text-muted-foreground">
          {JSON.stringify(call.result, null, 2)}
        </pre>
      )}
    </div>
  );
}

function AgentTraceRow({ trace }: { trace: AgentTrace }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded border border-border">
      <button
        type="button"
        className="flex w-full items-center justify-between px-2 py-1 text-xs"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-medium text-foreground">
          {open ? "▾" : "▸"} {LABELS[trace.agent]}
        </span>
        <span className="text-[10px] text-muted-foreground">
          {trace.tool_calls.length} tools
        </span>
      </button>
      {open && (
        <div className="px-2 pb-2">
          {trace.tool_calls.map((c, i) => (
            <ToolCallRow key={`${c.tool_name}-${i}`} call={c} />
          ))}
          {trace.narrative && (
            <p className="mt-1 text-[10px] italic text-muted-foreground">
              {trace.narrative}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function AgentTraceSection({ trace }: { trace?: AgentTrace[] }) {
  const withCalls = (trace ?? []).filter((t) => t.tool_calls.length > 0);
  if (withCalls.length === 0) return null;
  return (
    <div className="p-4 border-b border-border space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Agent trace
      </p>
      {withCalls.map((t) => (
        <AgentTraceRow key={t.agent} trace={t} />
      ))}
    </div>
  );
}
