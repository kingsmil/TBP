import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AppreciationCard from "./AppreciationCard";
import type { AppreciationResult } from "../types";

const data: AppreciationResult = {
  block_id: 1,
  appreciation_score: 68,
  confidence_level: "high",
  risk_level: "low",
  factors: { growth: 70, lease: 80 },
  disclaimer: "Not financial advice.",
};

describe("AppreciationCard", () => {
  it("shows score, levels and disclaimer", () => {
    render(<AppreciationCard data={data} />);
    expect(screen.getByText("68")).toBeInTheDocument();
    expect(screen.getByText("Low")).toBeInTheDocument();   // risk
    expect(screen.getByText("High")).toBeInTheDocument();  // confidence
    expect(screen.getByText(/Not financial advice/i)).toBeInTheDocument();
  });
});
