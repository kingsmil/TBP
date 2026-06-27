import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import InfoPanel from "../InfoPanel";
import EstateComparison from "../EstateComparison";
import { getEstateComparison } from "../../lib/api";

/** Insights: appreciation "Top areas" (InfoPanel) + estate comparison, in tabs. */
export default function InsightsModal({ onSelectBlock, onClose }: {
  onSelectBlock: (id: number) => void; onClose: () => void;
}) {
  const [tab, setTab] = useState<"areas" | "compare">("areas");
  const cmp = useQuery({
    queryKey: ["bo-estate-cmp"], queryFn: () => getEstateComparison(), enabled: tab === "compare", staleTime: 6e5,
  });

  return (
    <div className="fixed inset-0 z-[2400] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bo-glass flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <div className="inline-flex rounded-full border border-border bg-muted/50 p-1 text-xs font-semibold">
            {([["areas", "Top areas"], ["compare", "Estate comparison"]] as const).map(([k, label]) => (
              <button key={k} type="button" onClick={() => setTab(k)}
                className={`rounded-full px-3 py-1 ${tab === k ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>
                {label}
              </button>
            ))}
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {tab === "areas" ? (
            <InfoPanel onSelectBlock={(id) => { onSelectBlock(id); onClose(); }} />
          ) : (
            <div className="p-4">
              {cmp.isLoading && <p className="p-6 text-center text-sm text-muted-foreground">Loading…</p>}
              {cmp.data && <EstateComparison rows={cmp.data.estates} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
