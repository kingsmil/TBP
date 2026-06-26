import { useEffect, useState } from "react";

/** Animated 0–100 match bar. Grows on mount; respects reduced-motion. */
export default function ScoreBar({ score, gradient = false }: { score: number; gradient?: boolean }) {
  const [w, setW] = useState(0);
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setW(score); return; }
    const id = requestAnimationFrame(() => setW(score));
    return () => cancelAnimationFrame(id);
  }, [score]);

  const tone =
    score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-amber-500" : "bg-rose-400";
  const fill = gradient
    ? "bg-gradient-to-r from-primary/70 to-primary"
    : tone;

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full ${fill} transition-[width] duration-700 ease-out`}
          style={{ width: `${w}%` }}
        />
      </div>
      <span className="w-7 shrink-0 text-right text-xs font-semibold tabular-nums text-muted-foreground">
        {score}
      </span>
    </div>
  );
}
