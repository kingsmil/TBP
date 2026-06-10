from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import LocationEvidence

location_definition = AgentSpec(
    name="location",
    description="Evaluates MRT distance and school proximity to score location suitability for a buyer.",
    system_prompt=(
        "You are an HDB location analyst. "
        "Use get_proximity() to fetch MRT distance and school proximity data. "
        "Use get_commute() to analyze workplace commute times if work_locations are specified. "
        "Use get_bus_routes() to check bus connectivity. "
        "Include commute and bus-route findings in the narrative ONLY when available: true; "
        "when available is false, ignore that section entirely. "
        "Write a one-sentence narrative (max 30 words) describing the connectivity for this buyer. "
        "Return the connections list and narrative."
    ),
    output_type=LocationEvidence,
    tool_names=["proximity", "commute", "bus_routes"],
    prefetch=[],
)
