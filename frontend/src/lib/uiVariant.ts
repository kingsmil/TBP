/**
 * Toggle for the in-progress "Floating Glass" redesign (full-screen map shell).
 * Opt-in while it's built out so the existing app keeps working: `?ui=on`
 * enables it (persisted), `?ui=off` returns to the classic app.
 *
 * Once the redesign reaches parity it becomes the default and this flag + the
 * old App branches can be removed.
 */
const KEY = "hdb_ui_redesign";

export function isRedesignEnabled(): boolean {
  const fromUrl = new URLSearchParams(window.location.search).get("ui");
  // "on" enables it; "a" is kept as an alias for the old bake-off URL.
  if (fromUrl === "on" || fromUrl === "a") {
    try { localStorage.setItem(KEY, "on"); } catch { /* ignore */ }
    return true;
  }
  if (fromUrl === "off") {
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
    return false;
  }
  try { return localStorage.getItem(KEY) === "on"; } catch { return false; }
}

export function setRedesign(on: boolean): void {
  try {
    if (on) localStorage.setItem(KEY, "on");
    else localStorage.removeItem(KEY);
  } catch { /* ignore */ }
  const url = new URL(window.location.href);
  url.searchParams.set("ui", on ? "on" : "off");
  window.location.href = url.toString();
}
