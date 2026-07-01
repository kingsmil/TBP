// Central feature flags.
//
// AI_MODE_ENABLED gates the entire HomeOS AI experience (AI mode, the agent
// pipeline, login/subscription gating, and the upgrade flow). When off, the
// app ships as a pure manual "Explore" product and no AI surfaces are shown.
//
// Toggle via the build-time env var VITE_AI_MODE_ENABLED ("true"/"false").
// Defaults to ON because the app now has local/dev model fallbacks and the
// backend can run without a hosted AI key in local development.
export const AI_MODE_ENABLED =
  String(import.meta.env.VITE_AI_MODE_ENABLED ?? "true").toLowerCase() !== "false";
