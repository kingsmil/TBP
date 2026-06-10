from app.homeos.framework.agent import AgentDefinition
from app.homeos.models.evidence import LocationEvidence

location_definition = AgentDefinition(
    name="location",
    system_prompt=(
        "You are an HDB location analyst. "
        "Given MRT distance and school proximity data (in pre-fetched context), "
        "summarise the location evidence. "
        "Write a one-sentence narrative (max 30 words) describing the connectivity for this buyer. "
        "Copy the connections list directly from pre-fetched context."
    ),
    output_type=LocationEvidence,
    tool_names=["proximity"],
    prefetch=["proximity"],
)
