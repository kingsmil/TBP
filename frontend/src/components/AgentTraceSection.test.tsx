import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AgentTraceSection from "./AgentTraceSection";
import type { AgentTrace } from "../types";

const TRACE: AgentTrace[] = [
  {
    agent: "market",
    narrative: "Market looks solid.",
    tool_calls: [
      { tool_name: "recent_transactions", args: { block_id: 812 }, result: { count: 8 } },
    ],
  },
];

describe("AgentTraceSection", () => {
  it("renders nothing when trace is empty", () => {
    const { container } = render(<AgentTraceSection trace={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when trace is undefined", () => {
    const { container } = render(<AgentTraceSection trace={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows per-agent header and reveals tool calls on expand", () => {
    render(<AgentTraceSection trace={TRACE} />);
    expect(screen.getByText(/Market/)).toBeInTheDocument();
    expect(screen.queryByText("recent_transactions")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/Market/));
    expect(screen.getByText("recent_transactions")).toBeInTheDocument();
  });
});
