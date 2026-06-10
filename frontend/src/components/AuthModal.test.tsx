import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AuthModal from "./AuthModal";

vi.mock("../lib/api", () => ({
  apiLogin: vi.fn(),
  apiRegister: vi.fn(),
}));

describe("AuthModal", () => {
  it("separates the Pro requirement and shows Stripe attribution", () => {
    render(<AuthModal onSuccess={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByText("Free account gives access to Explore mode.")).toBeInTheDocument();
    expect(screen.getByText("AI mode requires a Pro subscription ($9.99/mo).")).toBeInTheDocument();
    expect(screen.getByText("Powered by")).toBeInTheDocument();
    expect(screen.getByText("stripe")).toBeInTheDocument();
  });
});
