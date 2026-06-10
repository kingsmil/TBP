from app.homeos.framework.spec import AgentSpec
from app.homeos.models.evidence import LocationEvidence

location_definition = AgentSpec(
    name="location",
    description="Evaluates MRT distance and school proximity to score location suitability for a buyer.",
    system_prompt=(
        "You are an HDB location analyst. "
        "Use the get_proximity() tool to fetch MRT distance and school proximity data. "
        "Analyze the location's connectivity and accessibility. "
        "Write a one-sentence narrative (max 30 words) describing the connectivity for this buyer. "
        "Return the connections list and narrative."
    ),
    output_type=LocationEvidence,
    tool_names=["proximity"],
    prefetch=[],
)
