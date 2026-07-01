import { useEffect, useRef, useState } from "react";
import { ChevronDown, Loader2, LogIn, Plus, Send, Sparkles } from "lucide-react";
import type { AgentEvent, HomeOSCase, HomeOSCaseSummary } from "../types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  type?: "profile" | "search" | "question" | "result" | "chat";
  field?: string;
}

function buildChatHistory(
  profileText: string,
  pipeline: AgentEvent[],
  conversation: { role: string; content: string }[],
  streamingEvents: AgentEvent[],
  chatChunks: string,
): ChatMessage[] {
  const messages: ChatMessage[] = [];

  // Initial profile as first user message
  messages.push({ role: "user", content: profileText, type: "profile" });

  // Use pipeline (committed history) + streaming (in-flight), but don't double-count:
  // streamingEvents are cleared and moved into pipeline when the stream completes.
  const allEvents = (pipeline.length > 0 ? pipeline : streamingEvents).filter(
    (event) =>
      event.event === "clarifying_question" ||
      event.event === "case_done" ||
      (event.event === "agent_summary" && event.agent === "search"),
  );

  // Walk conversation messages in order, inserting each user answer right after its question.
  let convIdx = 0;

  for (const e of allEvents) {
    if (e.event === "agent_summary" && e.agent === "search" && e.data) {
      const data = e.data as Record<string, unknown>;
      const count = data["candidates_found"] as number;
      const query = data["search_query"] as Record<string, unknown> | undefined;
      const queryLines = query
        ? Object.entries(query)
            .filter(([, v]) => v !== null && v !== undefined)
            .map(([k, v]) => `${k}: ${v}`)
            .join(" · ")
        : null;
      messages.push({
        role: "assistant",
        content: queryLines
          ? `I searched and found **${count}** matching properties.\n\`${queryLines}\``
          : `I searched and found **${count}** matching properties.`,
        type: "search",
      });
    } else if (e.event === "clarifying_question" && e.question) {
      messages.push({ role: "assistant", content: e.question, type: "question", field: e.field });
      // Interleave the user's answer immediately after the question
      if (convIdx < conversation.length && conversation[convIdx].role === "user") {
        messages.push({ role: "user", content: conversation[convIdx].content, type: "chat" });
        convIdx++;
      }
    } else if (e.event === "case_done" && e.shortlist) {
      if (e.shortlist.length === 0) {
        messages.push({
          role: "assistant",
          content: "No properties meet specified requirements. Please try with less strict requirements.",
          type: "result",
        });
        continue;
      }
      const worth = e.shortlist.filter((r) => r.worth_viewing_score >= 60).length;
      messages.push({
        role: "assistant",
        content:
          worth > 0
            ? `Analysis complete — **${worth} of ${e.shortlist.length}** properties are worth viewing. See the pipeline panel for details.`
            : `Analysis complete — **${e.shortlist.length}** properties analysed. See the pipeline panel for the ranked shortlist.`,
        type: "result",
      });
    }
  }

  // Remaining conversation (post-analysis chat back-and-forth)
  while (convIdx < conversation.length) {
    const m = conversation[convIdx++];
    messages.push({ role: m.role as "user" | "assistant", content: m.content, type: "chat" });
  }

  // Streaming chat chunk (post-analysis chat only)
  if (chatChunks) {
    messages.push({ role: "assistant", content: chatChunks, type: "chat" });
  }

  return messages;
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  const isQuestion = msg.type === "question";

  // Split on newline before a backtick block to render query line separately
  const [mainText, queryLine] = msg.content.includes("\n`")
    ? msg.content.split("\n`")
    : [msg.content, null];

  const html = mainText.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-snug ${
          isUser
            ? "bg-primary text-primary-foreground rounded-tr-sm"
            : isQuestion
              ? "bg-amber-50 border border-amber-200 text-amber-900 rounded-tl-sm"
              : "bg-muted text-foreground rounded-tl-sm"
        }`}
      >
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: controlled bold markup */}
        <span dangerouslySetInnerHTML={{ __html: html }} />
        {queryLine && (
          <div className="mt-1.5 rounded bg-black/10 px-1.5 py-0.5 font-mono text-[10px] leading-relaxed opacity-70">
            {queryLine.replace(/`$/, "")}
          </div>
        )}
      </div>
    </div>
  );
}

