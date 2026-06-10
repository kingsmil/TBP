# Town Extraction Fix - "Stay Near Central"

## Problem

The profile agent was not extracting town from natural language input:

**User Input:** "stay near central"

**Result:**
```json
{
  "search_query": {
    "town": null,  // ❌ Town not extracted
    "flat_type": null
  }
}
```

## Root Cause

Two issues:

1. **Profile Agent Prompt**: Didn't have clear examples showing how to extract town from natural language ("near central", "in tampines", etc.)

2. **HomeOSPreferences Validator**: The `normalise_town()` validator only did exact matching, not fuzzy matching, so even if the agent extracted "CENTRAL", it would fail to convert to "CENTRAL AREA"

## Solution

### 1. Enhanced Profile Agent Prompt

**Before:**
```python
"town (Singapore HDB town name in CAPS, e.g. QUEENSTOWN, TAMPINES, BISHAN)"
```

**After:**
```python
"town: CRITICAL - Extract town name from ANY location reference:
  Examples: 'near central' → 'CENTRAL AREA', 'in tampines' → 'TAMPINES',
  'bishan area' → 'BISHAN', 'stay in kallang' → 'KALLANG/WHAMPOA'

  IMPORTANT mappings:
  - 'central', 'CBD', 'downtown', 'city' → CENTRAL AREA
  - 'kallang', 'whampoa' → KALLANG/WHAMPOA
  - 'jurong', 'west' → JURONG WEST (default)
  - 'bukit' → BUKIT BATOK (if not specified)"
```

### 2. Updated HomeOSPreferences Validator

**Before:**
```python
@field_validator("town", mode="before")
@classmethod
def normalise_town(cls, v: str | None) -> HDBTown | None:
    if v is None:
        return None
    town_str = v.upper().strip()
    try:
        return HDBTown(town_str)  # ❌ Exact match only
    except ValueError:
        return None
```

**After:**
```python
@field_validator("town", mode="before")
@classmethod
def normalise_town(cls, v: str | None) -> HDBTown | None:
    if v is None or v == "":
        return None

    # Import fuzzy matcher
    from app.homeos.tools.search import _fuzzy_match_town

    # Use the same fuzzy matching logic as the search tool
    return _fuzzy_match_town(v)  # ✅ Fuzzy matching
```

## How It Works Now

### User Input → Profile Agent → Preferences → Search

1. **User says:** "stay near central"

2. **Profile agent extracts:**
   - Sees "near central" in the input
   - Uses mapping: "central" → "CENTRAL AREA"
   - Returns: `town: "CENTRAL AREA"`

3. **HomeOSPreferences validator:**
   - Receives: `town: "CENTRAL AREA"`
   - Fuzzy matcher converts: "CENTRAL AREA" → `HDBTown.CENTRAL_AREA`
   - Stored as: `town: HDBTown.CENTRAL_AREA`

4. **Search tool:**
   - Receives: `prefs.town = HDBTown.CENTRAL_AREA`
   - Converts to string: `"CENTRAL AREA"`
   - Searches database: `WHERE town = 'CENTRAL AREA'`
   - ✅ Returns results!

### Even If Agent Extracts Just "CENTRAL"

The fuzzy matcher in the validator handles it:

1. **Profile agent extracts:** `town: "CENTRAL"` (partial)
2. **Validator fuzzy matches:** "CENTRAL" → `HDBTown.CENTRAL_AREA`
3. **Search executes:** with `town="CENTRAL AREA"`
4. ✅ **Results found!**

## Examples That Now Work

