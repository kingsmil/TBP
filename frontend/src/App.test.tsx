import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

// These tests exercise the AI-mode experience, which ships behind a feature
// flag (off by default). Enable it here so the AI surfaces render.
vi.mock("./lib/featureFlags", () => ({ AI_MODE_ENABLED: true }));

vi.mock("./components/MapView", () => ({
  default: ({
    selectedBlockId,
    onSelectBlock,
  }: {
    selectedBlockId?: number | null;
    onSelectBlock?: (blockId: number) => void;
  }) => (
    <div data-testid="map-view">
      <span data-testid="selected-block">{selectedBlockId ?? "none"}</span>
      <button type="button" onClick={() => onSelectBlock?.(1)}>Select block 1</button>
      <button type="button" onClick={() => onSelectBlock?.(2)}>Select block 2</button>
    </div>
  ),
}));

vi.mock("./lib/api", () => ({
  apiSubscriptionStatus: vi.fn(async () => ({ email: "pro@example.com", is_subscribed: true })),
  chatInCase: vi.fn(async function* () {}),
  getCase: vi.fn(async () => ({
    case_id: "case-1",
    created_at: "2026-06-09T10:00:00Z",
    profile_text: "Family looking for 4 room under 800k.",
    avatar: null,
    pipeline: [],
    shortlist: [],
    conversation: [],
    status: "done",
  })),
  getCases: vi.fn(async () => []),
  getModels: vi.fn(async () => ({
    models: [{ id: "openai/gpt-5.4-nano", name: "GPT-5.4 Nano", provider: "OpenAI" }],
    default: "openai/gpt-5.4-nano",
  })),
  getBlockListings: vi.fn(async () => ({ block_id: 1, count: 0, listings: [] })),
  getEstateAnalytics: vi.fn(async () => ({
    scope: "estate",
    planning_area_id: 1,
    block_count: 1,
    metrics: {
      median_psf: 612,
      avg_psf: 615,
      median_price: 580000,
      avg_price: 585000,
      txn_count: 12,
      growth_pct: 3.4,
    },
    psf_over_time: [],
    volume_over_time: [],
    psf_by_flat_type: [],
  })),
  getEstateComparison: vi.fn(async () => ({ estates: [] })),
  getScoreRankingFields: vi.fn(async () => ({ fields: [] })),
  rankByScore: vi.fn(async () => ({ count: 0, results: [], fields: [], weights: {} })),
  getRegionRankings: vi.fn(async () => ({ count: 0, results: [], computed_at: null })),
  getBlockRankings: vi.fn(async () => ({ count: 0, results: [], computed_at: null })),
  getBtoExercises: vi.fn(async () => ({ results: [] })),
  getBtoTrends: vi.fn(async () => ({ overall: [], by_flat_type: [], exercise_count: 0 })),
  getBtoExercise: vi.fn(async () => ({ exercise: null, rates: [], estates: [] })),
  getBtoPriceTrends: vi.fn(async () => ({ years: [], by_room_type: [], towns: [], room_types: [] })),
  geocodeAddress: vi.fn(async () => ({ results: [] })),
  getHomeOSCaseFile: vi.fn(),
  getRecommendations: vi.fn(),
  getReferenceLayer: vi.fn(),
  getUndervalued: vi.fn(),
  investigateHomeOSProfile: vi.fn(),
  investigateStream: vi.fn(async function* () {}),
  scheduleHomeOSViewing: vi.fn(),
  searchProperties: vi.fn(async () => ({
    count: 2,
    results: [
      {
        block_id: 1,
        block_number: "117",
        street_name: "BISHAN ST 3",
        town: "BISHAN",
        planning_area_id: 1,
        lon: 103.85,
        lat: 1.35,
        lease_commencement_year: 1985,
        nearest_mrt_distance_m: 420,
        schools_within_1km: 4,
        median_psf: 620,
        median_price: 580000,
        txn_count: 12,
      },
      {
        block_id: 2,
        block_number: "118",
        street_name: "BISHAN ST 4",
        town: "BISHAN",
        planning_area_id: 1,
        lon: 103.851,
        lat: 1.351,
        lease_commencement_year: 1986,
        nearest_mrt_distance_m: 610,
        schools_within_1km: 3,
        median_psf: 610,
        median_price: 575000,
        txn_count: 10,
      },
    ],
  })),
}));

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    // Seed a subscribed user so the app initializes in AI mode (these tests
    // exercise the AI experience, which requires an active subscription).
    window.localStorage.setItem("hdb_token", "test-token");
    window.localStorage.setItem(
      "hdb_user",
      JSON.stringify({ email: "pro@example.com", is_subscribed: true }),
    );
    // These tests exercise the resale product; skip the BTO/Resale chooser.
    window.localStorage.setItem("hdb-product", "resale");
    document.documentElement.classList.remove("dark");
  });

  it("switches from AI mode to Explore mode", async () => {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: /^explore$/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /ai mode/i })).toBeInTheDocument();
    });
    expect(screen.getByText(/estate comparison/i)).toBeInTheDocument();
  });

  it("can select again after close and deselect with Escape", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: /^explore$/i }));

    await waitFor(() => expect(screen.getByText("Select block 1")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Select block 1" }));
    expect(screen.getByTestId("selected-block")).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("button", { name: "Close panel" }));
    expect(screen.getByTestId("selected-block")).toHaveTextContent("none");

    fireEvent.click(screen.getByRole("button", { name: "Select block 2" }));
    expect(screen.getByTestId("selected-block")).toHaveTextContent("2");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByTestId("selected-block")).toHaveTextContent("none");
  });

  it("keeps AI and Explore selections independent", async () => {
    window.localStorage.setItem("hdb_token", "test-token");
    window.localStorage.setItem("hdb_user", JSON.stringify({
      email: "pro@example.com",
      is_subscribed: true,
    }));
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Select block 1" }));
    expect(screen.getByTestId("selected-block")).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("button", { name: /^explore$/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /ai mode/i })).toBeInTheDocument());
    expect(screen.getByTestId("selected-block")).toHaveTextContent("none");

    fireEvent.click(screen.getByRole("button", { name: "Select block 2" }));
    expect(screen.getByTestId("selected-block")).toHaveTextContent("2");

    fireEvent.click(screen.getByRole("button", { name: /ai mode/i }));
    expect(screen.getByTestId("selected-block")).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("button", { name: /^explore$/i }));
    expect(screen.getByTestId("selected-block")).toHaveTextContent("2");
  });

  it("toggles and persists dark mode", () => {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: /switch to dark mode/i }));

    expect(document.documentElement).toHaveClass("dark");
    expect(window.localStorage.getItem("hdb-match-theme")).toBe("dark");
    expect(screen.getByRole("button", { name: /switch to light mode/i })).toBeInTheDocument();
  });

  it("opens the sign-in modal from Explore mode", async () => {
    // Logged-out visitor lands directly in Explore mode with a Sign in button.
    window.localStorage.clear();
    window.localStorage.setItem("hdb-product", "resale");
    renderApp();

    await waitFor(() => screen.getByRole("button", { name: /^sign in$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(screen.getByText("Sign in to your account")).toBeInTheDocument();
  });

  it("collapses and expands the AI sidebar", () => {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: /collapse ai sidebar/i }));
    expect(screen.getByRole("button", { name: /expand ai sidebar/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /expand ai sidebar/i }));
    expect(screen.getByRole("button", { name: /collapse ai sidebar/i })).toBeInTheDocument();
  });
});
