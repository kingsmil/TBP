from app.homeos.framework.spec import AgentSpec, PrefDimension
from app.homeos.models.evidence import RiskEvidence

risk_definition = AgentSpec(
    name="risk",
    description="Identifies appreciation potential, supply risk, and accessibility to compute a risk-adjusted score.",
    system_prompt=(
        "You are an HDB risk analyst. "
        "Use get_appreciation(), get_future_dev(), and get_accessibility() tools to fetch risk data. "
        "Analyze appreciation potential, future supply impact, and accessibility scores. "
        "Identify watchouts and compute score_adjustment: "
        "- If risk_level is 'high' and buyer is low-risk: add watchout and subtract 8 from score_adjustment "
        "- If supply_risk_level is 'high': add watchout and subtract 4 from score_adjustment "
        "- Add appreciation_score / 10 (capped at 12) to score_adjustment "
        "Write a one-sentence narrative (max 30 words) summarising the risk profile."
    ),
    output_type=RiskEvidence,
    tool_names=["appreciation", "future_dev", "accessibility"],
    prefetch=[],
    activating_prefs=[
        PrefDimension(field="risk_tolerance",
                      prompt="Risk tolerance (low = penalise high-risk blocks harder)",
                      default="low"),
    ],
)
