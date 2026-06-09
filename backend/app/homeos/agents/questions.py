from app.homeos.framework.agent import AgentDefinition
from app.homeos.models.evidence import AgentQuestions

questions_definition = AgentDefinition(
    name="questions",
    system_prompt=(
        "You are an HDB buyer advocate. "
        "Given the evidence from market, location, and risk agents, generate 4-6 due-diligence "
        "questions the buyer should ask the real-estate agent before viewing. "
        "Always include: floor/facing/renovation condition, comparable sales condition, "
        "ethnic quota/extension restrictions. "
        "Add questions about limited resale evidence if confidence is low or medium. "
        "Add a question about MRT/school walking route if any connection signal is not strong. "
        "Write a one-sentence narrative summarising why these questions matter."
    ),
    output_type=AgentQuestions,
    tool_names=["transactions", "proximity"],
    prefetch=[],
)
