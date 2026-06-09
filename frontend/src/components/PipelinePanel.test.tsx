import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PipelinePanel from "./PipelinePanel";
import type { AgentEvent, HomeOSCase } from "../types";

const mockCase: HomeOSCase = {
  case_id: "abc-123",
  created_at: "2026-06-09T10:00:00Z",
  profile_text: "Family 4 room 800k.",
  avatar: {
    label: "Mock HomeOS Agent",
    buyer_type: "family",
    summary: "Mock profile: Family buyer prioritizing schools.",
    preferences: {
      flat_type: "4 ROOM",
      max_price: 800000,
      commute_priority: "medium",
      school_priority: "high",
      risk_tolerance: "low",
      appreciation_priority: "medium",
    },
  },
  pipeline: [
    { event: "agent_start", agent: "profile", block_id: null },
    {
      event: "agent_summary",
      agent: "profile",
      block_id: null,
      narrative: "Mock profile: Family buyer, 4-room, $800k budget.",
    },
    { event: "agent_done", agent: "profile", block_id: null },
    { event: "agent_start", agent: "market", block_id: 1 },
    {
      event: "agent_summary",
      agent: "market",
      block_id: 1,
      narrative: "Mock market: 6 recent sales support budget.",
    },
  ],
  shortlist: [
    {
      block_id: 1,
      block_number: "117",
      street_name: "BISHAN ST 3",
      town: "BISHAN",
      worth_viewing_score: 81.2,
      verdict: "Worth viewing",
      confidence: "high",
      top_reasons: ["Budget fits.", "Schools nearby."],
      top_watchouts: ["MRT is moderate."],
    },
    {
      block_id: 2,
      block_number: "118",
      street_name: "BISHAN ST 4",
      town: "BISHAN",
      worth_viewing_score: 76.4,
      verdict: "Worth viewing",
      confidence: "medium",
      top_reasons: ["Good comparables."],
      top_watchouts: [],
    },
  ],
  conversation: [],
  status: "done",
};

describe("PipelinePanel", () => {
  it("renders avatar label and agent summary narratives", () => {
    render(
      <PipelinePanel
        activeCase={mockCase}
        streamingEvents={[]}
        onSelectBlock={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText("Mock HomeOS Agent")).toBeInTheDocument();
    expect(
      screen.getByText("Mock profile: Family buyer, 4-room, $800k budget."),
    ).toBeInTheDocument();
    expect(screen.getByText("Mock market: 6 recent sales support budget.")).toBeInTheDocument();
  });

  it("shows running agent steps from streaming events", () => {
    const streaming: AgentEvent[] = [
      { event: "agent_start", agent: "location", block_id: 2 },
    ];

    render(
      <PipelinePanel
        activeCase={null}
        streamingEvents={streaming}
        onSelectBlock={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText(/Querying Location Graph/i)).toBeInTheDocument();
  });

  it("renders multiple recommended listings for one case", () => {
    render(
      <PipelinePanel
        activeCase={mockCase}
        streamingEvents={[]}
        onSelectBlock={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText(/2 recommended listings/i)).toBeInTheDocument();
    expect(screen.getByText(/Blk 117 BISHAN ST 3/i)).toBeInTheDocument();
    expect(screen.getByText(/Blk 118 BISHAN ST 4/i)).toBeInTheDocument();
  });

  it("expands an agent row to show full details when clicked", () => {
    render(
      <PipelinePanel
        activeCase={{
          ...mockCase,
          pipeline: [
            {
              event: "agent_summary",
              agent: "risk",
              block_id: 1,
              narrative: "Mock risk: no major watchouts surfaced; score adjustment is 7.8.",
              data: { score_adjustment: 7.8, watchouts: [] },
            },
          ],
        }}
        streamingEvents={[]}
        onSelectBlock={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.queryByText(/score_adjustment/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Mock risk:/i }));

    expect(screen.getByText("Risk Agent")).toBeInTheDocument();
    expect(screen.getByText(/score_adjustment/)).toBeInTheDocument();
    expect(screen.getByText("Blk 1")).toBeInTheDocument();
  });

  it("calls onSendMessage when chat is submitted", () => {
    const onSend = vi.fn();
    render(
      <PipelinePanel
        activeCase={mockCase}
        streamingEvents={[]}
        onSelectBlock={vi.fn()}
        onSendMessage={onSend}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(/ask/i), {
      target: { value: "Why Bishan?" },
    });
    fireEvent.submit(screen.getByRole("form"));

    expect(onSend).toHaveBeenCalledWith("Why Bishan?");
  });
});
