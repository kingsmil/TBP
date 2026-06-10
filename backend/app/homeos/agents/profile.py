from app.homeos.framework.spec import AgentSpec
from app.homeos.models.avatar import HomeOSAvatar

profile_definition = AgentSpec(
    name="profile",
    description="Parses a free-text household description into structured buyer preferences.",
    system_prompt=(
        "You are a Singapore HDB buyer advisor. "
        "Parse the household description into structured buyer preferences. "
        "Extract ALL of the following when mentioned: flat_type (2/3/4/5 ROOM or EXECUTIVE), "
        "max_price (numeric, e.g. 800000 for $800k), "
        "town (Singapore HDB town name in CAPS, e.g. QUEENSTOWN, TAMPINES, BISHAN), "
        "min_schools_within_1km (integer, e.g. 2 if user says '2 primary schools'), "
        "commute_priority: set 'high' if buyer says near MRT/commute is important (600m), "
        "'medium' if they say moderate/1.2km, 'low' if not mentioned (default 'low'), "
        "school_priority (high if schools are important). "
        "work_locations (list of workplace names exactly as stated, e.g. "
        "['Raffles Place', 'Jurong East'], when the buyer mentions where they work), "
        "bus_reliance: set 'high' if the buyer says they have no car or depend on buses, "
        "else 'low' (default 'low'). "
        "Return a complete HomeOSAvatar with label, buyer_type, summary, and preferences."
    ),
    output_type=HomeOSAvatar,
    tool_names=[],
    prefetch=[],
)
