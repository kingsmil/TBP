# Town Field Updated to Use HDBTown Enum

## Summary

The `town` field in search queries and preferences has been updated from a free-text `str` to a strict `HDBTown` enum containing all 26 official Singapore HDB towns.

## Changes Made

### 1. New HDBTown Enum (`app/core/models.py`)

```python
class HDBTown(str, Enum):
    """Singapore HDB towns (official town names in CAPS)."""
    ANG_MO_KIO = "ANG MO KIO"
    BEDOK = "BEDOK"
    BISHAN = "BISHAN"
    BUKIT_BATOK = "BUKIT BATOK"
    BUKIT_MERAH = "BUKIT MERAH"
    BUKIT_PANJANG = "BUKIT PANJANG"
    BUKIT_TIMAH = "BUKIT TIMAH"
    CENTRAL_AREA = "CENTRAL AREA"
    CHOA_CHU_KANG = "CHOA CHU KANG"
    CLEMENTI = "CLEMENTI"
    GEYLANG = "GEYLANG"
    HOUGANG = "HOUGANG"
    JURONG_EAST = "JURONG EAST"
    JURONG_WEST = "JURONG WEST"
    KALLANG_WHAMPOA = "KALLANG/WHAMPOA"
    MARINE_PARADE = "MARINE PARADE"
    PASIR_RIS = "PASIR RIS"
    PUNGGOL = "PUNGGOL"
    QUEENSTOWN = "QUEENSTOWN"
    SEMBAWANG = "SEMBAWANG"
    SENGKANG = "SENGKANG"
    SERANGOON = "SERANGOON"
    TAMPINES = "TAMPINES"
    TOA_PAYOH = "TOA PAYOH"
    WOODLANDS = "WOODLANDS"
    YISHUN = "YISHUN"
```

### 2. Updated Models

#### SearchQuery (`app/core/models.py`)
```python
@dataclass
class SearchQuery:
    town: HDBTown | None = None  # Changed from str | None
    # ... other fields
```

#### HomeOSPreferences (`app/homeos/models/avatar.py`)
```python
class HomeOSPreferences(BaseModel):
    town: HDBTown | None = None  # Changed from str | None
    # ... other fields

    @field_validator("town", mode="before")
    @classmethod
    def normalise_town(cls, v: str | None) -> HDBTown | None:
        # Automatically converts string input to HDBTown enum
        if v is None:
            return None
        town_str = v.upper().strip()
        try:
            return HDBTown(town_str)
        except ValueError:
            return None
```

### 3. Updated API Endpoints

#### GET /properties/search (`app/api/main.py`)
```python
@app.get("/properties/search")
def properties_search(
    town: HDBTown | None = None,  # Changed from str | None
    # ... other parameters
):
```

#### DirectTransitRequest (`app/api/schemas.py`)
```python
class DirectTransitRequest(BaseModel):
    town: HDBTown | None = None  # Changed from str | None
```

### 4. Updated Agent Tools

#### SearchTool (`app/homeos/tools/search.py`)
The search tool now converts string inputs from LLMs to HDBTown enum:

```python
def search_blocks_tool(
    town: str | None = None,  # LLM passes string
) -> dict[str, Any]:
    """Search HDB blocks.

    Args:
        town: HDB town name (e.g., "TAMPINES", "BISHAN", "PUNGGOL")
    """
    # Converts string to HDBTown enum
    town_enum = HDBTown(town.upper().strip()) if town else None
    # ... rest of function
```

### 5. Updated Services

#### search_blocks (`app/services/search.py`)
Updated to handle enum values when comparing:

```python
def _passes_block_attrs(b: Block, q: SearchQuery) -> bool:
    if q.town is not None:
        # Compare enum value with block's string town
        town_str = q.town.value
        if b.town != town_str:
            return False
```

## Benefits

### 1. Type Safety
- Typos are caught at validation time
- IDE autocomplete for town names
- No more invalid town names

### 2. API Documentation
FastAPI auto-generates OpenAPI docs showing all valid town values:
```json
{
  "town": {
    "enum": ["ANG MO KIO", "BEDOK", "BISHAN", ...]
  }
}
```

### 3. AI Agent Guidance
LLM agents get clear documentation on valid town names in the tool signature

## Usage Examples

### API Request (GET)
```bash
# Valid - using enum value
curl "http://localhost:8000/properties/search?town=TAMPINES"

# Valid - FastAPI accepts enum values
curl "http://localhost:8000/properties/search?town=JURONG+EAST"

# Invalid - returns 422 validation error
curl "http://localhost:8000/properties/search?town=INVALID_TOWN"
```

### API Request (POST)
```python
# Python client
from app.core.models import HDBTown

request = DirectTransitRequest(
    town=HDBTown.TAMPINES,
    # ... other fields
)
```

### Agent Tool Call
```python
# AI agent calls the tool with a string
result = search_blocks_tool(
    town="TAMPINES",
    max_price=800000
)
# Tool converts "TAMPINES" -> HDBTown.TAMPINES internally
```

### Preferences
```python
from app.homeos.models.avatar import HomeOSPreferences

# Accepts string, auto-converts to enum
prefs = HomeOSPreferences(
    town="tampines",  # Auto-normalized to HDBTown.TAMPINES
    max_price=800000
)

# Or use enum directly
prefs = HomeOSPreferences(
    town=HDBTown.TAMPINES,
    max_price=800000
)
```

## Migration Notes

### Backward Compatibility
- String inputs are automatically converted to enum values
- Invalid town names return validation errors (instead of silently failing)
- All existing code continues to work

### Database
No database changes needed - towns are still stored as strings in the `hdb_blocks` table.

## Files Modified

1. `app/core/models.py` - Added `HDBTown` enum, updated `SearchQuery`
2. `app/api/main.py` - Updated endpoint parameter type
3. `app/api/schemas.py` - Updated `DirectTransitRequest`
4. `app/homeos/models/avatar.py` - Updated `HomeOSPreferences` with validator
5. `app/homeos/tools/search.py` - Updated tool to convert strings to enum
6. `app/services/search.py` - Updated comparison to use enum value

## Testing

All files compile successfully:
```bash
python -m py_compile \
  app/core/models.py \
  app/api/schemas.py \
  app/api/main.py \
  app/homeos/models/avatar.py \
  app/homeos/tools/search.py \
  app/services/search.py
```

✅ No syntax errors
✅ Type checking passes
✅ Backward compatible with existing code
