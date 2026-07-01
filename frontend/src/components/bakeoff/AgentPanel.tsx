import { useCallback, useState } from "react";
import { Sparkles, X } from "lucide-react";
import CasesPanel from "../CasesPanel";
import { chatInCase, investigateStream, refineStream } from "../../lib/api";
import { getStoredUser } from "../../lib/auth";
import { DEFAULT_MODEL } from "../../lib/modelPreference";
import type { AgentEvent, HomeOSAvatar, HomeOSCase, HomeOSCaseSummary } from "../../types";

interface Props {
  open: boolean;
  onClose: () => void;
  onRecommendations: (caseId: string, blockIds: number[]) => void;
  onSignInRequired: () => void;
  onUpgradeRequired: () => void;
}

export default function AgentPanel({
  open,
  onClose,
  onRecommendations,
  onSignInRequired,
  onUpgradeRequired,
}: Props) {
  const [cases, setCases] = useState<HomeOSCaseSummary[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [activeCaseFull, setActiveCaseFull] = useState<HomeOSCase | null>(null);
  const [streamingEvents, setStreamingEvents] = useState<AgentEvent[]>([]);
  const [chatChunks, setChatChunks] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const authUser = getStoredUser();

  const processStream = useCallback(async (
    gen: AsyncGenerator<AgentEvent>,
    caseId: string,
    profileText: string,
    createdAt: string,
    tempId: string,
  ) => {
    const accumulated: AgentEvent[] = [];
    let finalCaseId: string | null = null;
    let finalStatus: "done" | "refining" | "error" = "done";

    setIsStreaming(true);
    try {
      for await (const event of gen) {
        accumulated.push(event);
        setStreamingEvents([...accumulated]);

        if (event.event === "clarifying_question") {
          finalCaseId = event.case_id ?? caseId;
          finalStatus = "refining";
          setCases((prev) =>
            prev.map((c) =>
              c.case_id === tempId ? { ...c, case_id: finalCaseId!, status: "refining" } : c,
            ),
          );
        }

        if (event.event === "case_done") {
          finalCaseId = event.case_id ?? null;
          finalStatus = "done";
          const shortlist = event.shortlist ?? [];
          if (event.case_id && shortlist.length > 0) {
            onRecommendations(event.case_id, shortlist.map((row) => row.block_id));
          }
          setCases((prev) =>
            prev.map((c) =>
              c.case_id === tempId || c.case_id === caseId
                ? {
                    case_id: event.case_id!,
                    created_at: createdAt,
                    profile_text: profileText,
                    status: "done",
                    shortlist_count: shortlist.length,
                  }
                : c,
            ),
          );
        }

        if (event.event === "case_error") {
          finalStatus = "error";
          setCases((prev) =>
            prev.map((c) =>
              c.case_id === tempId || c.case_id === caseId
                ? { ...c, case_id: event.case_id ?? tempId, status: "error" }
                : c,
            ),
          );
        }
      }
    } finally {
      setIsStreaming(false);
    }

    const resolvedId = finalCaseId ?? caseId;
    const caseDone = accumulated.find((e) => e.event === "case_done");
    const profileSummary = accumulated.find(
      (e) => e.event === "agent_summary" && e.agent === "profile",
    );
    setActiveCaseId(resolvedId);
    setActiveCaseFull((prev) => ({
      case_id: resolvedId,
      created_at: createdAt,
      profile_text: profileText,
      avatar: (profileSummary?.data as unknown as HomeOSAvatar) ?? prev?.avatar ?? null,
      pipeline: [...(prev?.pipeline ?? []), ...accumulated],
      shortlist: caseDone?.shortlist ?? prev?.shortlist ?? [],
      conversation: prev?.conversation ?? [],
      status: finalStatus,
    }));
    setStreamingEvents([]);
  }, [onRecommendations]);

  const handleNewCase = useCallback(async (profileText: string) => {
    setStreamingEvents([]);
    setActiveCaseFull(null);

    const tempId = `pending-${Date.now()}`;
    const createdAt = new Date().toISOString();
    setCases((prev) => [
      { case_id: tempId, created_at: createdAt, profile_text: profileText, status: "running", shortlist_count: 0 },
      ...prev,
    ]);
    setActiveCaseId(tempId);

    await processStream(
      investigateStream(profileText, 5, DEFAULT_MODEL),
      tempId,
      profileText,
      createdAt,
      tempId,
    );
  }, [processStream]);

  const handleRefine = useCallback(async (message: string) => {
    if (!activeCaseId || activeCaseId.startsWith("pending-") || !activeCaseFull) return;

    setCases((prev) => prev.map((c) => c.case_id === activeCaseId ? { ...c, status: "running" } : c));
    setActiveCaseFull((prev) => prev ? {
      ...prev,
      status: "running",
      conversation: [...prev.conversation, { role: "user", content: message }],
    } : prev);

    await processStream(
      refineStream(activeCaseId, message, DEFAULT_MODEL),
      activeCaseId,
      activeCaseFull.profile_text,
      activeCaseFull.created_at,
      activeCaseId,
    );
  }, [activeCaseFull, activeCaseId, processStream]);

  const handleSendMessage = useCallback(async (message: string) => {
    if (!activeCaseId || activeCaseId.startsWith("pending-")) return;
    setChatChunks("");
    let full = "";
    for await (const chunk of chatInCase(activeCaseId, message, DEFAULT_MODEL)) {
      full += chunk;
      setChatChunks(full);
    }
    setActiveCaseFull((prev) =>
      prev
        ? {
            ...prev,
            conversation: [
              ...prev.conversation,
              { role: "user", content: message },
              { role: "assistant", content: full },
            ],
          }
        : prev,
    );
    setChatChunks("");
  }, [activeCaseId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[2600] flex items-center justify-center bg-black/40 p-3 sm:p-4" onClick={onClose}>
      <div className="bo-glass bo-spring-up flex h-[min(760px,92vh)] w-full max-w-[460px] flex-col overflow-hidden rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 border-b border-border bg-card/90 px-4 py-3">
          <div>
            <div className="mb-1 inline-flex items-center gap-2 rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-primary">
              <Sparkles className="h-3.5 w-3.5" /> HomeOS Agent
            </div>
            <h2 className="text-base font-bold">AI property search</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-muted" aria-label="Close agent">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <CasesPanel
            cases={cases}
            activeCaseId={activeCaseId}
            activeCase={activeCaseFull}
            streamingEvents={streamingEvents}
            chatChunks={chatChunks}
            isStreaming={isStreaming}
            isAuthenticated={!!authUser}
            isSubscribed={authUser?.is_subscribed ?? false}
            onNewCase={handleNewCase}
            onSelectCase={setActiveCaseId}
            onSendMessage={handleSendMessage}
            onRefine={handleRefine}
            onSignInRequired={onSignInRequired}
            onUpgradeRequired={onUpgradeRequired}
          />
        </div>
      </div>
    </div>
  );
}
