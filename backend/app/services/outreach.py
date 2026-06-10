"""Prepare a WhatsApp outreach message for a specific active listing.

Message generation always works (mock or LLM). Delivery channels are
best-effort: the HDB portal rarely exposes agent contact publicly, so
whatsapp_url / email_url appear in the result only when the listing
actually carries a phone / email. The caller (UI) falls back to
copy-to-clipboard otherwise.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote

from app.homeos import case_store
from app.homeos.mock.agents import mock_outreach_message
from app.homeos.mock.tools import is_mock_mode
from app.repositories.base import Repository

_SG_COUNTRY_CODE = "65"


def sanitize_phone(raw: str | None) -> str | None:
    """Digits only, prefixed with the SG country code. None when unusable."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if digits.startswith(_SG_COUNTRY_CODE) and len(digits) == 10:
        return digits
    return _SG_COUNTRY_CODE + digits


def prepare_outreach_message(
    repo: Repository,
    listing_id: int,
    case_id: str | None = None,
    contact_name: str | None = None,
    availability: list[str] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    listing = repo.active_listing(listing_id)
    if listing is None:
        raise ValueError("listing not found")

    availability = [s.strip() for s in (availability or []) if s and s.strip()]

    avatar_summary: str | None = None
    if case_id:
        case = case_store.get_case(case_id)
        if case and case.get("avatar"):
            avatar_summary = case["avatar"].get("summary")

    if is_mock_mode():
        message = mock_outreach_message(listing, avatar_summary, contact_name, availability)
        questions: list[str] = []
    else:
        prox = repo.proximity(listing.block_id)
        mrt_m = prox.nearest_mrt_distance_m if prox else None
        prompt = (
            f"Unit: {listing.flat_type} at Blk {listing.block_number} "
            f"{listing.street_name} ({listing.town}), {listing.floor_area_sqm} sqm, "
            f"storey {listing.storey_range}, asking ${listing.price:,.0f}, "
            f"remaining lease {listing.remaining_lease}. "
            f"Listing blurb: {listing.description or 'n/a'}. "
            f"Nearest MRT: {f'{mrt_m:.0f}m' if mrt_m is not None else 'unknown'}. "
            f"Buyer name: {contact_name or 'not given'}. "
            f"Buyer profile: {avatar_summary or 'not given'}. "
            f"Availability: {'; '.join(availability) or 'not given'}. "
            f"Extra note from buyer: {note or 'none'}."
        )
        from app.services.homeos_ai_agents import outreach_agent
        result = asyncio.run(outreach_agent.run(prompt))
        message = result.output.message or mock_outreach_message(
            listing, avatar_summary, contact_name, availability)
        questions = result.output.questions

    out: dict[str, Any] = {
        "listing_id": listing.listing_id,
        "message": message,
        "questions": questions,
    }
    phone = sanitize_phone(listing.agent_phone)
    if phone:
        out["whatsapp_url"] = f"https://wa.me/{phone}?text={quote(message)}"
    if listing.agent_email:
        subject = quote(f"Enquiry: Blk {listing.block_number} {listing.street_name}")
        out["email_url"] = f"mailto:{listing.agent_email}?subject={subject}&body={quote(message)}"
    if listing.agent_name:
        out["agent_name"] = listing.agent_name
    return out
