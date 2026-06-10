"""Resolve a block by free-text address and list the agents marketing it.

The FE sends an address like "104A Bidadari Pk Dr"; we split it into block
number + street, resolve via the same street normalization the listings
ingester uses, then group that block's active listings by agent contact.
Owner-listed units (no public contact) are returned separately so the UI
can still show them with the copy-message fallback.
"""
from __future__ import annotations

from typing import Any

from app.core.models import ActiveListing
from app.data.hdb_listings import normalize_street
from app.repositories.base import Repository


def parse_address(address: str) -> tuple[str, str]:
    """Split '104A Bidadari Pk Dr' into ('104A', 'Bidadari Pk Dr')."""
    parts = address.strip().split()
    if len(parts) < 2:
        raise ValueError("address must be '<block number> <street name>'")
    return parts[0].upper(), " ".join(parts[1:])


def _listing_summary(a: ActiveListing) -> dict[str, Any]:
    d = {
        "listing_id": a.listing_id,
        "price": a.price,
        "flat_type": a.flat_type,
        "floor_area_sqm": a.floor_area_sqm,
        "floor_area_sqft": round(a.floor_area_sqft, 1),
        "storey_range": a.storey_range,
        "remaining_lease": a.remaining_lease,
    }
    if a.description:
        d["description"] = a.description
    return d


def find_block_agents(repo: Repository, address: str) -> dict[str, Any] | None:
    """Block + its agents for an address, or None when no block matches."""
    block_number, street = parse_address(address)
    want = normalize_street(street)
    block = next(
        (b for b in repo.blocks_by_number(block_number)
         if normalize_street(b.street_name) == want),
        None,
    )
    if block is None:
        return None

    listings = sorted(repo.active_listings_for_block(block.block_id),
                      key=lambda a: a.price)
    agents: dict[str, dict[str, Any]] = {}
    owner_listings: list[dict[str, Any]] = []
    for a in listings:
        key = a.agent_phone or a.agent_email or a.agent_name
        if not key:
            owner_listings.append(_listing_summary(a))
            continue
        entry = agents.setdefault(key, {
            "agent_name": a.agent_name,
            "agent_phone": a.agent_phone,
            "agent_email": a.agent_email,
            "agency_name": a.agency_name,
            "listings": [],
        })
        entry["listings"].append(_listing_summary(a))

    return {
        "block": {
            "block_id": block.block_id,
            "block_number": block.block_number,
            "street_name": block.street_name,
            "town": block.town,
        },
        "agents": list(agents.values()),
        "owner_listings": owner_listings,
        "listing_count": len(listings),
    }
