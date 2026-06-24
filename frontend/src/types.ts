// Shared API types (mirror the backend response shapes).

export interface SearchFilters {
  town?: string;
  planning_area_id?: number;
  flat_type?: string;
  min_price?: number;
  max_price?: number;
  min_psf?: number;
  max_psf?: number;
  max_mrt_distance_m?: number;
  min_schools_within_1km?: number;
  bbox?: [number, number, number, number]; // minx, miny, maxx, maxy
  limit?: number;
}

export interface BlockSummary {
  block_id: number;
  block_number: string;
  street_name: string;
  town: string;
  planning_area_id: number | null;
  lon: number;
  lat: number;
  lease_commencement_year: number;
  nearest_mrt_distance_m: number | null;
  schools_within_1km: number | null;
  median_psf: number | null;
  median_price: number | null;
  txn_count: number;
  transit_matches?: DirectTransitMatch[];
}

export interface DirectTransitDestination {
  name: string;
  address?: string;
  lat: number;
  lon: number;
}

export interface DirectTransitOption {
  mode: "bus" | "mrt";
  origin_code: string;
  origin_name: string;
  destination_code: string;
  destination_name: string;
  service: string;
  direction: string | null;
  origin_walk_m: number;
  destination_walk_m: number;
}

export interface DirectTransitMatch {
  destination: string;
  options: DirectTransitOption[];
}

export interface DirectTransitResponse {
  count: number;
  walk_limit_m: number;
  destinations: DirectTransitDestination[];
  results: BlockSummary[];
}

export interface SearchResponse {
  count: number;
  results: BlockSummary[];
}

export interface MonthlyPoint {
  month: string;
  median_psf: number | null;
  avg_psf: number | null;
  median_price: number | null;
  avg_price: number | null;
  txn_count: number;
}

export interface EstateAnalytics {
  scope: "estate";
  planning_area_id: number;
  block_count: number;
  metrics: {
    median_psf: number | null;
    avg_psf: number | null;
    median_price: number | null;
    avg_price: number | null;
    txn_count: number;
    growth_pct: number | null;
  };
  psf_over_time: MonthlyPoint[];
  volume_over_time: { month: string; txn_count: number }[];
  psf_by_flat_type: { flat_type: string; median_psf: number | null; txn_count: number }[];
}

export interface AccessibilityScores {
  mrt_score: number | null;
  future_mrt_score: number | null;
  bus_score: number | null;
  school_score: number | null;
  combined_score: number | null;
}

export interface LeaseProfile {
  avg_remaining_lease: number | null;
  min_remaining_lease: number | null;
  max_remaining_lease: number | null;
}

export interface EstateComparisonRow {
  planning_area_id: number;
  name: string | null;
  block_count: number;
  median_psf: number | null;
  median_price: number | null;
  growth_pct: number | null;
  txn_count: number;
  lease_profile: LeaseProfile;
  accessibility: AccessibilityScores;
}

export interface ComparisonResponse {
  estates: EstateComparisonRow[];
}

// --- Phase 3 ---
export interface DestinationPayload {
  name: string;
  lat: number;
  lon: number;
  visits_per_week: number;
  mode?: string;
}

export interface CommuteResultRow {
  block_id: number;
  block_number: string;
  town: string;
  lon: number;
  lat: number;
  weekly_minutes: number;
  monthly_minutes: number;
  commute_score: number;
  band: string;
}

export interface CommuteOptimizeResponse {
  results: CommuteResultRow[];
}

export interface CommuteHeatmapResponse {
  points: {
    block_id: number;
    lon: number;
    lat: number;
    commute_score: number;
    band: string;
  }[];
}

export interface LifestyleResult {
  block_id: number;
  lifestyle_score: number | null;
  factors: Record<string, number>;
}

// --- Phase 4 ---
export interface AppreciationResult {
  block_id: number;
  appreciation_score: number | null;
  confidence_level: string;
  risk_level: string;
  factors: Record<string, number>;
  disclaimer: string;
}

export interface DreamHomeMatch {
  block_id: number;
  block_number: string;
  town: string;
  planning_area_id: number | null;
  lon: number;
  lat: number;
  median_price: number | null;
  remaining_lease_years: number;
  match_score: number | null;
  components: Record<string, number>;
}

export interface DreamHomeResponse {
  match_count: number;
  results: DreamHomeMatch[];
  recommended_estates: {
    planning_area_id: number;
    avg_match_score: number;
    block_count: number;
  }[];
}

// --- Phase 5 ---
export interface ForecastPoint {
  month: string;
  psf: number;
  lower: number;
  upper: number;
}

export interface ForecastResult {
  scope: string;
  current_psf: number;
  slope_per_month: number;
  r_squared: number;
  horizon_months: number;
  projected_psf: number;
  projection: ForecastPoint[];
  disclaimer: string;
}

