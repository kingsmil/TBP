import { describe, expect, it } from "vitest";
import { deriveAgentProgress, deriveBlockNarratives } from "./agentProgress";
import type { AgentEvent } from "../types";

const events: AgentEvent[] = [
  { event: "agent_start", agent: "market", block_id: 10 },
  { event: "agent_summary", agent: "market", block_id: 10, narrative: "Market looks good." },
  { event: "agent_done", agent: "market", block_id: 10 },
  { event: "agent_start", agent: "location", block_id: 10 },
  { event: "agent_summary", agent: "location", block_id: 10, narrative: "MRT is close." },
  { event: "agent_start", agent: "market", block_id: 11 },
];

describe("deriveAgentProgress", () => {
  it("counts blocksDone per agent", () => {
    const map = deriveAgentProgress(events);
    expect(map.get("market")?.blocksDone).toBe(1);
    expect(map.get("location")?.blocksDone).toBe(0);
  });

  it("sets status=running for agent_start without agent_done", () => {
    const map = deriveAgentProgress(events);
    expect(map.get("location")?.status).toBe("running");
    expect(map.get("market")?.status).toBe("running");
  });

  it("collects snippets per agent", () => {
    const map = deriveAgentProgress(events);
    expect(map.get("market")?.snippets).toEqual([
      { block_id: 10, narrative: "Market looks good." },
    ]);
  });

  it("returns idle entry for agents with no events", () => {
    const map = deriveAgentProgress(events);
    expect(map.get("risk")).toEqual({ status: "idle", blocksDone: 0, snippets: [] });
  });
});

describe("deriveBlockNarratives", () => {
  it("indexes narratives by block_id then agent", () => {
    const map = deriveBlockNarratives(events);
    expect(map.get(10)?.get("market")).toBe("Market looks good.");
    expect(map.get(10)?.get("location")).toBe("MRT is close.");
  });

  it("returns empty map for empty events", () => {
    expect(deriveBlockNarratives([]).size).toBe(0);
  });
});
