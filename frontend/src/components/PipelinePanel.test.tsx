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
  pipeline: [],
  shortlist: [
    {
      block_id: 1,
      block_number: "117",
      street_name: "BISHAN ST 3",
      town: "BISHAN",
      worth_viewing_score: 81.2,
      verdict: "Worth viewing",
      confidence: "high",
      top_reasons: [
        { text: "Budget fits.", source: "market" },
        { text: "Schools nearby.", source: "location" },
      ],
      top_watchouts: [{ text: "MRT is moderate.", source: "location" }],
    },
    {
      block_id: 2,
      block_number: "118",
      street_name: "BISHAN ST 4",
      town: "BISHAN",
      worth_viewing_score: 76.4,
      verdict: "Worth viewing",
      confidence: "medium",
      top_reasons: [{ text: "Good comparables.", source: "market" }],
      top_watchouts: [],
    },
  ],
  conversation: [],
  status: "done",
};

describe("PipelinePanel", () => {
  it("renders recommended listings for the active case", () => {
    render(
      <PipelinePanel
        activeCase={mockCase}
        streamingEvents={[]}
        onSelectBlock={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByText(/2 homes matched/i)).toBeInTheDocument();
    expect(screen.getByText(/Blk 117 BISHAN ST 3/i)).toBeInTheDocument();
    expect(screen.getByText(/Blk 118 BISHAN ST 4/i)).toBeInTheDocument();
  });

  it("shows a download case button in the visible shortlist panel", () => {
    render(
      <PipelinePanel
        activeCase={mockCase}
        streamingEvents={[]}
        onSelectBlock={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /download case/i })).toBeInTheDocument();
  });

  it("downloads the active case as json", () => {
    const createObjectURLMock = vi.fn(() => "blob:test");
    const revokeObjectURLMock = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectURLMock,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectURLMock,
    });
    const click = vi.fn();
    const appendChild = vi.spyOn(document.body, "appendChild");
    const originalCreateElement = document.createElement.bind(document);
    const createElement = vi.spyOn(document, "createElement");
    createElement.mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName === "a") {
        element.click = click;
      }
      return element;
    });

    render(
      <PipelinePanel
        activeCase={mockCase}
        streamingEvents={[]}
        onSelectBlock={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /download case/i }));

    expect(createObjectURLMock).toHaveBeenCalledWith(expect.any(Blob));
    expect(appendChild).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:test");

    appendChild.mockRestore();
    createElement.mockRestore();
  });

  it("shows running state from streaming events", () => {
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

    expect(screen.getByText(/Finding the best matching listings/i)).toBeInTheDocument();
  });
});
