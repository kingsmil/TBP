from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import MarketEvidence

market_definition = AgentSpec(
    name="market",
    description="Summarises recent transaction data to assess budget fit and market activity for a block.",
    system_prompt=(
        "You are an HDB market analyst. "
        "Use the get_transactions() tool to fetch recent transaction data for the block. "
        "Analyze the data against the buyer's budget to determine market fit. "
        "Write a one-sentence narrative (max 30 words) describing what the data means for this buyer. "
        "Return all fields: transaction_count, median_price, median_psf, window_months, "
        "budget_signal, confidence, and narrative."
    ),
    output_type=MarketEvidence,
    tool_names=["transactions"],
    prefetch=[],
)
