import { useQuery } from "@tanstack/react-query";
import { getNews } from "@/lib/api";
import type { NewsItem } from "../types";
import exaLogo from "@/assets/exa-logo.png";

function formatDate(raw: string | null): string {
  if (!raw) return "";
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-SG", { day: "2-digit", month: "short", year: "numeric" });
}

function PoweredByExa() {
  return (
    <a
      href="https://exa.ai"
      target="_blank"
      rel="noreferrer"
      className="flex shrink-0 items-center justify-center gap-1.5 border-t border-border bg-background px-4 py-2 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
    >
      <span>Powered by</span>
      <img src={exaLogo} alt="Exa" className="h-3.5 w-3.5 rounded-[3px]" />
      <span className="font-semibold tracking-tight">Exa</span>
    </a>
  );
}

export default function NewsPanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["news"],
    queryFn: getNews,
    staleTime: Infinity,
  });

  if (isLoading) {
    return (
      <div className="px-5 py-4 text-sm text-muted-foreground">Loading…</div>
    );
  }
  if (isError) {
    return (
      <div className="px-5 py-4 text-sm text-destructive">
        Failed to load news — try again later
      </div>
    );
  }
  if (!data?.length) {
    return (
      <div className="px-5 py-4 text-sm text-muted-foreground">No news found</div>
    );
  }

  return (
    <div className="flex flex-1 flex-col min-h-0">
      <ul className="flex-1 divide-y divide-border overflow-y-auto">
        {data.map((item: NewsItem) => (
          <li key={item.url} className="px-4 py-3">
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className="block text-sm font-medium text-foreground hover:text-primary leading-snug"
            >
              {item.title}
            </a>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {[item.domain, formatDate(item.published_date)].filter(Boolean).join(" · ")}
            </p>
          </li>
        ))}
      </ul>
      <PoweredByExa />
    </div>
  );
}
