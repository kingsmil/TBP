"""One-shot script to create the HDB Match Bedrock Agent.

Run once to provision the agent, then set the output IDs in .env:
  AWS_BEDROCK_AGENT_ID=...
  AWS_BEDROCK_AGENT_ALIAS_ID=...

Usage:
  cd C:\\Users\\tkhta\\Documents\\GitHub\\TBP
  python infrastructure/bedrock/setup_agent.py

The script is idempotent — re-running it skips creation if the agent
already exists (matched by name).
"""
from __future__ import annotations

import json
import time
import os
import boto3

REGION      = os.getenv("AWS_REGION", "us-west-2")
ACCOUNT_ID  = os.getenv("AWS_ACCOUNT_ID", "274946909740")
AGENT_NAME  = "hdb-match-homeos"
ROLE_NAME   = "hdb-match-bedrock-agent-role"
# Claude Haiku 3 is available in this sandbox account
MODEL_ID    = "anthropic.claude-3-haiku-20240307-v1:0"

iam = boto3.client("iam",            region_name=REGION)
ba  = boto3.client("bedrock-agent",  region_name=REGION)


AGENT_INSTRUCTIONS = """You are HomeOS, an AI advisor for Singapore HDB homebuyers.

You help buyers make data-driven decisions about which HDB block and estate to buy.
You have access to analytics including:
- Price per square foot (PSF) trends by estate and block
- MRT and bus accessibility scores
- School proximity data
- Lease remaining and appreciation potential
- Commute time to user-specified workplaces

When a user describes their household situation, you:
1. Parse their budget, flat type preference, and lifestyle priorities
2. Identify the top matching estates based on their criteria
3. Summarise market evidence, location evidence, and risk factors
4. Generate 4-6 due-diligence questions they should ask before viewing

Always be specific, cite data where possible, and be honest about uncertainty.
Never give financial advice — frame insights as data-driven observations."""


# ── Step 1: IAM execution role ────────────────────────────────────────────────

def ensure_agent_role() -> str:
    """Create (or find existing) IAM role for Bedrock Agent execution."""
    try:
        role = iam.get_role(RoleName=ROLE_NAME)
        role_arn = role["Role"]["Arn"]
        print(f"  IAM role already exists: {role_arn}")
        return role_arn
    except iam.exceptions.NoSuchEntityException:
        pass

    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": ACCOUNT_ID},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:agent/*"}
            }
        }]
    })

    role = iam.create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=trust,
        Description="Execution role for HDB Match Bedrock Agent",
    )
    role_arn = role["Role"]["Arn"]
    print(f"  Created IAM role: {role_arn}")

    # Attach managed policy — Bedrock Agents needs InvokeModel on its own behalf
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="bedrock-invoke",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                "Resource": f"arn:aws:bedrock:{REGION}::foundation-model/*"
            }]
        })
    )
    print("  Attached InvokeModel policy to role")
    time.sleep(10)   # IAM propagation
    return role_arn


# ── Step 2: Bedrock Agent ─────────────────────────────────────────────────────

def ensure_agent(role_arn: str) -> str:
    """Create (or find existing) Bedrock Agent, return agent_id."""
    agents = ba.list_agents().get("agentSummaries", [])
    for a in agents:
        if a["agentName"] == AGENT_NAME:
            agent_id = a["agentId"]
            print(f"  Agent already exists: {agent_id}")
            return agent_id

    resp = ba.create_agent(
        agentName=AGENT_NAME,
        agentResourceRoleArn=role_arn,
        foundationModel=MODEL_ID,
        instruction=AGENT_INSTRUCTIONS,
        description="HomeOS — HDB buyer advisor agent for HDB Match",
        idleSessionTTLInSeconds=1800,
    )
    agent_id = resp["agent"]["agentId"]
    print(f"  Created agent: {agent_id}")
    return agent_id


# ── Step 3: Prepare (compile) the agent ──────────────────────────────────────

def prepare_agent(agent_id: str) -> None:
    status = ba.get_agent(agentId=agent_id)["agent"]["agentStatus"]
    if status == "PREPARED":
        print(f"  Agent already PREPARED")
        return

    print("  Preparing agent (compiling)…")
    ba.prepare_agent(agentId=agent_id)

    for _ in range(20):
        time.sleep(5)
        status = ba.get_agent(agentId=agent_id)["agent"]["agentStatus"]
        print(f"    status: {status}")
        if status == "PREPARED":
            break
        if status == "FAILED":
            raise RuntimeError("Agent preparation failed")


# ── Step 4: Agent alias ───────────────────────────────────────────────────────

def ensure_alias(agent_id: str) -> str:
    aliases = ba.list_agent_aliases(agentId=agent_id).get("agentAliasSummaries", [])
    for a in aliases:
        if a["agentAliasName"] == "prod":
            alias_id = a["agentAliasId"]
            print(f"  Alias already exists: {alias_id}")
            return alias_id

    resp = ba.create_agent_alias(
        agentId=agent_id,
        agentAliasName="prod",
        description="Production alias for HDB Match",
    )
    alias_id = resp["agentAlias"]["agentAliasId"]
    print(f"  Created alias: {alias_id}")
    return alias_id


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n[1/4] Ensuring IAM execution role…")
    role_arn = ensure_agent_role()

    print("\n[2/4] Ensuring Bedrock Agent…")
    agent_id = ensure_agent(role_arn)

    print("\n[3/4] Preparing agent…")
    prepare_agent(agent_id)

    print("\n[4/4] Ensuring agent alias…")
    alias_id = ensure_alias(agent_id)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Setup complete. Add these to your .env file:

  AWS_BEDROCK_AGENT_ID={agent_id}
  AWS_BEDROCK_AGENT_ALIAS_ID={alias_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
