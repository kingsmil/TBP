import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./components/MapView", () => ({
  default: () => <div data-testid="map-view" />,
}));

vi.mock("./lib/api", () => ({
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
  it("switches the left pane to manual live data mode", async () => {
    renderApp();

    expect(screen.getByRole("button", { name: /ai mode/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /manual/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /manual/i }));

    await waitFor(() => {
      expect(screen.getByText(/manual mode/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/browse the live dataset/i)).toBeInTheDocument();
    expect(screen.getByText(/estate comparison/i)).toBeInTheDocument();
  });
});
