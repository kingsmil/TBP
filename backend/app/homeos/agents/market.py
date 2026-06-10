from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import MarketEvidence

market_definition = AgentSpec(
    name="market",
    description="Summarises recent transaction data to assess budget fit and market activity for a block.",
    system_prompt=(
        "You are an HDB market analyst. "
        "Given recent transaction data and a buyer's budget (in pre-fetched context), "
        "summarise the market evidence. "
        "Write a one-sentence narrative (max 30 words) describing what the data means for this buyer. "
        "Copy structured fields (transaction_count, median_price, median_psf, window_months, "
        "budget_signal, confidence) directly from the pre-fetched context."
    ),
    output_type=MarketEvidence,
    tool_names=["transactions"],
    prefetch=["transactions"],
)