interface Props {
  cases: HomeOSCaseSummary[];
  activeCaseId: string | null;
  activeCase: HomeOSCase | null;
  streamingEvents: AgentEvent[];
  chatChunks: string;
  isStreaming: boolean;
  isAuthenticated: boolean;
  isSubscribed: boolean;
  onNewCase: (profileText: string) => void;
  onSelectCase: (caseId: string) => void;
  onSendMessage: (message: string) => void;
  onRefine: (message: string) => void;
  onSignInRequired: () => void;
  onUpgradeRequired: () => void;
}

const CHIP_OPTIONS: Record<string, { label: string; value: string }[]> = {
  commute_priority: [
    { label: "High (<600 m)", value: "high" },
    { label: "Medium (<1.2 km)", value: "medium" },
    { label: "Not important", value: "not important" },
  ],
  school_priority: [
    { label: "2+ schools", value: "high" },
    { label: "1+ school", value: "medium" },
    { label: "Not needed", value: "not important" },
  ],
  risk_tolerance: [
    { label: "Low risk", value: "low" },
    { label: "Medium", value: "medium" },
    { label: "High risk ok", value: "high" },
  ],
  bus_reliance: [
    { label: "Yes, no car", value: "high" },
    { label: "Have a car", value: "low" },
  ],
  flat_type: [
    { label: "2-room", value: "2 room" },
    { label: "3-room", value: "3 room" },
    { label: "4-room", value: "4 room" },
    { label: "5-room", value: "5 room" },
    { label: "Executive", value: "executive" },
  ],
  max_price: [
    { label: "$600k", value: "$600k" },
    { label: "$800k", value: "$800k" },
    { label: "$1M", value: "$1M" },
  ],
  town: [
    { label: "Tampines", value: "Tampines" },
    { label: "Bishan", value: "Bishan" },
    { label: "Queenstown", value: "Queenstown" },
    { label: "Toa Payoh", value: "Toa Payoh" },
  ],
  work_locations: [
    { label: "CBD", value: "work in CBD" },
    { label: "Raffles Place", value: "work at Raffles Place" },
    { label: "Jurong East", value: "work at Jurong East" },
  ],
  open_ended: [
    { label: "Proceed as-is", value: "proceed" },
    { label: "Need cheaper", value: "max budget $700k" },
    { label: "Near MRT", value: "near MRT" },
  ],
  ready_to_proceed: [
    { label: "Proceed with analysis", value: "proceed" },
  ],
  no_results: [
    { label: "Any town", value: "any town" },
    { label: "Any flat type", value: "any flat" },
    { label: "Remove budget", value: "no budget" },
    { label: "Try $900k", value: "max budget $900k" },
  ],
};

const DEFAULT_PROFILE =
  "Family looking for 4 room under 800k near primary schools and MRT.";

