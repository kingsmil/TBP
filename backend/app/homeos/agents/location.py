from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import LocationEvidence

location_definition = AgentSpec(
    name="location",
    description="Evaluates MRT distance and school proximity to score location suitability for a buyer.",
    system_prompt=(
        "You are an HDB location analyst. "
        "ALWAYS call get_proximity() to fetch MRT distance and school proximity data. "
        "ALWAYS call get_commute() to analyze workplace commute times (returns available=false if no work_locations). "
        "ALWAYS call get_bus_routes() to check bus connectivity (returns available=false if not bus-dependent). "
        "Return a LocationEvidence with: "
        "- connections: list from proximity tool "
        "- commute: full output from get_commute() "
        "- bus_routes: full output from get_bus_routes() "
        "- narrative: one sentence (max 30 words) describing connectivity. "
        "Include commute and bus-route findings in the narrative ONLY when that tool returned available: true. "
        "When available is false, don't mention that aspect in the narrative."
    ),
    output_type=LocationEvidence,
    tool_names=["proximity", "commute", "bus_routes"],
    prefetch=["proximity", "commute", "bus_routes"],
)
