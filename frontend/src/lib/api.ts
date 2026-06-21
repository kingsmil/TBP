// Typed API client. Base URL is "/api" which the Vite dev server proxies to
// the FastAPI backend (see vite.config.ts).

import type {
  AccessibilityScores,
  BlockAgentsResponse,
  BlockListingsResponse,
  OutreachMessageResponse,
  AppreciationResult,
  CommuteHeatmapResponse,
  CommuteOptimizeResponse,
  ComparisonResponse,
  DestinationPayload,
  DirectTransitDestination,
  DirectTransitResponse,
  DreamHomeResponse,
  EstateAnalytics,
  ForecastResult,
  AgentEvent,
  HomeOSCase,
  HomeOSCaseSummary,
  HomeOSCaseFile,
  HomeOSInvestigationResponse,
  HomeOSScheduleViewingBody,
  HomeOSScheduleViewingResponse,
  LifestyleResult,
  NewsItem,
  RankingsResponse,
  RecommendationResponse,
  RegionRankingRow,
  BlockRankingRow,
  ScoreField,
  ScoreRankingResponse,
  SearchFilters,
  SearchResponse,
  UndervaluedResponse,
} from "../types";
import { buildSearchQuery } from "./format";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

import { authHeaders } from "./auth";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return (await res.json()) as T;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw Object.assign(new Error(detail?.detail ?? `API ${res.status}: ${path}`), { status: res.status });
  }
  return (await res.json()) as T;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface AuthResponse { token: string; email: string; is_subscribed: boolean; }

export function apiRegister(email: string, password: string): Promise<AuthResponse> {
  return postJSON<AuthResponse>("/auth/register", { email, password });
}
export function apiLogin(email: string, password: string): Promise<AuthResponse> {
  return postJSON<AuthResponse>("/auth/login", { email, password });
}
export function apiCreateCheckout(): Promise<{ url: string }> {
  return postJSON<{ url: string }>("/stripe/checkout", {});
}
export function apiSubscriptionStatus(): Promise<{ is_subscribed: boolean; email: string }> {
  return getJSON("/stripe/status");
}

export function searchProperties(filters: SearchFilters): Promise<SearchResponse> {
  const qs = buildSearchQuery(filters);
  return getJSON<SearchResponse>(`/properties/search${qs ? `?${qs}` : ""}`);
}

export function getEstateAnalytics(
  planningAreaId: number,
  flatType?: string,
): Promise<EstateAnalytics> {
  const qs = flatType ? `?flat_type=${encodeURIComponent(flatType)}` : "";
  return getJSON<EstateAnalytics>(`/analytics/estate/${planningAreaId}${qs}`);
}

export function getEstateAccessibility(
  planningAreaId: number,
): Promise<AccessibilityScores & { planning_area_id: number; block_count: number }> {
  return getJSON(`/accessibility/estate/${planningAreaId}`);
}

export function getEstateComparison(
  estateIds?: number[],
  flatType?: string,
): Promise<ComparisonResponse> {
  const params = new URLSearchParams();
  if (estateIds?.length) params.set("estates", estateIds.join(","));
  if (flatType) params.set("flat_type", flatType);
  const qs = params.toString();
  return getJSON<ComparisonResponse>(`/comparison/estates${qs ? `?${qs}` : ""}`);
}

export interface ReferenceFeatureCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    properties: Record<string, unknown>;
    geometry: { type: "Point"; coordinates: [number, number] };
  }[];
}

export function getReferenceLayer(layer: string): Promise<ReferenceFeatureCollection> {
  return getJSON<ReferenceFeatureCollection>(`/reference/${layer}`);
}

export interface BusReachStop {
  bus_stop_code: string;
  description: string;
  lat: number;
  lon: number;
  stop_sequence?: number;
}

export interface BusReachResponse {
  origin: BusReachStop;
  service_count: number;
  reachable_stop_count: number;
  services: {
    service_no: string;
    direction: number;
    stops: BusReachStop[];
  }[];
  reachable_stops: BusReachStop[];
}

