import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatCard from "./StatCard";

describe("StatCard", () => {
  it("renders label and value", () => {
    render(<StatCard label="Median PSF" value="$612 psf" />);
    expect(screen.getByText("Median PSF")).toBeInTheDocument();
    expect(screen.getByText("$612 psf")).toBeInTheDocument();
  });

  it("renders hint when provided", () => {
    render(<StatCard label="Txns" value="120" hint="last 24 months" />);
    expect(screen.getByText("last 24 months")).toBeInTheDocument();
  });

  it("omits hint when absent", () => {
    const { container } = render(<StatCard label="X" value="1" />);
    expect(container.textContent).not.toContain("undefined");
  });
});
