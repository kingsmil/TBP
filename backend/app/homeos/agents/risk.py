from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import RiskEvidence

risk_definition = AgentSpec(
    name="risk",
    description="Identifies appreciation potential, supply risk, and accessibility to compute a risk-adjusted score.",
    system_prompt=(
        "You are an HDB risk analyst. "
        "Given appreciation score, future supply, and accessibility data (in pre-fetched context), "
        "identify watchouts and compute a score adjustment. "
        "Rules: if risk_level is 'high' and buyer is low-risk, add watchout and subtract 8 from score_adjustment. "
        "If supply_risk_level is 'high', add watchout and subtract 4 from score_adjustment. "
        "Add appreciation_score / 10 (capped at 12) to score_adjustment. "
        "Write a one-sentence narrative (max 30 words) summarising the risk profile."
    ),
    output_type=RiskEvidence,
    tool_names=["appreciation", "future_dev", "accessibility"],
    prefetch=["appreciation", "future_dev"],
)
