/**
 * Toggle for the "Floating Glass" redesign (full-screen map shell).
 *
 * The redesign is now the DEFAULT. `?ui=off` returns to the classic app (and is
 * remembered); `?ui=on` forces the redesign. Anyone who previously chose classic
 * keeps it until they switch back.
 */
const KEY = "hdb_ui_redesign";

export function isRedesignEnabled(): boolean {
  const fromUrl = new URLSearchParams(window.location.search).get("ui");
  // "on" forces it; "a" is kept as an alias for the old bake-off URL.
  if (fromUrl === "on" || fromUrl === "a") {
    try { localStorage.setItem(KEY, "on"); } catch { /* ignore */ }
    return true;
  }
  if (fromUrl === "off") {
    try { localStorage.setItem(KEY, "off"); } catch { /* ignore */ }
    return false;
  }
  // Default ON — only stay classic if the user explicitly opted out.
  try { return localStorage.getItem(KEY) !== "off"; } catch { return true; }
}

export function setRedesign(on: boolean): void {
  try { localStorage.setItem(KEY, on ? "on" : "off"); } catch { /* ignore */ }
  const url = new URL(window.location.href);
  url.searchParams.set("ui", on ? "on" : "off");
  window.location.href = url.toString();
}
