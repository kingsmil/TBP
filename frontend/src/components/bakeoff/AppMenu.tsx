import { useEffect, useRef, useState } from "react";
import { Menu, User, LogOut, MapPin, Heart, BarChart3, Building2, Wand2, Moon, Sun, Undo2 } from "lucide-react";
import { setRedesign } from "../../lib/uiVariant";
import type { ShellProps } from "./shell";

/** One tidy menu for the secondary features — keeps the map chrome minimal. */
export default function AppMenu(p: ShellProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const item = (icon: React.ReactNode, label: string, onClick: () => void) => (
    <button type="button" onClick={() => { setOpen(false); onClick(); }}
      className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-muted">
      {icon} {label}
    </button>
  );

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)}
        title="Menu"
        className="bo-glass flex h-11 items-center gap-2 rounded-full px-3.5 text-sm font-semibold">
        <Menu className="h-4 w-4" />
        <span className="hidden max-w-[110px] truncate sm:inline">{p.authEmail ?? "Menu"}</span>
      </button>
      {open && (
        <div className="bo-glass absolute right-0 top-12 z-[1300] w-56 rounded-2xl p-2">
          {item(p.authEmail ? <LogOut className="h-4 w-4" /> : <User className="h-4 w-4" />,
            p.authEmail ? "Sign out" : "Sign in", p.onAccount)}
          {item(<Heart className="h-4 w-4" />, "Saved homes", p.onSavedHomes)}
          {item(<MapPin className="h-4 w-4" />, "My places", p.onSaved)}
          {item(<BarChart3 className="h-4 w-4" />, "Insights", p.onInsights)}
          {item(<Building2 className="h-4 w-4" />, "BTO data", p.onBtoData)}
          {item(<Wand2 className="h-4 w-4" />, "Help me decide", p.onHelp)}
          {item(p.theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />,
            p.theme === "light" ? "Dark mode" : "Light mode", p.onToggleTheme)}
          <div className="my-1 border-t border-border/60" />
          {item(<Undo2 className="h-4 w-4" />, "Classic app", () => setRedesign(false))}
        </div>
      )}
    </div>
  );
}
