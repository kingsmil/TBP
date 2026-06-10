import type { AgentEvent, AgentKey, AgentProgressMap, BlockNarrativeMap } from "../types";

const AGENT_KEYS: AgentKey[] = ["market", "location", "lifestyle", "risk"];

function isAgentKey(agent: string | undefined): agent is AgentKey {
  return AGENT_KEYS.includes(agent as AgentKey);
}

export function deriveAgentProgress(events: AgentEvent[]): AgentProgressMap {
  const map: AgentProgressMap = new Map(
    AGENT_KEYS.map((k) => [k, { status: "idle" as const, blocksDone: 0, snippets: [] }]),
  );

  for (const ev of events) {
    if (!isAgentKey(ev.agent) || ev.block_id == null) continue;
    const entry = map.get(ev.agent)!;

    if (ev.event === "agent_start") {
      map.set(ev.agent, { ...entry, status: "running" });
    } else if (ev.event === "agent_summary" && ev.narrative) {
      map.set(ev.agent, {
        ...entry,
        snippets: [...entry.snippets, { block_id: ev.block_id, narrative: ev.narrative }],
      });
    } else if (ev.event === "agent_done") {
      const current = map.get(ev.agent)!;
      map.set(ev.agent, { ...current, status: "idle", blocksDone: current.blocksDone + 1 });
    }
  }

  return map;
}

export function deriveBlockNarratives(events: AgentEvent[]): BlockNarrativeMap {
  const map: BlockNarrativeMap = new Map();

  for (const ev of events) {
    if (ev.event !== "agent_summary" || !isAgentKey(ev.agent) || ev.block_id == null || !ev.narrative) continue;
    if (!map.has(ev.block_id)) map.set(ev.block_id, new Map());
    map.get(ev.block_id)!.set(ev.agent, ev.narrative);
  }

  return map;
}