export interface UndervaluedEstate {
  planning_area_id: number;
  name: string | null;
  median_psf: number;
  predicted_psf: number;
  discount_vs_peers_pct: number;
  growth_pct: number | null;
  accessibility: number | null;
  undervalued_score: number;
  reason: string;
}

export interface UndervaluedResponse {
  undervalued: UndervaluedEstate[];
  disclaimer?: string;
}

export interface RecommendationRow {
  block_id: number;
  block_number: string;
  town: string;
  overall_score: number;
  lifestyle_score: number | null;
  appreciation_score: number | null;
  reasons: string[];
}

export interface RecommendationResponse {
  count: number;
  results: RecommendationRow[];
  recommended_estates: {
    planning_area_id: number;
    avg_score: number;
    block_count: number;
  }[];
}

// --- Score Ranking ---
export interface ScoreField {
  key: string;
  label: string;
  description: string;
  default_weight: number;
  needs_destinations: boolean;
  coming_soon: boolean;
}

export interface ScoreRankingRow {
  block_id: number;
  block_number: string;
  street_name: string;
  town: string;
  planning_area_id: number | null;
  lon: number;
  lat: number;
  overall_score: number;
  breakdown: Record<string, number>;
  rank: number;
}

export interface ScoreRankingResponse {
  count: number;
  results: ScoreRankingRow[];
  fields: ScoreField[];
  weights: Record<string, number>;
}

// --- Appreciation rankings ---
export interface RegionRankingRow {
  planning_area_id: number;
  name: string | null;
  region: string | null;
  rank: number;
  appreciation_score: number | null;
  cagr_pct: number | null;
  median_psf_start: number | null;
  median_psf_end: number | null;
  year_start: number | null;
  year_end: number | null;
  txn_count: number;
  block_count: number;
  computed_at: string;
}

export interface BlockRankingRow {
  block_id: number;
  planning_area_id: number | null;
  planning_area_name: string | null;
  block_number: string | null;
  street_name: string | null;
  town: string | null;
  lat: number | null;
  lon: number | null;
  rank: number;
  region_rank: number | null;
  appreciation_score: number | null;
  cagr_pct: number | null;
  year_start: number | null;
  year_end: number | null;
  txn_count: number;
}

export interface RankingsResponse<T> {
  count: number;
  results: T[];
  computed_at: string | null;
}

// --- BTO ---
export interface BtoExercise {
  exercise_id: string;
  label: string;
  launch_start_date: string | null;
  launch_end_date: string | null;
  is_final_update: boolean;
  estate_count: number;
  total_units: number;
  total_applicants: number;
  overall_app_rate: number | null;
  fetched_at: string;
}

export interface BtoRate {
  id: number;
  exercise_id: string;
  estate_name: string;
  flat_type: string;
  classification: string | null;
  project_names: string | null;
  flat_supply: number;
  total_applicant_no: number;
  overall_rate: number | null;
  rate_first_time_fam: number | null;
  rate_second_time_fam: number | null;
  rate_first_time_singles: number | null;
  rate_elderly: number | null;
}

export interface BtoExerciseDetail {
  exercise: BtoExercise;
  rates: BtoRate[];
  estates: { estate_name: string; flat_types: BtoRate[] }[];
}

export interface BtoTrends {
  overall: { exercise_id: string; label: string; overall_app_rate: number | null; total_units: number; total_applicants: number }[];
  by_flat_type: { flat_type: string; series: { exercise_id: string; label: string; rate: number | null }[] }[];
  exercise_count: number;
}

export interface BtoPriceTrends {
  years: number[];
  by_room_type: { room_type: string; series: { financial_year: number; mid: number | null }[] }[];
  towns: string[];
  room_types: string[];
}

export interface BtoPriceRow {
  id: number;
  financial_year: number;
  town: string;
  room_type: string;
  min_selling_price: number | null;
  max_selling_price: number | null;
  min_price_less_grant: number | null;
  max_price_less_grant: number | null;
}

export interface CompareOptions {
  towns: string[];
  flat_types: string[];
}

export interface BtoResaleCompare {
  town: string;
  flat_type: string;
  bto: {
    available: boolean; latest_year: number | null;
    min_price: number | null; max_price: number | null; mid_price: number | null;
    app_rate: number | null; wait_years: string;
  };
  resale: {
    available: boolean; median_price: number | null; median_psf: number | null;
    txn_count: number; cagr_pct: number | null; wait_years: string;
  };
  gap: { price_diff: number | null; price_pct: number | null; annual_saving: number | null };
  price_series: { year: number; bto: number | null; resale: number | null }[];
}

// --- HomeOS Agent ---
export interface HomeOSPreferences {
  flat_type: string | null;
  max_price: number | null;
  commute_priority: "low" | "medium" | "high";
  school_priority: "low" | "medium" | "high";
  risk_tolerance: "low" | "medium";
  appreciation_priority: "medium" | "high";
}

export interface HomeOSAvatar {
  label: string;
  buyer_type: string;
  summary: string;
  preferences: HomeOSPreferences;
}