export function getBusStopReach(busStopCode: string): Promise<BusReachResponse> {
  return getJSON<BusReachResponse>(`/bus-stops/${encodeURIComponent(busStopCode)}/reach`);
}

export interface GeocodeResult {
  label: string;
  lat: number;
  lon: number;
}

export function geocodeAddress(query: string): Promise<{ results: GeocodeResult[] }> {
  return getJSON(`/geocode?q=${encodeURIComponent(query)}`);
}

export function findDirectTransitHomes(body: {
  destinations: DirectTransitDestination[];
  max_walk_minutes: number;
  modes: ("bus" | "mrt")[];
  town?: string;
  planning_area_id?: number;
  flat_type?: string;
  min_price?: number;
  max_price?: number;
  min_psf?: number;
  max_psf?: number;
  max_mrt_distance_m?: number;
  min_schools_within_1km?: number;
  limit?: number;
}): Promise<DirectTransitResponse> {
  return postJSON<DirectTransitResponse>("/transit/direct-convenience", body);
}

// --- Phase 3: commute / couple / lifestyle ---
export function optimizeCommute(
  destinations: DestinationPayload[],
  limit = 100,
): Promise<CommuteOptimizeResponse> {
  return postJSON<CommuteOptimizeResponse>("/commute/optimize", { destinations, limit });
}

export function getCommuteHeatmap(
  destinations: DestinationPayload[],
): Promise<CommuteHeatmapResponse> {
  return postJSON<CommuteHeatmapResponse>("/commute/heatmap", { destinations });
}

export function getBlockLifestyle(
  blockId: number,
  destinations: DestinationPayload[] = [],
): Promise<LifestyleResult> {
  return postJSON<LifestyleResult>(`/lifestyle/block/${blockId}`, { destinations });
}

// --- Phase 4: appreciation / dream home ---
export function getAppreciation(blockId: number): Promise<AppreciationResult> {
  return getJSON<AppreciationResult>(`/appreciation/${blockId}`);
}

export interface DreamHomeBody {
  max_price?: number;
  flat_type?: string;
  min_remaining_lease?: number;
  max_mrt_distance_m?: number;
  min_schools_within_1km?: number;
  destinations?: DestinationPayload[];
  limit?: number;
}

export function findDreamHome(body: DreamHomeBody): Promise<DreamHomeResponse> {
  return postJSON<DreamHomeResponse>("/dream-home-finder", body);
}

// --- Phase 5: forecast / undervalued / recommendations ---
export function getEstateForecast(
  planningAreaId: number,
  flatType?: string,
  horizonMonths = 12,
): Promise<ForecastResult> {
  const params = new URLSearchParams({ horizon_months: String(horizonMonths) });
  if (flatType) params.set("flat_type", flatType);
  return getJSON<ForecastResult>(`/forecast/estate/${planningAreaId}?${params}`);
}

export function getUndervalued(flatType?: string): Promise<UndervaluedResponse> {
  const qs = flatType ? `?flat_type=${encodeURIComponent(flatType)}` : "";
  return getJSON<UndervaluedResponse>(`/undervalued${qs}`);
}

export function getRecommendations(
  destinations: DestinationPayload[] = [],
  limit = 10,
): Promise<RecommendationResponse> {
  return postJSON<RecommendationResponse>("/recommendations", { destinations, limit });
}

// --- Score Ranking ---
export function getScoreRankingFields(): Promise<{ fields: ScoreField[] }> {
  return getJSON<{ fields: ScoreField[] }>("/score-ranking/fields");
}

export function rankByScore(body: {
  weights: Record<string, number>;
  destinations?: DestinationPayload[];
  limit?: number;
}): Promise<ScoreRankingResponse> {
  return postJSON<ScoreRankingResponse>("/score-ranking", body);
}

// --- Appreciation rankings (precomputed) ---
export function getRegionRankings(limit = 30): Promise<RankingsResponse<RegionRankingRow>> {
  return getJSON<RankingsResponse<RegionRankingRow>>(`/rankings/regions?limit=${limit}`);
}

