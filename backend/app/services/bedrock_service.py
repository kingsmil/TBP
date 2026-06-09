"""Amazon Bedrock Agent inference wrapper.

Uses bedrock:InvokeAgent (agent runtime) instead of bedrock:InvokeModel so
it works in the Kiro sandbox where direct model invocation is blocked.

The Bedrock Agent was provisioned by infrastructure/bedrock/setup_agent.py.
Set these in .env after running that script:
  AWS_BEDROCK_AGENT_ID=...
  AWS_BEDROCK_AGENT_ALIAS_ID=...

Invocation styles:
  invoke_agent_text()   — single-turn, returns full response string
  invoke_agent_stream() — yields text chunks (generator) for SSE routes
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator

from app.core.aws_config import get_bedrock_agent_runtime

AGENT_ID       = os.getenv("AWS_BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.getenv("AWS_BEDROCK_AGENT_ALIAS_ID", "TSTALIASID")


class BedrockAgentUnavailable(RuntimeError):
    """Raised when agent IDs are not configured."""


def _require_agent() -> tuple[str, str]:
    if not AGENT_ID:
        raise BedrockAgentUnavailable(
            "AWS_BEDROCK_AGENT_ID is not set. "
            "Run infrastructure/bedrock/setup_agent.py first."
        )
    return AGENT_ID, AGENT_ALIAS_ID


def _new_session() -> str:
    return str(uuid.uuid4())


def invoke_agent_text(
    user_prompt: str,
    session_id: str | None = None,
) -> str:
    """Single-turn agent invocation; returns the full response as a string."""
    agent_id, alias_id = _require_agent()
    client = get_bedrock_agent_runtime()

    resp = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id or _new_session(),
        inputText=user_prompt,
    )

    chunks: list[str] = []
    for event in resp["completion"]:
        if "chunk" in event:
            chunks.append(event["chunk"]["bytes"].decode("utf-8"))

    return "".join(chunks)


def invoke_agent_stream(
    user_prompt: str,
    session_id: str | None = None,
) -> Generator[str, None, None]:
    """Streaming agent invocation; yields text chunks as they arrive."""
    agent_id, alias_id = _require_agent()
    client = get_bedrock_agent_runtime()

    resp = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id or _new_session(),
        inputText=user_prompt,
        streamingConfigurations={"streamFinalResponse": True},
    )

    for event in resp["completion"]:
        if "chunk" in event:
            yield event["chunk"]["bytes"].decode("utf-8")


def is_available() -> bool:
    return bool(AGENT_ID)