export type AgentSource = "market" | "location" | "risk" | "lifestyle";

export type AgentKey = "market" | "location" | "lifestyle" | "risk";

export interface AgentProgressEntry {
  status: "idle" | "running" | "done";
  blocksDone: number;
  snippets: { block_id: number; narrative: string }[];
}

export type AgentProgressMap = Map<AgentKey, AgentProgressEntry>;

export type BlockNarrativeMap = Map<number, Map<AgentKey, string>>;

export interface EvidenceItem {
  text: string;
  source: AgentSource;
}

export interface TraceToolCall {
  tool_name: string;
  args: unknown;
  result?: unknown;
}

export interface AgentTrace {
  agent: AgentSource;
  narrative: string;
  tool_calls: TraceToolCall[];
}

export interface HomeOSShortlistRow {
  block_id: number;
  block_number: string;
  street_name: string;
  town: string;
  worth_viewing_score: number;
  verdict: "Worth viewing" | "Maybe view" | "Skip for now";
  confidence: "low" | "medium" | "high";
  top_reasons: EvidenceItem[];
  top_watchouts: EvidenceItem[];
}

export interface HomeOSInvestigationResponse {
  avatar: HomeOSAvatar;
  shortlist: HomeOSShortlistRow[];
}

export interface HomeOSCaseFile {
  block_id: number;
  block_number: string;
  street_name: string;
  town: string;
  verdict: string;
  worth_viewing_score: number;
  confidence: "low" | "medium" | "high";
  top_reasons: EvidenceItem[];
  top_watchouts: EvidenceItem[];
  evidence: {
    recent_sales: {
      transaction_count: number;
      median_price: number | null;
      median_psf: number | null;
      window_months: number;
      summary: string;
    };
    connections: Record<string, unknown>[];
    risks: string[];
    future_signals: Record<string, unknown>;
    agent_questions: string[];
  };
  trace?: AgentTrace[];
}

export interface HomeOSScheduleViewingBody {
  profile_text: string;
  block_id: number;
  availability: string[];
  contact_name: string;
  contact_note?: string;
}

export interface HomeOSScheduleViewingResponse {
  status: "ready_for_agent";
  confirmation: string;
  outbox: {
    block_id: number;
    recipient_type: "real_estate_agent";
    message: string;
    availability: string[];
  };
}

// --- HomeOS Cases and Pipeline ---
export interface AgentEvent {
  event: "agent_start" | "agent_data" | "agent_summary" | "agent_done" | "case_done" | "case_error" | "clarifying_question";
  agent?: string;
  block_id?: number | null;
  narrative?: string;
  data?: Record<string, unknown>;
  case_id?: string;
  shortlist?: HomeOSShortlistRow[];
  message?: string;
  question?: string;
  field?: string;
}

export interface HomeOSCaseSummary {
  case_id: string;
  created_at: string;
  profile_text: string;
  status: "running" | "refining" | "done" | "error";
  shortlist_count: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface HomeOSCase {
  case_id: string;
  created_at: string;
  profile_text: string;
  avatar: HomeOSAvatar | null;
  pipeline: AgentEvent[];
  shortlist: HomeOSShortlistRow[];
  conversation: ChatMessage[];
  status: "running" | "refining" | "done" | "error";
}


// --- Active listings (HDB Flat Portal) ---
export interface ActiveListing {
  listing_id: number;
  block_id: number;
  block_number: string;
  street_name: string;
  postal_code: string;
  town: string;
  price: number;
  flat_type: string;
  floor_area_sqm: number;
  floor_area_sqft: number;
  storey_range: string;
  remaining_lease: string;
  bedroom?: number;
  bathroom?: number;
  description?: string;
  photo_path?: string;
  agent_name?: string;
  agent_phone?: string;
  agent_email?: string;
  agency_name?: string;
  managed_by_agent: boolean;
  last_updated: string;
}

export interface BlockListingsResponse {
  count: number;
  listings: ActiveListing[];
}

export interface OutreachMessageResponse {
  listing_id: number;
  message: string;
  questions: string[];
  whatsapp_url?: string;
  email_url?: string;
  agent_name?: string;
}

export interface ListingSummary {
  listing_id: number;
  price: number;
  flat_type: string;
  floor_area_sqm: number;
  floor_area_sqft: number;
  storey_range: string;
  remaining_lease: string;
  description?: string;
}

export interface BlockAgent {
  agent_name?: string;
  agent_phone?: string;
  agent_email?: string;
  agency_name?: string;
  listings: ListingSummary[];
}

export interface BlockAgentsResponse {
  block: {
    block_id: number;
    block_number: string;
    street_name: string;
    town: string;
  };
  agents: BlockAgent[];
  owner_listings: ListingSummary[];
  listing_count: number;
}

export interface NewsItem {
  title: string;
  url: string;
  published_date: string | null;
  domain: string | null;
}