| User Input | Agent Extracts | Validator Converts | Search Uses |
|------------|----------------|-------------------|-------------|
| "stay near central" | "CENTRAL AREA" | CENTRAL_AREA | "CENTRAL AREA" ✅ |
| "near central" | "CENTRAL" | CENTRAL_AREA | "CENTRAL AREA" ✅ |
| "CBD area" | "CENTRAL AREA" | CENTRAL_AREA | "CENTRAL AREA" ✅ |
| "in tampines" | "TAMPINES" | TAMPINES | "TAMPINES" ✅ |
| "bishan preferred" | "BISHAN" | BISHAN | "BISHAN" ✅ |
| "kallang area" | "KALLANG" | KALLANG_WHAMPOA | "KALLANG/WHAMPOA" ✅ |
| "near AMK" | "AMK" | ANG_MO_KIO | "ANG MO KIO" ✅ |

## Files Modified

1. **`app/homeos/agents/profile.py`**
   - Added explicit extraction examples
   - Added mapping rules (central → CENTRAL AREA, etc.)
   - Clearer structure with newlines

2. **`app/homeos/models/avatar.py`**
   - Updated `normalise_town()` validator
   - Now uses `_fuzzy_match_town()` from search tool
   - Consistent fuzzy matching across the app

## Testing

The fuzzy matching logic is tested in:
```bash
python test_town_fuzzy_match.py  # Tests _fuzzy_match_town()
```

Test coverage:
- ✅ Exact matches
- ✅ Partial matches ("CENTRAL" → "CENTRAL AREA")
- ✅ Abbreviations ("AMK" → "ANG MO KIO")
- ✅ Case variations ("central" → "CENTRAL AREA")

## Before vs After

### Before (Broken)

**Input:** "stay near central, budget $800k"

**Profile Agent Output:**
```json
{
  "label": "HomeOS Agent",
  "preferences": {
    "town": null,  // ❌ Not extracted
    "max_price": 800000
  }
}
```

**Search Query:**
```json
{
  "town": null,  // ❌ Missing
  "max_price": 800000
}
```

**Result:** Returns blocks from ALL towns (no filter) 😞

### After (Fixed)

**Input:** "stay near central, budget $800k"

**Profile Agent Output:**
```json
{
  "label": "HomeOS Agent",
  "preferences": {
    "town": "CENTRAL AREA",  // ✅ Extracted!
    "max_price": 800000
  }
}
```

**After Validation:**
```json
{
  "preferences": {
    "town": "HDBTown.CENTRAL_AREA",  // ✅ Converted to enum
    "max_price": 800000
  }
}
```

**Search Query:**
```json
{
  "town": "CENTRAL AREA",  // ✅ Correct!
  "max_price": 800000
}
```

**Result:** Returns only CENTRAL AREA blocks under $800k ✅

## Benefits

1. ✅ **Natural Language Support**: "near central", "in tampines" work
2. ✅ **Consistent Fuzzy Matching**: Same logic everywhere (search tool + validator)
3. ✅ **Better Agent Guidance**: Clear examples and mappings in prompt
4. ✅ **Robust Extraction**: Handles abbreviations, partial names, variations

## Common Mappings

The profile agent now understands these conversions:

| User Says | Agent Extracts | Final Town |
|-----------|----------------|------------|
| "central", "CBD", "downtown", "city" | "CENTRAL AREA" | CENTRAL AREA |
| "kallang", "whampoa" | "KALLANG/WHAMPOA" | KALLANG/WHAMPOA |
| "AMK", "ang mo kio" | "ANG MO KIO" | ANG MO KIO |
| "CCK", "choa chu kang" | "CHOA CHU KANG" | CHOA CHU KANG |
| "JE", "jurong east" | "JURONG EAST" | JURONG EAST |
| "JW", "jurong west" | "JURONG WEST" | JURONG WEST |
| "TPY", "toa payoh" | "TOA PAYOH" | TOA PAYOH |

## Summary

**Problem**: "stay near central" → `town: null`

**Solution**:
1. Better profile agent prompt with examples
2. Fuzzy matching validator in HomeOSPreferences

**Result**: "stay near central" → `town: "CENTRAL AREA"` ✅

The extraction and validation pipeline is now robust end-to-end! 🎉
