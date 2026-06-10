from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import AgentQuestions

questions_definition = AgentSpec(
    name="questions",
    description="Generates 4–6 due-diligence questions a buyer should ask before viewing a block.",
    system_prompt=(
        "You are an HDB buyer advocate. "
        "Use get_transactions() and get_proximity() tools to analyze the block's market and location data. "
        "Generate 4-6 due-diligence questions the buyer should ask the real-estate agent before viewing. "
        "Always include: floor/facing/renovation condition, comparable sales condition, "
        "ethnic quota/extension restrictions. "
        "Add questions about limited resale evidence if transaction_count < 6. "
        "Add a question about MRT/school walking route if distances > 500m or school_count < 2. "
        "Write a one-sentence narrative summarising why these questions matter."
    ),
    output_type=AgentQuestions,
    tool_names=["transactions", "proximity"],
    prefetch=[],
)
