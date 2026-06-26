/**
 * UI bake-off switch. Three redesign shells (A/B/C) are mounted when `?ui=a|b|c`
 * is present (or persisted). This is a temporary evaluation harness — once a
 * direction is chosen, delete src/components/bakeoff/, this file, and the guard
 * in App.tsx. Nothing else depends on it.
 */
export type UiVariant = "a" | "b" | "c";

const KEY = "hdb_ui_variant";
const VALID: UiVariant[] = ["a", "b", "c"];

export function getUiVariant(): UiVariant | null {
  const fromUrl = new URLSearchParams(window.location.search).get("ui");
  if (fromUrl === "off") {
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
    return null;
  }
  if (fromUrl && VALID.includes(fromUrl as UiVariant)) {
    try { localStorage.setItem(KEY, fromUrl); } catch { /* ignore */ }
    return fromUrl as UiVariant;
  }
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && VALID.includes(saved as UiVariant)) return saved as UiVariant;
  } catch { /* ignore */ }
  return null;
}

export function setUiVariant(v: UiVariant | null): void {
  try {
    if (v) localStorage.setItem(KEY, v);
    else localStorage.removeItem(KEY);
  } catch { /* ignore */ }
  const url = new URL(window.location.href);
  if (v) url.searchParams.set("ui", v);
  else url.searchParams.set("ui", "off");
  window.location.href = url.toString();
}

export const VARIANT_META: Record<UiVariant, { name: string; tagline: string }> = {
  a: { name: "Floating Glass", tagline: "Map canvas · frosted panels float on top" },
  b: { name: "Minimal Command", tagline: "Bare map · one command bar, collapses away" },
  c: { name: "Immersive Explorer", tagline: "Map + price pins · Airbnb-style sheet/panel" },
};
