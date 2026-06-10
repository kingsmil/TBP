# Function Calling Implementation for AI Agents

## Overview

The AI agents now use **function calling** to dynamically invoke the same tools that manual mode uses, instead of receiving pre-fetched static data. This makes the agents more flexible and intelligent.

## What Changed

### 1. Agent Definitions Updated

**Before:** Agents used `prefetch` to receive static data in their system prompts.

**After:** Agents use `tool_names` to dynamically call tools during inference.

#### Files Modified:
- `backend/app/homeos/agents/market.py`
- `backend/app/homeos/agents/location.py`
- `backend/app/homeos/agents/risk.py`
- `backend/app/homeos/agents/questions.py`

#### Example Change (market.py):
```python
# BEFORE
market_definition = AgentDefinition(
    name="market",
    system_prompt="Given recent transaction data (in pre-fetched context), summarise...",
    tool_names=["transactions"],
    prefetch=["transactions"],  # Data injected as text
)

# AFTER
market_definition = AgentDefinition(
    name="market",
    system_prompt="Use the get_transactions() tool to fetch recent transaction data...",
    tool_names=["transactions"],  # Agent calls this tool dynamically
    prefetch=[],  # No pre-fetching needed
)
```

### 2. Evidence Model Enhanced

Added fields to `RiskEvidence` to store raw tool outputs:

```python
class RiskEvidence(BaseModel):
    appreciation: dict[str, Any] = Field(default_factory=dict)  # NEW
    future_mrt: dict[str, Any] = Field(default_factory=dict)    # NEW
    future_supply: dict[str, Any] = Field(default_factory=dict) # NEW
    accessibility: dict[str, Any] = Field(default_factory=dict) # NEW
    watchouts: list[str] = Field(default_factory=list)
    score_adjustment: float = 0.0
    narrative: str = ""
```

**File:** `backend/app/homeos/models/evidence.py`

### 3. Pipeline Simplified

The pipeline now lets agents do their own tool calling instead of manually prefetching and merging data.

**Before:**
```python
# Manually prefetch data
_, prefetched = agent_registry.build("market", repo, block_id, prefs)
txn_data = prefetched.get("transactions", {})

# Call agent just for narrative
output, _ = await _run_block_agent("market", repo, block_id, prefs, "Summarise...")
narrative = output.narrative

# Manually merge data
market_evidence = {**txn_data, "narrative": narrative}
```

**After:**
```python
# Agent calls get_transactions() itself and returns complete evidence
output, _ = await _run_block_agent(
    "market", repo, block_id, prefs,
    "Analyze market evidence using the available tools."
)
market_evidence = output.model_dump()
```

**File:** `backend/app/homeos/pipeline.py`

## Architecture

### Tool Registry System

The framework already had the infrastructure for function calling:

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Registry                          │
│                                                              │
│  registry.build(name, repo, block_id, prefs)                │
│    ├─ Fetches AgentDefinition                              │
│    ├─ Creates tools: [tool.as_tool(...) for tool in ...]   │
│    ├─ Builds Agent with tools attached                      │
│    └─ Returns (agent, prefetched_context)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Tool Adapters                          │
│                                                              │
│  class TransactionsTool(ToolAdapter):                       │
│    def fetch(repo, block_id, prefs) -> dict                 │
│    def as_tool(repo, block_id, prefs) -> Callable           │
│                                                              │
│  # as_tool() returns a function that the LLM can call       │
│  def get_transactions(flat_type=None) -> dict:              │
│      return self.fetch(...)                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Manual Mode Services                     │
│                                                              │
│  • app.services.search.search_blocks()                      │
│  • app.services.accessibility.block_accessibility()         │
│  • app.services.appreciation.appreciation()                 │
│  • app.services.future_dev.future_mrt/future_supply()       │
│  • app.services.stats.summarize()                           │
└─────────────────────────────────────────────────────────────┘
```

### Available Tools

| Tool Name | Function | Purpose |
|-----------|----------|---------|
| `transactions` | `get_transactions(flat_type=None)` | Fetch recent HDB resale transactions |
| `proximity` | `get_proximity()` | Get MRT distance and school count |
| `appreciation` | `get_appreciation()` | Get appreciation score and risk level |
| `future_dev` | `get_future_dev()` | Get future MRT and BTO supply data |
| `accessibility` | `get_accessibility()` | Get bus stop accessibility scores |
| `search` | `search_blocks_tool(flat_type, max_price, town)` | Search for HDB blocks |

### Agent Definitions

| Agent | Tools Available | What It Does |
|-------|----------------|--------------|
| `market` | `transactions` | Analyzes recent sales, computes budget fit |
| `location` | `proximity` | Evaluates MRT access and school proximity |
| `risk` | `appreciation`, `future_dev`, `accessibility` | Identifies risks, computes score adjustments |
| `questions` | `transactions`, `proximity` | Generates viewing questions based on data gaps |
| `profile` | (none) | Parses buyer preferences from text |

## How It Works

### 1. Agent Creation

```python
from app.homeos.wiring import setup, agent_registry

# Initialize registries (done at app startup)
setup()

# Build an agent with tools attached
agent, prefetched = agent_registry.build(
    "market",
    repo=repository,
    block_id=123,
    prefs={"flat_type": "4 ROOM", "max_price": 800000}
)
```

### 2. Tool Attachment

The `registry.build()` method (lines 100-103 in `registry.py`):

```python
tools = [
    self._tools.get(t).as_tool(repo=repo, block_id=block_id, prefs=prefs)
    for t in defn.tool_names
]

