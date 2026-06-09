import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import CommuteResults from "./CommuteResults";
import type { CommuteResultRow } from "../types";

const rows: CommuteResultRow[] = [
  {
    block_id: 1, block_number: "101", town: "TAMPINES",
    lon: 103.94, lat: 1.35, weekly_minutes: 300, monthly_minutes: 1300,
    commute_score: 82, band: "green",
  },
];

describe("CommuteResults", () => {
  it("renders a row with score", () => {
    render(<CommuteResults rows={rows} />);
    expect(screen.getByText("Blk 101")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
  });

  it("shows empty prompt with no rows", () => {
    render(<CommuteResults rows={[]} />);
    expect(screen.getByText(/Add destinations/i)).toBeInTheDocument();
  });
});
