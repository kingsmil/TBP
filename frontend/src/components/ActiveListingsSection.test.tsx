import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ActiveListingsSection from "./ActiveListingsSection";
import type { ActiveListing } from "../types";

const baseListing: ActiveListing = {
  listing_id: 40661,
  block_id: 1,
  block_number: "126A",
  street_name: "KIM TIAN RD",
  postal_code: "161126",
  town: "Bukit Merah",
  price: 1330000,
  flat_type: "4-Room",
  floor_area_sqm: 93,
  floor_area_sqft: 1001.0,
  storey_range: "More than 30",
  remaining_lease: "85 years 8 months",
  description: "Rare top-floor gem",
  managed_by_agent: false,
  last_updated: "2026-06-10 01:07:50",
};

const getBlockListings = vi.fn();
const prepareOutreachMessage = vi.fn();

vi.mock("../lib/api", () => ({
  getBlockListings: (blockId: number) => getBlockListings(blockId),
  prepareOutreachMessage: (id: number, body: unknown) => prepareOutreachMessage(id, body),
}));

describe("ActiveListingsSection", () => {
  beforeEach(() => {
    getBlockListings.mockReset();
  });

  it("renders listing count and card details", async () => {
    getBlockListings.mockResolvedValue({
      count: 2,
      listings: [baseListing, { ...baseListing, listing_id: 2, price: 900000 }],
    });
    render(<ActiveListingsSection blockId={1} />);
    await waitFor(() =>
      expect(screen.getByText(/2 units listed in this block/i)).toBeInTheDocument(),
    );
    expect(screen.getAllByText(/4-Room/)).toHaveLength(2);
    expect(screen.getAllByText(/85 years 8 months/)).toHaveLength(2);
  });

  it("omits the agent line when agent details are absent", async () => {
    getBlockListings.mockResolvedValue({ count: 1, listings: [baseListing] });
    render(<ActiveListingsSection blockId={1} />);
    await waitFor(() =>
      expect(screen.getByText(/1 unit listed in this block/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/agent/i)).not.toBeInTheDocument();
  });

  it("shows the agent line when agent details are present", async () => {
    getBlockListings.mockResolvedValue({
      count: 1,
      listings: [
        { ...baseListing, agent_name: "Jane Tan", agency_name: "PropNex" },
      ],
    });
    render(<ActiveListingsSection blockId={1} />);
    await waitFor(() => expect(screen.getByText(/Jane Tan/)).toBeInTheDocument());
    expect(screen.getByText(/PropNex/)).toBeInTheDocument();
  });

  it("prepares an outreach message with copy fallback when no phone", async () => {
    const { fireEvent } = await import("@testing-library/react");
    getBlockListings.mockResolvedValue({ count: 1, listings: [baseListing] });
    prepareOutreachMessage.mockResolvedValue({
      listing_id: 40661,
      message: "Hi! I saw your 4-Room listing at Blk 126A KIM TIAN RD…",
      questions: [],
    });
    render(<ActiveListingsSection blockId={1} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /prepare message/i })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /prepare message/i }));
    await waitFor(() =>
      expect(screen.getByText(/I saw your 4-Room listing/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /copy message/i })).toBeInTheDocument();
    expect(screen.queryByText(/open in whatsapp/i)).not.toBeInTheDocument();
    expect(screen.getByText(/paste this message/i)).toBeInTheDocument();
  });

  it("shows the WhatsApp deep-link when the listing has a phone", async () => {
    const { fireEvent } = await import("@testing-library/react");
    getBlockListings.mockResolvedValue({ count: 1, listings: [baseListing] });
    prepareOutreachMessage.mockResolvedValue({
      listing_id: 40661,
      message: "Hi Jane!",
      questions: [],
      whatsapp_url: "https://wa.me/6591234567?text=Hi%20Jane",
    });
    render(<ActiveListingsSection blockId={1} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /prepare message/i })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /prepare message/i }));
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /open in whatsapp/i })).toHaveAttribute(
        "href",
        "https://wa.me/6591234567?text=Hi%20Jane",
      ),
    );
  });

  it("renders nothing when there are no listings", async () => {
    getBlockListings.mockResolvedValue({ count: 0, listings: [] });
    const { container } = render(<ActiveListingsSection blockId={1} />);
    await waitFor(() => expect(getBlockListings).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
