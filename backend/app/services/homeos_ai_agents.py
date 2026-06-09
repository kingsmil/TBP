"""Pydantic AI agent definitions for HomeOS.

Hackathon requirement: use Vercel AI Gateway as the LLM provider.

Auto-detection (no LLM_PROVIDER needed):
  Set AI_GATEWAY_API_KEY → Vercel AI Gateway is used automatically.
  Set LLM_MODEL to any gateway model (default: google/gemini-2.0-flash).
  Model format: "provider/model-name". Full list: vercel.com/ai-gateway/models

Explicit overrides via LLM_PROVIDER:
  vercel     — Vercel AI Gateway (same as auto-detect, explicit)
  bedrock    — Amazon Bedrock (AWS_BEDROCK_MODEL_ID + IAM credentials required)
  anthropic  — Direct Anthropic SDK (ANTHROPIC_API_KEY required)
  openrouter — OpenRouter (OPENROUTER_API_KEY required)
  test       — TestModel, no key needed (used in CI and unit tests)
"""
from __future__ import annotations

import os

from pydantic_ai import Agent
from pydantic_ai.models import Model

from app.services.homeos_ai_models import (
    AgentQuestions,
    HomeOSAvatar,
    LocationEvidence,
    MarketEvidence,
    RiskEvidence,
)

_VERCEL_BASE_URL = "https://ai-gateway.vercel.sh/v1"
_DEFAULT_GATEWAY_MODEL = "google/gemini-2.0-flash"


def get_model() -> Model:
    # Vercel AI Gateway auto-activates when the key is present.
    gateway_key = os.getenv("AI_GATEWAY_API_KEY", "")
    provider = os.getenv("LLM_PROVIDER", "vercel" if gateway_key else "test")
    model_name = os.getenv("LLM_MODEL", _DEFAULT_GATEWAY_MODEL)

    if provider in ("vercel",) or (provider == "test" and gateway_key):
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(
            model_name,
            provider=OpenAIProvider(
                base_url=_VERCEL_BASE_URL,
                api_key=gateway_key,
            ),
        )

    if provider == "bedrock":
        # Amazon Bedrock Agent — uses bedrock:InvokeAgent (not InvokeModel).
        # The sandbox blocks InvokeModel on foundation models directly, but
        # InvokeAgent is allowed because the agent's own IAM role makes the
        # underlying model call, not our WSParticipantRole.
        #
        # pydantic-ai structured output is not available via InvokeAgent, so
        # the bedrock provider returns TestModel here and the actual agent call
        # is made by bedrock_service.invoke_agent_text() in the homeos routes.
        from pydantic_ai.models.test import TestModel
        return TestModel()

    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        return AnthropicModel(os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001"))

    if provider == "openrouter":
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIModel(
            model_name,
            provider=OpenAIProvider(
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                api_key=os.getenv("OPENROUTER_API_KEY", ""),
            ),
        )

    from pydantic_ai.models.test import TestModel
    return TestModel()


profile_agent: Agent[None, HomeOSAvatar] = Agent(
    get_model(),
    output_type=HomeOSAvatar,
    system_prompt=(
        "You are a Singapore HDB buyer advisor. "
        "Parse the household description into structured buyer preferences. "
        "Return a complete HomeOSAvatar with label, buyer_type, summary, and preferences."
    ),
)

market_agent: Agent[None, MarketEvidence] = Agent(
    get_model(),
    output_type=MarketEvidence,
    system_prompt=(
        "You are an HDB market analyst. "
        "Given recent transaction data and a buyer's budget, summarise the market evidence. "
        "Write a one-sentence narrative (max 30 words) describing what the data means for this buyer."
    ),
)

location_agent: Agent[None, LocationEvidence] = Agent(
    get_model(),
    output_type=LocationEvidence,
    system_prompt=(
        "You are an HDB location analyst. "
        "Given MRT distance and school proximity data, summarise the location evidence. "
        "Write a one-sentence narrative (max 30 words) describing the connectivity for this buyer."
    ),
)

risk_agent: Agent[None, RiskEvidence] = Agent(
    get_model(),
    output_type=RiskEvidence,
    system_prompt=(
        "You are an HDB risk analyst. "
        "Given appreciation score, future supply, and accessibility data, identify watchouts. "
        "Write a one-sentence narrative (max 30 words) summarising the risk profile."
    ),
)

questions_agent: Agent[None, AgentQuestions] = Agent(
    get_model(),
    output_type=AgentQuestions,
    system_prompt=(
        "You are an HDB buyer advocate. "
        "Given the evidence from market, location, and risk agents, generate 4-6 due-diligence "
        "questions the buyer should ask the real-estate agent before viewing. "
        "Write a one-sentence narrative summarising why these questions matter."
    ),
)
