import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import HomeOSDetailPanel from "./HomeOSDetailPanel";

vi.mock("../lib/api", () => ({
  getBlockListings: vi.fn(async () => ({ block_id: 1, count: 0, listings: [] })),
  getHomeOSCaseFile: vi.fn(async () => ({
    block_id: 1,
    block_number: "117",
    street_name: "BISHAN ST 3",
    town: "BISHAN",
    verdict: "Worth viewing",
    worth_viewing_score: 82,
    confidence: "high",
    top_reasons: ["Recent comparable sales support the budget."],
    top_watchouts: [],
    evidence: {
      recent_sales: {
        transaction_count: 6,
        median_price: 580000,
        median_psf: 620,
        window_months: 6,
        summary: "Recent sales look healthy.",
      },
      connections: [],
      risks: [],
      future_signals: {},
      agent_questions: ["Can the agent confirm condition?"],
    },
  })),
  scheduleHomeOSViewing: vi.fn(),
}));

const block = {
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
};

describe("HomeOSDetailPanel", () => {
  it("shows a download case button after the case file loads", async () => {
    render(
      <HomeOSDetailPanel
        block={block}
        profileText="Family looking for 4 room under 800k."
        caseId="case-1"
        onClose={vi.fn()}
      />,
    );

    expect(await screen.findByRole("button", { name: /download case/i })).toBeInTheDocument();
  });

  it("uses the active recommendation score instead of a recalculated case-file score", async () => {
    render(
      <HomeOSDetailPanel
        block={block}
        profileText="Family looking for 4 room under 800k."
        caseId="case-1"
        recommendation={{
          block_id: 1,
          block_number: "117",
          street_name: "BISHAN ST 3",
          town: "BISHAN",
          verdict: "Worth viewing",
          worth_viewing_score: 91.5,
          confidence: "high",
          top_reasons: ["Matches the refined requirements."],
          top_watchouts: [],
        }}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/Worth viewing · 91\.5/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /download case/i })).toBeInTheDocument();
    expect(screen.queryByText(/Worth viewing · 82/)).not.toBeInTheDocument();
  });
});
