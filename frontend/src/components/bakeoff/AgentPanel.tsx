import { Sparkles, X, Send } from "lucide-react";

/** Placeholder for the AI Agent (the old "AI mode" / HomeOS). Not wired up yet —
 *  shows what it will do. */
export default function AgentPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[2600] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bo-glass bo-spring-up w-full max-w-md overflow-hidden rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="relative bg-gradient-to-br from-primary/25 via-primary/10 to-transparent p-5">
          <button type="button" onClick={onClose} className="absolute right-3 top-3 rounded-md p-1 hover:bg-card/60"><X className="h-4 w-4" /></button>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-card/80 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-primary">
            <Sparkles className="h-3.5 w-3.5" /> Coming soon
          </div>
          <h2 className="text-lg font-bold">AI Agent</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Describe what you're after in plain English — budget, commute, family, lifestyle —
            and the agent shortlists and explains the best-fit homes for you.
          </p>
        </div>

        <div className="space-y-3 p-5">
          <div className="flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground">
            <span className="flex-1 truncate">e.g. “4-room under $600k, ≤30 min to Raffles Place, near a good primary school”</span>
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/40 text-primary-foreground"><Send className="h-4 w-4" /></span>
          </div>
          <ul className="space-y-1.5 text-xs text-muted-foreground">
            <li>• Natural-language search across BTO, resale &amp; private</li>
            <li>• Commute &amp; lifestyle scoring from your saved places</li>
            <li>• A ranked shortlist with the reasoning for each pick</li>
          </ul>
          <button type="button" disabled
            className="w-full cursor-not-allowed rounded-xl bg-primary/50 py-2.5 text-sm font-semibold text-primary-foreground">
            Not available yet
          </button>
        </div>
      </div>
    </div>
  );
}
