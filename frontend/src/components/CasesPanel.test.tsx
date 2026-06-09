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

describe("CasesPanel", () => {
  it("renders new case input and investigate button", () => {
    render(
      <CasesPanel
        cases={[]}
        activeCaseId={null}
        onNewCase={vi.fn()}
        onSelectCase={vi.fn()}
      />,
    );

    expect(screen.getByPlaceholderText(/household/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /investigate/i })).toBeInTheDocument();
  });

  it("calls onNewCase with profile text when investigate is clicked", () => {
    const onNewCase = vi.fn();
    render(
      <CasesPanel
        cases={[]}
        activeCaseId={null}
        onNewCase={onNewCase}
        onSelectCase={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(/household/i), {
      target: { value: "Family 4 room 800k schools." },
    });
    fireEvent.click(screen.getByRole("button", { name: /investigate/i }));

    expect(onNewCase).toHaveBeenCalledWith("Family 4 room 800k schools.");
  });

  it("renders case list with status and shortlist count", () => {
    render(
      <CasesPanel
        cases={[mockCase]}
        activeCaseId={null}
        onNewCase={vi.fn()}
        onSelectCase={vi.fn()}
      />,
    );

    expect(screen.getByText("Family looking for 4 room under 800k.")).toBeInTheDocument();
    expect(screen.getByText("3 listings")).toBeInTheDocument();
  });

  it("highlights active case", () => {
    const { container } = render(
      <CasesPanel
        cases={[mockCase]}
        activeCaseId="abc-123"
        onNewCase={vi.fn()}
        onSelectCase={vi.fn()}
      />,
    );

    expect(container.querySelector("[data-active='true']")).not.toBeNull();
  });
});