export default function CasesPanel({
  cases,
  activeCaseId,
  activeCase,
  streamingEvents,
  chatChunks,
  isStreaming,
  isAuthenticated,
  isSubscribed,
  onNewCase,
  onSelectCase,
  onSendMessage,
  onRefine,
  onSignInRequired,
  onUpgradeRequired,
}: Props) {
  const [input, setInput] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const activeStatus =
    activeCase?.status ??
    cases.find((c) => c.case_id === activeCaseId)?.status ??
    null;

  const isRefining = activeStatus === "refining";
  const isRunning = activeStatus === "running" || isStreaming;
  const isDeepAnalysis = isRunning && streamingEvents.some((e) => e.block_id != null);
  const isDone = activeStatus === "done";

  const profileText =
    activeCase?.profile_text ??
    cases.find((c) => c.case_id === activeCaseId)?.profile_text ??
    "";

  const chatHistory =
    profileText
      ? buildChatHistory(
          profileText,
          activeCase?.pipeline ?? [],
          activeCase?.conversation ?? [],
          streamingEvents,
          chatChunks,
        )
      : [];

  const lastQuestion = isRefining
    ? [...chatHistory].reverse().find((m) => m.type === "question")
    : null;
  const activeChips = lastQuestion?.field ? (CHIP_OPTIONS[lastQuestion.field] ?? null) : null;

  // Auto-scroll to bottom
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [chatHistory.length, chatChunks]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");

    if (!activeCaseId || activeCaseId.startsWith("pending-")) {
      // Start a new investigation using the input as profile
      onNewCase(text);
      return;
    }
    if (isRefining) {
      onRefine(text);
    } else if (isDone) {
      onSendMessage(text);
    }
  }

  const placeholder = isRunning
    ? "Agent is working…"
    : isRefining
      ? "Answer the question above…"
      : isDone
        ? "Ask HomeOS about this case…"
        : activeCaseId
          ? "Ask HomeOS about this case…"
          : "Describe your household, budget, commute, schools…";

  const activeSummary = cases.find((c) => c.case_id === activeCaseId);

  return (
    <div className="flex h-full flex-col">
      {/* Cases selector */}
      <div className="border-b border-border p-3 flex items-center gap-2">
        <div className="relative flex-1">
          <button
            type="button"
            onClick={() => setShowDropdown((v) => !v)}
            className="flex w-full items-center justify-between gap-2 rounded-md border border-border bg-background px-3 py-2 text-xs text-foreground hover:bg-muted"
          >
            <span className="truncate font-medium">
              {activeSummary
                ? activeSummary.profile_text.slice(0, 40) + (activeSummary.profile_text.length > 40 ? "…" : "")
                : "No active case"}
            </span>
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          </button>

          {showDropdown && cases.length > 0 && (
            <div className="absolute left-0 top-full z-50 mt-1 w-full rounded-md border border-border bg-popover shadow-md">
              {cases.map((c) => (
                <button
                  key={c.case_id}
                  type="button"
                  onClick={() => { onSelectCase(c.case_id); setShowDropdown(false); }}
                  className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted ${c.case_id === activeCaseId ? "bg-primary/5 font-semibold" : ""}`}
                >
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      c.status === "done" ? "bg-emerald-500" :
                      c.status === "error" ? "bg-red-500" :
                      c.status === "refining" ? "bg-amber-500" : "bg-blue-500"
                    }`}
                  />
                  <span className="truncate">{c.profile_text.slice(0, 50)}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          type="button"
          title="New case"
          onClick={() => {
            setShowDropdown(false);
            if (!isAuthenticated) {
              onSignInRequired();
              return;
            }
            if (!isSubscribed) {
              onUpgradeRequired();
              return;
            }
            onNewCase(DEFAULT_PROFILE);
          }}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-background hover:bg-muted text-muted-foreground"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Chat history */}
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {chatHistory.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center px-4">
            <p className="text-xs text-muted-foreground leading-relaxed">
              Start a new investigation by typing your requirements below, or select a previous case from the dropdown.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {chatHistory.map((msg, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: stable chat order
              <ChatBubble key={i} msg={msg} />
            ))}
            {activeChips && (
              <div className="flex flex-wrap gap-1.5 px-1 pb-1">
                {activeChips.map((chip) => (
                  <button
                    key={chip.value}
                    type="button"
                    onClick={() => { onRefine(chip.value); }}
                    className="rounded-full border border-border bg-background px-3 py-1 text-xs hover:bg-muted"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            )}
            {isRunning && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm bg-muted px-3 py-2">
                  <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">
                    HomeOS is working…{isDeepAnalysis && " (This may take a few minutes)"}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      {!isAuthenticated ? (
        <div className="border-t border-border p-3">
          <button
            type="button"
            onClick={onSignInRequired}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-dashed border-border bg-muted/50 px-3 py-3 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground hover:border-primary/40"
          >
            <LogIn className="h-3.5 w-3.5 shrink-0" />
            Sign in to use AI mode
          </button>
        </div>
      ) : !isSubscribed ? (
        <div className="border-t border-border p-3">
          <button
            type="button"
            onClick={onUpgradeRequired}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-dashed border-primary/40 bg-primary/5 px-3 py-3 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
          >
            <Sparkles className="h-3.5 w-3.5 shrink-0" />
            Upgrade to Pro to use AI mode
          </button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex items-end gap-2 border-t border-border p-3">
          <textarea
            rows={1}
            className="flex-1 resize-none overflow-hidden rounded-md border border-input bg-background px-3 py-2 text-sm leading-snug placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
            placeholder={placeholder}
            value={input}
            disabled={isRunning}
            onChange={(e) => {
              setInput(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${e.target.scrollHeight}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e as unknown as React.FormEvent);
              }
            }}
          />
          <button
            type="submit"
            aria-label="Send message"
            disabled={isRunning || !input.trim()}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      )}
    </div>
  );
}
