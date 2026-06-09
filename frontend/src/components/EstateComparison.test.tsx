import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EstateComparison from "./EstateComparison";
import type { EstateComparisonRow } from "../types";

const rows: EstateComparisonRow[] = [
  {
    planning_area_id: 1,
    name: "TAMPINES",
    block_count: 6,
    median_psf: 560,
    median_price: 520000,
    growth_pct: 9.5,
    txn_count: 120,
    lease_profile: { avg_remaining_lease: 80, min_remaining_lease: 70, max_remaining_lease: 90 },
    accessibility: {
      mrt_score: 70, future_mrt_score: 50, bus_score: 60,
      school_score: 80, combined_score: 72,
    },
  },
];

describe("EstateComparison", () => {
  it("renders a row per estate", () => {
    render(<EstateComparison rows={rows} />);
    expect(screen.getByText("TAMPINES")).toBeInTheDocument();
    expect(screen.getByText("9.5%")).toBeInTheDocument();
    expect(screen.getByText("72")).toBeInTheDocument(); // combined score pill
  });

  it("shows empty state with no rows", () => {
    render(<EstateComparison rows={[]} />);
    expect(screen.getByText(/No estates to compare/i)).toBeInTheDocument();
  });
});
