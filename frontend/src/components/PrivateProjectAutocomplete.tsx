import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, Search, X } from "lucide-react";
import { getPrivateProjects } from "../lib/api";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(timer);
  }, [value, ms]);

  return debounced;
}

interface Props {
  label?: string;
  value?: string;
  placeholder?: string;
  compact?: boolean;
  onChange: (value: string | undefined) => void;
}

export default function PrivateProjectAutocomplete({
  label = "Project",
  value = "",
  placeholder = "e.g. The Continuum",
  compact,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const debounced = useDebounced(value.trim(), 250);

  const projects = useQuery({
    queryKey: ["private-projects", debounced],
    queryFn: () => getPrivateProjects(debounced),
    enabled: open && debounced.length >= 2,
    staleTime: 6e5,
  });
  const rows = projects.data?.results?.slice(0, 8) ?? [];

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pick = (projectName: string) => {
    onChange(projectName);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      {label && <div className={compact ? "mb-1 text-[10px] font-medium text-muted-foreground" : "mb-2 text-sm font-semibold"}>{label}</div>}
      <div className={`flex items-center gap-2 rounded-xl border border-border bg-card px-3 ${compact ? "h-8" : "h-10"}`}>
        <Search className={compact ? "h-3.5 w-3.5 shrink-0 text-muted-foreground" : "h-4 w-4 shrink-0 text-muted-foreground"} />
        <input
          type="text"
          value={value}
          placeholder={placeholder}
          autoComplete="off"
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            onChange(e.target.value || undefined);
            setOpen(true);
          }}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        {value && (
          <button type="button" title="Clear project" onClick={() => { onChange(undefined); setOpen(false); }}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-muted">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {open && debounced.length >= 2 && (projects.isFetching || rows.length > 0) && (
        <div className="absolute inset-x-0 top-full z-[2100] mt-1.5 max-h-72 overflow-y-auto rounded-xl border border-border bg-popover p-1.5 shadow-lg">
          {projects.isFetching && rows.length === 0 && (
            <div className="px-2.5 py-2 text-xs text-muted-foreground">Searching projects...</div>
          )}
          {rows.map((row) => (
            <button
              key={row.project_name}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(row.project_name)}
              className="flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left hover:bg-muted"
            >
              <Building2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-semibold">{row.project_name}</span>
                <span className="block truncate text-[11px] text-muted-foreground">
                  {row.property_type} - D{row.district ?? "--"} {row.planning_region ?? ""} - {row.count.toLocaleString()} txns
                  {row.median_psf != null ? ` - $${row.median_psf.toLocaleString()} psf median` : ""}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
