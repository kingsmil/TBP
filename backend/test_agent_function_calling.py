"""Test script to demonstrate AI agents using function calling with manual mode tools.

This script shows how the updated agent framework enables AI agents to dynamically
call the same tools that manual mode uses, rather than just receiving pre-fetched data.

Usage:
    python test_agent_function_calling.py
"""
import asyncio
import logging
import os

# Set up minimal env for testing
os.environ.setdefault("DATABASE_URL", "")  # Use mock mode
os.environ.setdefault("LLM_PROVIDER", "test")  # Use test model for demo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_market_agent_with_function_calling():
    """Test the market agent calling get_transactions() tool."""
    from app.homeos.wiring import setup, agent_registry
    from app.repositories.memory import MemoryRepository

    # Initialize the registry
    setup()

    # Create a test repository with some data
    repo = MemoryRepository()

    # Test with block_id=1 (should exist in memory repo)
    block_id = 1
    prefs = {
        "flat_type": "4 ROOM",
        "max_price": 800000,
        "risk_tolerance": "low"
    }

    logger.info("=" * 60)
    logger.info("Testing Market Agent with Function Calling")
    logger.info("=" * 60)

    # Build the agent - this attaches the transactions tool
    agent, prefetched = agent_registry.build(
        "market",
        repo=repo,
        block_id=block_id,
        prefs=prefs
    )

    logger.info(f"Agent built successfully")
    logger.info(f"Prefetched data: {prefetched}")  # Should be empty now
    logger.info(f"Tools available: {[tool.__name__ for tool in agent.tools]}")

    # Run the agent - it will call get_transactions() during inference
    result = await agent.run("Analyze market evidence for this block using the available tools.")

    logger.info(f"\nAgent output type: {type(result.output)}")
    logger.info(f"Market Evidence: {result.output.model_dump()}")
    logger.info(f"Narrative: {result.output.narrative}")

    return result.output


async def test_location_agent_with_function_calling():
    """Test the location agent calling get_proximity() tool."""
    from app.homeos.wiring import agent_registry
    from app.repositories.memory import MemoryRepository

    repo = MemoryRepository()
    block_id = 1
    prefs = {}

    logger.info("\n" + "=" * 60)
    logger.info("Testing Location Agent with Function Calling")
    logger.info("=" * 60)

    agent, _ = agent_registry.build("location", repo=repo, block_id=block_id, prefs=prefs)

    logger.info(f"Tools available: {[tool.__name__ for tool in agent.tools]}")

    result = await agent.run("Analyze location and connectivity for this block using the available tools.")

    logger.info(f"\nLocation Evidence: {result.output.model_dump()}")
    logger.info(f"Narrative: {result.output.narrative}")

    return result.output


async def test_risk_agent_with_function_calling():
    """Test the risk agent calling multiple tools (appreciation, future_dev, accessibility)."""
    from app.homeos.wiring import agent_registry
    from app.repositories.memory import MemoryRepository

    repo = MemoryRepository()
    block_id = 1
    prefs = {"risk_tolerance": "low"}

    logger.info("\n" + "=" * 60)
    logger.info("Testing Risk Agent with Function Calling")
    logger.info("=" * 60)

    agent, _ = agent_registry.build("risk", repo=repo, block_id=block_id, prefs=prefs)

    logger.info(f"Tools available: {[tool.__name__ for tool in agent.tools]}")

    result = await agent.run(
        f"Analyze risk factors for this block. Buyer risk_tolerance: {prefs.get('risk_tolerance', 'low')}"
    )

    logger.info(f"\nRisk Evidence: {result.output.model_dump()}")
    logger.info(f"Watchouts: {result.output.watchouts}")
    logger.info(f"Score Adjustment: {result.output.score_adjustment}")
    logger.info(f"Narrative: {result.output.narrative}")

    return result.output


async def main():
    """Run all tests."""
    logger.info("\n🚀 Testing AI Agents with Function Calling\n")

    try:
        market_result = await test_market_agent_with_function_calling()
        location_result = await test_location_agent_with_function_calling()
        risk_result = await test_risk_agent_with_function_calling()

        logger.info("\n" + "=" * 60)
        logger.info("✅ All tests completed successfully!")
        logger.info("=" * 60)
        logger.info("\nKey Improvements:")
        logger.info("1. Agents now use function calling instead of pre-fetched data")
        logger.info("2. Agents dynamically call the same tools that manual mode uses")
        logger.info("3. Tools are attached via registry.build() automatically")
        logger.info("4. Mock mode still works with pre-fetched data fallback")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
