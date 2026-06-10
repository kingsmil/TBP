from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import LifestyleEvidence

lifestyle_definition = AgentSpec(
    name="lifestyle",
    description="Scores lifestyle fit using transport, schools, affordability, and commute data.",
    system_prompt=(
        "You are an HDB lifestyle analyst for Singapore. "
        "ALWAYS call get_lifestyle_score() to fetch the blended lifestyle score and per-factor breakdown. "
        "Interpret the score (0-100) and factor breakdown for this buyer. "
        "Return a LifestyleEvidence with: "
        "- lifestyle_score: the blended score from the tool "
        "- factors: the per-factor dict from the tool "
        "- watchouts: list any factor below 40 as a concern "
        "- narrative: one sentence (max 30 words) describing overall livability for this buyer. "
        "Set commute_band and couple_fairness to null unless you have that data."
    ),
    output_type=LifestyleEvidence,
    tool_names=["lifestyle_score"],
    prefetch=["lifestyle_score"],
)
