from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import LocationEvidence

location_definition = AgentSpec(
    name="location",
    description="Evaluates MRT distance and school proximity to score location suitability for a buyer.",
    system_prompt=(
        "You are an HDB location analyst. "
        "Given MRT distance and school proximity data (in pre-fetched context), "
        "summarise the location evidence. "
        "Commute and bus-route data may also be pre-fetched: include those findings "
        "in the narrative ONLY when that section has available: true; when "
        "available is false, ignore the section entirely and never invent coverage. "
        "Write a one-sentence narrative (max 30 words) describing the connectivity for this buyer. "
        "Copy the connections list directly from pre-fetched context."
    ),
    output_type=LocationEvidence,
    tool_names=["proximity", "commute", "bus_routes"],
    prefetch=["proximity", "commute", "bus_routes"],
)
