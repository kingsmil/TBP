import { afterEach, describe, expect, it, vi } from "vitest";
import { getCase, getCases, investigateStream } from "./api";

describe("homeos cases api", () => {
  afterEach(() => vi.restoreAllMocks());

  it("getCases calls /homeos/cases", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [],
      }),
    );

    await getCases();

    expect(fetch).toHaveBeenCalledWith("/api/homeos/cases");
  });

  it("getCase calls /homeos/cases/:id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ case_id: "abc", pipeline: [], shortlist: [] }),
      }),
    );

    await getCase("abc");

    expect(fetch).toHaveBeenCalledWith("/api/homeos/cases/abc");
  });

  it("investigateStream returns an async iterable of events", async () => {
    const mockStream = new ReadableStream({
      start(ctrl) {
        ctrl.enqueue(
          new TextEncoder().encode(
            'data: {"event":"agent_start","agent":"profile","block_id":null}\n\n',
          ),
        );
        ctrl.enqueue(
          new TextEncoder().encode(
            'data: {"event":"case_done","case_id":"x","shortlist":[]}\n\n',
          ),
        );
        ctrl.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, body: mockStream }));

    const events: unknown[] = [];
    for await (const evt of investigateStream("Family 800k.", 1)) {
      events.push(evt);
    }

    expect(events).toHaveLength(2);
    expect((events[0] as { event: string }).event).toBe("agent_start");
  });
});
