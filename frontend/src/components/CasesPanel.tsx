import { useState } from "react";
import { Loader2, Search, FolderOpen } from "lucide-react";
import type { HomeOSCaseSummary } from "../types";

const DEFAULT_PROFILE =
  "Family looking for 4 room under 800k near primary schools and MRT.";

interface Props {
  cases: HomeOSCaseSummary[];
  activeCaseId: string | null;
  onNewCase: (profileText: string) => void;
  onSelectCase: (caseId: string) => void;
}

export default function CasesPanel({
  cases,
  activeCaseId,
  onNewCase,
  onSelectCase,
}: Props) {
  const [profileText, setProfileText] = useState(DEFAULT_PROFILE);

  const statusClass = (status: HomeOSCaseSummary["status"]) =>
    status === "done"
      ? "bg-emerald-100 text-emerald-700"
      : status === "error"
        ? "bg-red-100 text-red-700"
        : "bg-amber-100 text-amber-700";

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-4">
        <div className="mb-3 flex items-center gap-2">
          <FolderOpen className="h-4 w-4 text-primary" />
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Cases
          </p>
        </div>
        <textarea
          className="min-h-24 w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm leading-snug placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder="Describe your household, budget, commute, schools, and risk tolerance."
          value={profileText}
          onChange={(e) => setProfileText(e.target.value)}
        />
        <button
          type="button"
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={profileText.trim().length < 10}
          onClick={() => onNewCase(profileText.trim())}
        >
          <Search className="h-4 w-4" />
          Investigate homes
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {cases.length === 0 ? (
          <p className="px-2 pt-6 text-center text-xs text-muted-foreground">
            No cases yet. Start an investigation above.
          </p>
        ) : (
          <div className="space-y-2">
            {cases.map((c) => {
              const active = c.case_id === activeCaseId;
              return (
                <button
                  key={c.case_id}
                  type="button"
                  data-active={active}
                  onClick={() => onSelectCase(c.case_id)}
                  className={`w-full rounded-md border p-3 text-left transition-colors ${
                    active
                      ? "border-primary bg-primary/5"
                      : "border-border bg-card hover:bg-muted"
                  }`}
                >
                  <p className="line-clamp-2 text-xs font-medium leading-snug text-foreground">
                    {c.profile_text}
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${statusClass(c.status)}`}
                    >
                      {c.status}
                    </span>
                    {c.status === "running" && (
                      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                    )}
                    <span className="text-[10px] text-muted-foreground">
                      {c.shortlist_count} listings
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
