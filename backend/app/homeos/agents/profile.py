from app.homeos.framework.agent import AgentDefinition
from app.homeos.models.avatar import HomeOSAvatar

profile_definition = AgentDefinition(
    name="profile",
    system_prompt=(
        "You are a Singapore HDB buyer advisor. "
        "Parse the household description into structured buyer preferences. "
        "Extract ALL of the following when mentioned: flat_type (2/3/4/5 ROOM or EXECUTIVE), "
        "max_price (numeric, e.g. 800000 for $800k), "
        "town (Singapore HDB town name in CAPS, e.g. QUEENSTOWN, TAMPINES, BISHAN), "
        "min_schools_within_1km (integer, e.g. 2 if user says '2 primary schools'), "
        "commute_priority (high if near MRT is important), "
        "school_priority (high if schools are important). "
        "Return a complete HomeOSAvatar with label, buyer_type, summary, and preferences."
    ),
    output_type=HomeOSAvatar,
    tool_names=[],
    prefetch=[],
)