export function getBlockRankings(
  limit = 30,
  planningAreaId?: number,
): Promise<RankingsResponse<BlockRankingRow>> {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (planningAreaId != null) qs.set("planning_area_id", String(planningAreaId));
  return getJSON<RankingsResponse<BlockRankingRow>>(`/rankings/blocks?${qs}`);
}

// --- HomeOS Agent ---
export function investigateHomeOSProfile(
  profileText: string,
  limit = 5,
): Promise<HomeOSInvestigationResponse> {
  return postJSON<HomeOSInvestigationResponse>("/homeos/investigate", {
    profile_text: profileText,
    limit,
  });
}

export function getHomeOSCaseFile(
  blockId: number,
  profileText: string,
  caseId?: string,
): Promise<HomeOSCaseFile> {
  return postJSON<HomeOSCaseFile>(`/homeos/case-file/${blockId}`, {
    profile_text: profileText,
    ...(caseId ? { case_id: caseId } : {}),
  });
}

export function scheduleHomeOSViewing(
  body: HomeOSScheduleViewingBody,
): Promise<HomeOSScheduleViewingResponse> {
  return postJSON<HomeOSScheduleViewingResponse>("/homeos/schedule-viewing", body);
}

export function getBlockListings(blockId: number): Promise<BlockListingsResponse> {
  return getJSON<BlockListingsResponse>(`/blocks/${blockId}/listings`);
}

export function getBlockAgents(address: string): Promise<BlockAgentsResponse> {
  return getJSON<BlockAgentsResponse>(
    `/blocks/agents?address=${encodeURIComponent(address)}`,
  );
}

export function prepareOutreachMessage(
  listingId: number,
  body: {
    case_id?: string;
    contact_name?: string;
    availability?: string[];
    note?: string;
  },
): Promise<OutreachMessageResponse> {
  return postJSON<OutreachMessageResponse>(`/listings/${listingId}/outreach-message`, body);
}

export function getCases(): Promise<HomeOSCaseSummary[]> {
  return getJSON<HomeOSCaseSummary[]>("/homeos/cases");
}

export function getCase(caseId: string): Promise<HomeOSCase> {
  return getJSON<HomeOSCase>(`/homeos/cases/${caseId}`);
}

export async function* investigateStream(
  profileText: string,
  limit = 5,
  model?: string,
): AsyncGenerator<AgentEvent> {
  const res = await fetch(`${BASE}/homeos/investigate-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ profile_text: profileText, limit, model }),
  });
  if (!res.ok || !res.body) throw new Error(`API ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        yield JSON.parse(line.slice(6)) as AgentEvent;
      } catch {
        // Ignore malformed SSE payloads.
      }
    }
  }
}

export async function* refineStream(
  caseId: string,
  message: string,
  model?: string,
): AsyncGenerator<AgentEvent> {
  const res = await fetch(`${BASE}/homeos/cases/${caseId}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ message, model }),
  });
  if (!res.ok || !res.body) throw new Error(`API ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        yield JSON.parse(line.slice(6)) as AgentEvent;
      } catch {
        // Ignore malformed SSE payloads.
      }
    }
  }
}

export async function* chatInCase(
  caseId: string,
  message: string,
): AsyncGenerator<string> {
  const res = await fetch(`${BASE}/homeos/cases/${caseId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ message }),
  });
  if (!res.ok || !res.body) throw new Error(`API ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") return;
      try {
        const parsed = JSON.parse(payload) as { chunk: string };
        yield parsed.chunk;
      } catch {
        // Ignore malformed SSE payloads.
      }
    }
  }
}

export async function getNews(): Promise<NewsItem[]> {
  return getJSON<NewsItem[]>("/news");
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
}

export interface ModelsResponse {
  models: ModelInfo[];
  default: string;
}

export function getModels(): Promise<ModelsResponse> {
  return getJSON<ModelsResponse>("/models");
}
