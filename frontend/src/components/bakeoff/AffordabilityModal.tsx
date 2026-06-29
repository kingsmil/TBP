import { useEffect, useMemo, useState } from "react";
import { X, Wallet, Info } from "lucide-react";
import { affordability, type LoanType } from "../../lib/affordability";

const sgd0 = (n: number) => `$${Math.round(n).toLocaleString()}`;

function Field({ label, value, onChange, prefix, suffix }: {
  label: string; value: number; onChange: (n: number) => void; prefix?: string; suffix?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="flex items-center gap-1.5 rounded-xl border border-border bg-card px-3">
        {prefix && <span className="text-sm text-muted-foreground">{prefix}</span>}
        <input type="number" inputMode="numeric" value={value || ""}
          onChange={(e) => onChange(Number(e.target.value) || 0)}
          className="h-10 w-full bg-transparent text-sm outline-none" />
        {suffix && <span className="text-xs text-muted-foreground">{suffix}</span>}
      </span>
    </label>
  );
}

export default function AffordabilityModal({ onClose }: { onClose: () => void }) {
  const [income, setIncome] = useState(7000);
  const [savings, setSavings] = useState(150000);
  const [debt, setDebt] = useState(0);
  const [age, setAge] = useState(30);
  const [loan, setLoan] = useState<LoanType>("hdb");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const r = useMemo(
    () => affordability({ monthlyIncome: income, savings, monthlyDebt: debt, age, loan }),
    [income, savings, debt, age, loan],
  );

  return (
    <div className="fixed inset-0 z-[2400] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bo-glass flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <div className="flex items-center gap-2">
            <Wallet className="h-4 w-4 text-primary" />
            <h2 className="text-base font-bold">What can I afford?</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
          {/* Loan type */}
          <div className="grid grid-cols-2 gap-2">
            {(["hdb", "bank"] as LoanType[]).map((t) => (
              <button key={t} type="button" onClick={() => setLoan(t)}
                className={`rounded-xl border p-2.5 text-left text-sm font-semibold transition-colors ${loan === t ? "border-primary bg-primary/10" : "border-border hover:bg-muted"}`}>
                {t === "hdb" ? "HDB loan" : "Bank loan"}
                <span className="block text-[11px] font-normal text-muted-foreground">{t === "hdb" ? "2.6% · up to 80%" : "~4% · up to 75%"}</span>
              </button>
            ))}
          </div>

          {/* Inputs */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Monthly household income" value={income} onChange={setIncome} prefix="$" />
            <Field label="Cash + CPF savings" value={savings} onChange={setSavings} prefix="$" />
            <Field label="Other monthly debt" value={debt} onChange={setDebt} prefix="$" />
            <Field label="Your age" value={age} onChange={setAge} suffix="yrs" />
          </div>

          {/* Headline */}
          <div className="rounded-2xl bg-primary/10 p-4 text-center">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">You could afford up to</div>
            <div className="text-3xl font-bold text-primary">{sgd0(r.maxPrice)}</div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              limited by your {r.limitedBy === "savings" ? "savings / downpayment" : "income"} · {r.tenureYears}-year loan
            </div>
          </div>

          {/* Breakdown */}
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Max loan" value={sgd0(r.maxLoan)} />
            <Stat label="Downpayment needed" value={sgd0(r.downpayment)} />
            <Stat label="Monthly instalment" value={`${sgd0(r.monthlyInstalment)}/mo`} />
            <Stat label="Est. EHG grant" value={r.ehgGrant > 0 ? sgd0(r.ehgGrant) : "—"} />
          </div>

          <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/30 p-3 text-[11px] text-muted-foreground">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p>
              Rough estimate, not financial advice. Uses MSR/TDSR, LTV and a {loan === "hdb" ? "2.6%" : "4% stress"} rate.
              You may also qualify for the CPF Housing Grant and Proximity Housing Grant — check HDB for exact figures.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card/60 p-2.5">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="text-sm font-bold tabular-nums">{value}</div>
    </div>
  );
}