agent: Agent[Any, Any] = Agent(
    get_model(),
    output_type=defn.output_type,
    system_prompt=system_prompt,
    tools=tools,  # ← Tools attached here
)
```

### 3. Agent Execution

```python
# Agent decides when/how to call tools
result = await agent.run("Analyze market evidence using available tools.")

# Returns structured output
market_evidence = result.output  # MarketEvidence instance
print(market_evidence.transaction_count)
print(market_evidence.median_price)
print(market_evidence.narrative)
```

### 4. Tool Execution Flow

```
User Prompt
    │
    ▼
┌─────────────────┐
│  AI Agent       │  "I need transaction data"
│  (market)       │
└────────┬────────┘
         │ calls get_transactions(flat_type="4 ROOM")
         ▼
┌─────────────────┐
│ TransactionsTool│  1. Filters transactions by flat_type
│ .as_tool()      │  2. Computes median_price, median_psf
└────────┬────────┘  3. Determines budget_signal
         │           4. Returns structured dict
         ▼
┌─────────────────┐
│  Manual Mode    │  Actual data fetching logic
│  Service Layer  │  (repo.transactions_for_block)
└─────────────────┘
         │
         ▼
    Returns data to agent
         │
         ▼
┌─────────────────┐
│  AI Agent       │  Generates narrative + returns
│  (market)       │  complete MarketEvidence
└─────────────────┘
```

## Mock Mode vs AI Mode

The system supports both modes:

### Mock Mode (No LLM)
- Uses `is_mock_mode()` to detect
- Manually prefetches data via `registry.build()`
- Computes results with deterministic logic
- Uses mock narratives
- Fast, no API costs

### AI Mode (With LLM)
- Agents call tools dynamically via function calling
- LLM decides when to call which tools
- LLM generates narratives
- More flexible, handles edge cases better

The pipeline (`app/homeos/pipeline.py`) handles both:

```python
if mock:
    # Manual prefetch + mock narrative
    _, prefetched = agent_registry.build("market", repo, block_id, prefs)
    txn_data = prefetched["transactions"]
    narrative = mock_market_narrative(txn_data, prefs)
    market_evidence = {**txn_data, "narrative": narrative}
else:
    # Let agent call tools dynamically
    output, _ = await _run_block_agent("market", repo, block_id, prefs, "Analyze...")
    market_evidence = output.model_dump()
```

## Testing

Run the test script to see function calling in action:

```bash
cd backend
python test_agent_function_calling.py
```

This demonstrates:
1. ✅ Agents calling tools dynamically
2. ✅ Tools returning structured data
3. ✅ Agents generating narratives
4. ✅ Complete evidence objects returned

## Benefits

### Before (Pre-fetch Only)
- ❌ Data fetched once, agent can't refetch
- ❌ Agent just formats pre-fetched data
- ❌ Limited flexibility
- ❌ Manual data merging in pipeline

### After (Function Calling)
- ✅ Agent decides when to call tools
- ✅ Agent can call multiple tools
- ✅ Agent analyzes raw data dynamically
- ✅ Cleaner pipeline code
- ✅ More intelligent behavior
- ✅ Uses same tools as manual mode

## Configuration

### LLM Provider Setup

Set environment variables:

```bash
# Vercel AI Gateway (default)
export AI_GATEWAY_API_KEY="your_key"
export LLM_MODEL="openai/gpt-5.4-nano"

# Anthropic
export LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="your_key"
export LLM_MODEL="claude-haiku-4-5-20251001"

# OpenRouter
export LLM_PROVIDER="openrouter"
export OPENROUTER_API_KEY="your_key"

# Test Mode (no API calls)
export LLM_PROVIDER="test"
```

See `backend/app/homeos/framework/registry.py` for provider details.

## Next Steps

### Potential Enhancements

1. **Add More Tools**: Create adapters for other services
2. **Tool Chaining**: Let agents call tools in sequence
3. **Caching**: Cache tool results within a session
4. **Streaming**: Stream tool call progress to frontend
5. **Error Handling**: Better fallbacks when tools fail
6. **Observability**: Log which tools are called and why

### Example: Adding a New Tool

```python
# 1. Create tool adapter
class AnalyticsTool(ToolAdapter):
    name = "analytics"
    description = "Fetch price trends and analytics"

    def fetch(self, repo, block_id, prefs):
        from app.services.analytics import block_analytics
        return block_analytics(repo, block_id) or {}

    def as_tool(self, repo, block_id, prefs):
        def get_analytics():
            """Fetch price trends for the current block."""
            return self.fetch(repo, block_id, prefs)
        return get_analytics

# 2. Register in wiring.py
from app.homeos.tools.analytics import AnalyticsTool
tool_registry.register(AnalyticsTool(mock=mock))

# 3. Add to agent definition
market_definition = AgentDefinition(
    name="market",
    tool_names=["transactions", "analytics"],  # ← Add here
    ...
)
```

## Summary

The AI agents now use **function calling** to dynamically access the same tools that manual mode uses. The framework was already in place (`ToolRegistry`, `AgentRegistry`, `ToolAdapter.as_tool()`), but agents were only using `prefetch`. By moving tools from `prefetch` to `tool_names`, agents can now call tools intelligently during inference, making them much more powerful and flexible.
