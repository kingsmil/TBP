"""Typed output for the WhatsApp outreach agent."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OutreachMessage(BaseModel):
    """A ready-to-send WhatsApp message to a listing's seller/agent."""
    message: str = ""
    questions: list[str] = Field(default_factory=list)
