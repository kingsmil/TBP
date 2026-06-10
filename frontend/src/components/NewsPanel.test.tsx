import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import NewsPanel from "./NewsPanel";

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
}));

import { useQuery } from "@tanstack/react-query";

const mockUseQuery = vi.mocked(useQuery);

beforeEach(() => {
  mockUseQuery.mockReset();
});

describe("NewsPanel", () => {
  it("shows loading state", () => {
    mockUseQuery.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
    } as ReturnType<typeof useQuery>);

    render(<NewsPanel />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseQuery.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
    } as ReturnType<typeof useQuery>);

    render(<NewsPanel />);

    expect(screen.getByText(/Failed to load news/)).toBeInTheDocument();
  });

  it("shows empty state", () => {
    mockUseQuery.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
    } as ReturnType<typeof useQuery>);

    render(<NewsPanel />);

    expect(screen.getByText("No news found")).toBeInTheDocument();
  });

  it("renders news items with title, domain and date", () => {
    mockUseQuery.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        {
          title: "HDB resale prices hit new high",
          url: "https://straitstimes.com/hdb",
          published_date: "2026-06-01T00:00:00Z",
          domain: "straitstimes.com",
        },
      ],
    } as ReturnType<typeof useQuery>);

    render(<NewsPanel />);

    const link = screen.getByRole("link", { name: /HDB resale prices hit new high/ });
    expect(link).toHaveAttribute("href", "https://straitstimes.com/hdb");
    expect(link).toHaveAttribute("target", "_blank");
    expect(screen.getByText(/straitstimes\.com/)).toBeInTheDocument();
    expect(screen.getByText(/Jun 2026/)).toBeInTheDocument();
  });

  it("renders multiple items", () => {
    mockUseQuery.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { title: "Article A", url: "https://a.com/1", published_date: null, domain: "a.com" },
        { title: "Article B", url: "https://b.com/2", published_date: null, domain: "b.com" },
      ],
    } as ReturnType<typeof useQuery>);

    render(<NewsPanel />);

    expect(screen.getByText("Article A")).toBeInTheDocument();
    expect(screen.getByText("Article B")).toBeInTheDocument();
  });
});
