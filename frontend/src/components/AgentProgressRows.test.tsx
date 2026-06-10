import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AgentProgressRows from "./AgentProgressRows";
import type { AgentProgressMap } from "../types";

function makeMap(overrides: Partial<Record<string, { status: "idle" | "running" | "done"; blocksDone: number; snippets: { block_id: number; narrative: string }[] }>> = {}): AgentProgressMap {
  const defaults = {
    market: { status: "idle" as const, blocksDone: 0, snippets: [] },
    location: { status: "running" as const, blocksDone: 1, snippets: [{ block_id: 10, narrative: "MRT close." }] },
    lifestyle: { status: "idle" as const, blocksDone: 0, snippets: [] },
    risk: { status: "idle" as const, blocksDone: 0, snippets: [] },
  };
  return new Map(Object.entries({ ...defaults, ...overrides })) as AgentProgressMap;
}

describe("AgentProgressRows", () => {
  it("renders all four agent rows", () => {
    render(<AgentProgressRows agentProgress={makeMap()} globalStatus={null} />);
    expect(screen.getByText("Market")).toBeInTheDocument();
    expect(screen.getByText("Location")).toBeInTheDocument();
    expect(screen.getByText("Lifestyle")).toBeInTheDocument();
    expect(screen.getByText("Risk")).toBeInTheDocument();
  });

  it("shows block count badge when blocksDone > 0", () => {
    render(<AgentProgressRows agentProgress={makeMap()} globalStatus={null} />);
    expect(screen.getByText("1 block")).toBeInTheDocument();
  });

  it("shows global status line when provided", () => {
    render(<AgentProgressRows agentProgress={makeMap()} globalStatus="Searching for candidates…" />);
    expect(screen.getByText("Searching for candidates…")).toBeInTheDocument();
  });

  it("expands to show snippets on click", () => {
    render(<AgentProgressRows agentProgress={makeMap()} globalStatus={null} />);
    fireEvent.click(screen.getByText("Location"));
    expect(screen.getByText(/MRT close\./)).toBeInTheDocument();
  });

  it("collapses snippets on second click", () => {
    render(<AgentProgressRows agentProgress={makeMap()} globalStatus={null} />);
    fireEvent.click(screen.getByText("Location"));
    fireEvent.click(screen.getByText("Location"));
    expect(screen.queryByText(/MRT close\./)).not.toBeInTheDocument();
  });
});
