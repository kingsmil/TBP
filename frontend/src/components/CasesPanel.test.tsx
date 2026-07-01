import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CasesPanel from "./CasesPanel";
import type { HomeOSCase, HomeOSCaseSummary } from "../types";

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
  isSubscribed: true,
  onNewCase: vi.fn(),
  onSelectCase: vi.fn(),
  onSendMessage: vi.fn(),
  onRefine: vi.fn(),
  onSignInRequired: vi.fn(),
  onUpgradeRequired: vi.fn(),
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

  it("routes the new-case shortcut through sign-in gating", () => {
    const onSignInRequired = vi.fn();
    const onNewCase = vi.fn();
    render(
      <CasesPanel
        {...baseProps}
        isAuthenticated={false}
        onSignInRequired={onSignInRequired}
        onNewCase={onNewCase}
      />,
    );
    fireEvent.click(screen.getByTitle(/new case/i));
    expect(onSignInRequired).toHaveBeenCalled();
    expect(onNewCase).not.toHaveBeenCalled();
  });

  it("routes the new-case shortcut through upgrade gating", () => {
    const onUpgradeRequired = vi.fn();
    const onNewCase = vi.fn();
    render(
      <CasesPanel
        {...baseProps}
        isSubscribed={false}
        onUpgradeRequired={onUpgradeRequired}
        onNewCase={onNewCase}
      />,
    );
    fireEvent.click(screen.getByTitle(/new case/i));
    expect(onUpgradeRequired).toHaveBeenCalled();
    expect(onNewCase).not.toHaveBeenCalled();
  });

  it("disables input while streaming", () => {
    render(<CasesPanel {...baseProps} isStreaming />);
    const input = screen.getByRole("textbox");
    expect(input).toBeDisabled();
  });

  it("shows search summaries from the agent pipeline", () => {
    const activeCase: HomeOSCase = {
      case_id: "abc-123",
      created_at: "2026-06-09T10:00:00Z",
      profile_text: "Family looking for 4 room under 800k.",
      status: "refining",
      avatar: null,
      shortlist: [],
      conversation: [],
      pipeline: [
        {
          event: "agent_summary",
          agent: "search",
          block_id: null,
          narrative: "Found 12 matching properties.",
          data: {
            candidates_found: 12,
            search_query: { flat_type: "4 ROOM", max_price: 800000 },
          },
        },
        {
          event: "clarifying_question",
          case_id: "abc-123",
          field: "ready_to_proceed",
          question: "Ready to analyse 5 blocks?",
        },
      ],
    };

    render(
      <CasesPanel
        {...baseProps}
        cases={[{ ...mockCase, status: "refining" }]}
        activeCaseId="abc-123"
        activeCase={activeCase}
      />,
    );

    expect(screen.getByText(/I searched and found/i)).toBeInTheDocument();
    expect(screen.getByText(/flat_type: 4 ROOM/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /proceed with analysis/i })).toBeInTheDocument();
  });

  it("shows no-results recovery chips", () => {
    const activeCase: HomeOSCase = {
      case_id: "abc-123",
      created_at: "2026-06-09T10:00:00Z",
      profile_text: "I want a 3 room in Serangoon under 700k.",
      status: "refining",
      avatar: null,
      shortlist: [],
      conversation: [],
      pipeline: [
        {
          event: "clarifying_question",
          case_id: "abc-123",
          field: "no_results",
          question: "I found 0 matching blocks with those filters.",
        },
      ],
    };

    render(
      <CasesPanel
        {...baseProps}
        cases={[{ ...mockCase, status: "refining" }]}
        activeCaseId="abc-123"
        activeCase={activeCase}
      />,
    );

    expect(screen.getByRole("button", { name: /any town/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove budget/i })).toBeInTheDocument();
  });
});
