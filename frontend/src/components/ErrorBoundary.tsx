import React from "react";

interface State { hasError: boolean }

/** Top-level safety net: a thrown render error shows a friendly reload screen
 *  instead of a blank white page. */
export default class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State { return { hasError: true }; }

  componentDidCatch(error: unknown, info: unknown) {
    // eslint-disable-next-line no-console
    console.error("App crashed:", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div style={{
        minHeight: "100vh", display: "flex", flexDirection: "column", gap: 14,
        alignItems: "center", justifyContent: "center", padding: 24, textAlign: "center",
        fontFamily: "system-ui, sans-serif", background: "#f4f6f8", color: "#1f2937",
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: 12, background: "#2563eb",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontWeight: 800, fontSize: 22,
        }}>H</div>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Something went wrong</h1>
        <p style={{ fontSize: 14, color: "#6b7280", margin: 0, maxWidth: 320 }}>
          The app hit an unexpected error. Reloading usually fixes it.
        </p>
        <button type="button" onClick={() => window.location.reload()} style={{
          marginTop: 4, padding: "9px 18px", borderRadius: 9999, border: "none",
          background: "#2563eb", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer",
        }}>Reload</button>
      </div>
    );
  }
}
