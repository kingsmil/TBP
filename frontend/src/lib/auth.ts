/** Auth helpers — token stored in localStorage */

const TOKEN_KEY = "hdb_token";
const USER_KEY  = "hdb_user";

export interface AuthUser {
  email: string;
  is_subscribed: boolean;
}

/**
 * Dev mode: mirrors the backend `AUTH_REQUIRED=false` bypass. When
 * `VITE_AUTH_REQUIRED=false`, the app treats the visitor as a fake subscribed
 * dev user so no login/subscription gating appears. Defaults to off so
 * production builds are unaffected.
 */
export function devAuthEnabled(): boolean {
  return String(import.meta.env.VITE_AUTH_REQUIRED ?? "true").trim().toLowerCase() === "false";
}

export const DEV_USER: AuthUser = { email: "dev@local", is_subscribed: true };

export function saveAuth(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return devAuthEnabled() ? DEV_USER : null;
  try { return JSON.parse(raw) as AuthUser; } catch { return devAuthEnabled() ? DEV_USER : null; }
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
