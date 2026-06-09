import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import UndervaluedList from "./UndervaluedList";
import type { UndervaluedEstate } from "../types";

const estates: UndervaluedEstate[] = [
  {
    planning_area_id: 4,
    name: "JURONG WEST",
    median_psf: 504,
    predicted_psf: 601,
    discount_vs_peers_pct: 16,
    growth_pct: 9.8,
    accessibility: 55,
    undervalued_score: 25.9,
    reason: "16% below accessibility-implied PSF with 9.8% historical growth",
  },
];

describe("UndervaluedList", () => {
  it("renders an estate with its discount", () => {
    render(<UndervaluedList estates={estates} />);
    expect(screen.getByText("JURONG WEST")).toBeInTheDocument();
    expect(screen.getByText("-16%")).toBeInTheDocument();
    expect(screen.getByText(/historical growth/i)).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(<UndervaluedList estates={[]} />);
    expect(screen.getByText(/No undervalued estates/i)).toBeInTheDocument();
  });
});
