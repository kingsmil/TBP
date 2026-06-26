import { useState } from "react";
import { Building2, KeyRound, Scale, Wand2, Landmark } from "lucide-react";
import BtoResaleCompare from "./BtoResaleCompare";
import RecommendWizard from "./RecommendWizard";

interface Props {
  onSelect: (product: "resale" | "bto" | "private") => void;
}

const COMPARE: { label: string; bto: string; resale: string }[] = [
  { label: "What it is", bto: "Brand-new flat from HDB", resale: "Existing flat from the open market" },
  { label: "Wait time", bto: "~3–4 years (or shorter for some)", resale: "Move in within months" },
  { label: "Price", bto: "Lower, subsidised", resale: "Higher, market price" },
  { label: "Choice", bto: "Limited launches & locations", resale: "Any town, any block" },
  { label: "Ballot", bto: "Subject to application/ballot", resale: "No ballot — buy directly" },
];

export default function ProductChooser({ onSelect }: Props) {
  const [helpMode, setHelpMode] = useState<"" | "compare" | "recommend">("");

  return (
    <div className="flex h-full items-center justify-center bg-background p-6">
      <div className="w-full max-w-3xl">
        <div className="mb-1 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">H</div>
          <span className="text-sm font-bold">HDB Match</span>
        </div>
        <h1 className="text-2xl font-bold">What kind of flat are you after?</h1>
        <p className="mt-1 text-sm text-muted-foreground">Pick a path — you can switch any time.</p>

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <button
            type="button"
            onClick={() => onSelect("bto")}
            className="group flex flex-col items-start gap-2 rounded-2xl border border-border bg-card p-5 text-left transition-colors hover:border-primary hover:bg-muted"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Building2 className="h-5 w-5" /></span>
            <span className="text-base font-semibold">New flat (BTO)</span>
            <span className="text-xs text-muted-foreground">Explore sales-exercise trends and how competitive each launch is by estate &amp; flat type.</span>
          </button>

          <button
            type="button"
            onClick={() => onSelect("resale")}
            className="group flex flex-col items-start gap-2 rounded-2xl border border-border bg-card p-5 text-left transition-colors hover:border-primary hover:bg-muted"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><KeyRound className="h-5 w-5" /></span>
            <span className="text-base font-semibold">Resale flat</span>
            <span className="text-xs text-muted-foreground">Search the market on a map, score blocks by what matters to you, and see appreciation trends.</span>
          </button>

          <button
            type="button"
            onClick={() => onSelect("private")}
            className="group flex flex-col items-start gap-2 rounded-2xl border border-border bg-card p-5 text-left transition-colors hover:border-primary hover:bg-muted"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Landmark className="h-5 w-5" /></span>
            <span className="text-base font-semibold">Private property</span>
            <span className="text-xs text-muted-foreground">Condos, apartments, ECs &amp; landed — browse URA transactions, PSF trends and prices by project or district.</span>
          </button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setHelpMode((m) => (m === "recommend" ? "" : "recommend"))}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
              helpMode === "recommend" ? "bg-primary text-primary-foreground" : "border border-border hover:bg-muted"
            }`}
          >
            <Wand2 className="h-4 w-4" /> Help me decide
          </button>
          <button
            type="button"
            onClick={() => setHelpMode((m) => (m === "compare" ? "" : "compare"))}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
              helpMode === "compare" ? "bg-primary text-primary-foreground" : "border border-border hover:bg-muted"
            }`}
          >
            <Scale className="h-4 w-4" /> Compare the numbers
          </button>
        </div>

        {helpMode === "recommend" && (
          <div className="mt-4">
            <h2 className="text-base font-semibold">Answer a few questions</h2>
            <p className="mb-3 text-xs text-muted-foreground">We'll suggest BTO or resale based on what matters to you.</p>
            <RecommendWizard onSelect={onSelect} />
          </div>
        )}

        {helpMode === "compare" && (
          <div className="mt-4 space-y-5">
            <div className="overflow-hidden rounded-xl border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 text-left">
                    <th className="px-4 py-2 font-medium text-muted-foreground"></th>
                    <th className="px-4 py-2 font-semibold">BTO</th>
                    <th className="px-4 py-2 font-semibold">Resale</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARE.map((row) => (
                    <tr key={row.label} className="border-t border-border">
                      <td className="px-4 py-2 font-medium text-muted-foreground">{row.label}</td>
                      <td className="px-4 py-2">{row.bto}</td>
                      <td className="px-4 py-2">{row.resale}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h2 className="text-base font-semibold">See the real numbers</h2>
              <p className="mb-3 text-xs text-muted-foreground">Pick a town &amp; flat type to compare actual BTO and resale prices.</p>
              <BtoResaleCompare onSelect={onSelect} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
