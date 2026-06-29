import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AgentChip from "./AgentChip";

describe("AgentChip", () => {
  it("renders 'Market' for market source", () => {
    render(<AgentChip source="market" />);
    expect(screen.getByText("Market")).toBeInTheDocument();
  });

  it("renders 'Location' for location source", () => {
    render(<AgentChip source="location" />);
    expect(screen.getByText("Location")).toBeInTheDocument();
  });

  it("renders 'Risk' for risk source", () => {
    render(<AgentChip source="risk" />);
    expect(screen.getByText("Risk")).toBeInTheDocument();
  });
});
