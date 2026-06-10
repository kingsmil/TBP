import { fireEvent, render, screen } from "@testing-library/react";
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
  isAuthenticated: true,
  onNewCase: vi.fn(),
  onNewSession: vi.fn(),
  onSelectCase: vi.fn(),
  onSendMessage: vi.fn(),
  onRefine: vi.fn(),
  onSignInRequired: vi.fn(),
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
    expect(screen.getAllByText(/Family looking/i).length).toBeGreaterThan(0);
  });

  it("disables input while streaming", () => {
    render(<CasesPanel {...baseProps} isStreaming />);
    const input = screen.getByRole("textbox");
    expect(input).toBeDisabled();
  });

  it("+ button opens a blank session instead of auto-submitting a profile", () => {
    const onNewSession = vi.fn();
    const onNewCase = vi.fn();
    render(<CasesPanel {...baseProps} onNewSession={onNewSession} onNewCase={onNewCase} />);
    fireEvent.click(screen.getByRole("button", { name: /new case/i }));
    expect(onNewSession).toHaveBeenCalledTimes(1);
    expect(onNewCase).not.toHaveBeenCalled();
  });
});
