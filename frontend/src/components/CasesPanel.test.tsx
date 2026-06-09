import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CasesPanel from "./CasesPanel";
import type { HomeOSCaseSummary } from "../types";

const mockCase: HomeOSCaseSummary = {
  case_id: "abc-123",
  created_at: "2026-06-09T10:00:00Z",
  profile_text: "Family looking for 4 room under 800k.",
  status: "done",
  shortlist_count: 3,
};

const baseProps = {
  cases: [] as HomeOSCaseSummary[],
  activeCaseId: null,
  activeCase: null,
  streamingEvents: [],
  chatChunks: "",
  isStreaming: false,
  onNewCase: vi.fn(),
  onSelectCase: vi.fn(),
  onSendMessage: vi.fn(),
  onRefine: vi.fn(),
};

describe("CasesPanel", () => {
  it("renders input and send button", () => {
    render(<CasesPanel {...baseProps} />);
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });

  it("shows no-case placeholder when no cases", () => {
    render(<CasesPanel {...baseProps} />);
    expect(screen.getByText(/start a new investigation/i)).toBeInTheDocument();
  });

  it("shows cases in dropdown when cases exist", () => {
    render(<CasesPanel {...baseProps} cases={[mockCase]} activeCaseId="abc-123" />);
    expect(screen.getByText(/Family looking/i)).toBeInTheDocument();
  });

  it("disables input while streaming", () => {
    render(<CasesPanel {...baseProps} isStreaming />);
    const input = screen.getByRole("textbox");
    expect(input).toBeDisabled();
  });
});
