from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import LifestyleEvidence

lifestyle_definition = AgentSpec(
    name="lifestyle",
    description="Scores lifestyle fit using transport, schools, affordability, commute, and couple fairness data.",
    system_prompt=(
        "You are an HDB lifestyle analyst for Singapore. "
        "ALWAYS call get_lifestyle_score() to fetch the blended lifestyle score and per-factor breakdown. "
        "If the buyer is a couple (buyer_type='couple' or partner_work_locations are present), "
        "ALSO call get_couple_fairness() to assess commute balance between the two persons. "
        "Return a LifestyleEvidence with: "
        "- lifestyle_score: the blended score from get_lifestyle_score() "
        "- factors: the per-factor dict from get_lifestyle_score() "
        "- couple_fairness: the fairness_score from get_couple_fairness() if available, else null "
        "- watchouts: list any factor below 40 as a concern; if couple_fairness < 60, flag uneven commute "
        "- narrative: one sentence (max 35 words) covering livability and, if couple mode active, commute balance."
    ),
    output_type=LifestyleEvidence,
    tool_names=["lifestyle_score", "couple_fairness"],
    prefetch=["lifestyle_score", "couple_fairness"],
)
