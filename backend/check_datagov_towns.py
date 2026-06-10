"""Check data.gov.sg API for actual town values in the live dataset.

This script queries the data.gov.sg HDB resale transactions API
to verify what town values actually appear in the live data.
"""
import json
import sys
from collections import Counter
from typing import Set

try:
    import httpx
except ImportError:
    print("❌ httpx not installed. Install with: pip install httpx")
    sys.exit(1)

from app.core.models import HDBTown


DATASET_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"


def fetch_towns_from_api(sample_size: int = 5000) -> tuple[Set[str], Counter]:
    """Fetch town values from data.gov.sg API."""
    print(f"🌐 Querying data.gov.sg API (sampling {sample_size} records)...")
    print()

    towns: Set[str] = set()
    town_counts: Counter = Counter()

    with httpx.Client(timeout=30.0) as client:
        offset = 0
        page_size = 1000
        total_fetched = 0

        while total_fetched < sample_size:
            batch_size = min(page_size, sample_size - total_fetched)

            print(f"  Fetching records {offset} to {offset + batch_size}...", end="\r")

            response = client.get(
                DATASTORE_URL,
                params={
                    "resource_id": DATASET_ID,
                    "limit": batch_size,
                    "offset": offset
                }
            )
            response.raise_for_status()
            data = response.json()

            records = data["result"]["records"]
            if not records:
                break

            for record in records:
                town = str(record["town"]).strip().upper()
                towns.add(town)
                town_counts[town] += 1

            total_fetched += len(records)
            offset += len(records)

            # Check if we've reached the end
            if len(records) < batch_size:
                break

    print(f"  ✓ Fetched {total_fetched} records" + " " * 20)
    print()

    return towns, town_counts


def verify_against_api():
    """Verify enum against live API data."""
    print("=" * 70)
    print("Data.gov.sg Live Data Verification")
    print("=" * 70)
    print()

    try:
        api_towns, town_counts = fetch_towns_from_api(sample_size=5000)
    except Exception as e:
        print(f"❌ Failed to query API: {e}")
        return False

    enum_towns = {town.value for town in HDBTown}

    print(f"📡 Towns found in data.gov.sg ({len(api_towns)} unique towns):")
    print("-" * 70)
    for i, town in enumerate(sorted(api_towns), 1):
        count = town_counts[town]
        print(f"{i:2d}. {town:<25} ({count:,} blocks)")
    print()

    # Compare
    print("🔍 Comparison with HDBTown Enum:")
    print("-" * 70)

    missing_in_enum = api_towns - enum_towns
    missing_in_api = enum_towns - api_towns
    matching = api_towns & enum_towns

    all_match = len(missing_in_enum) == 0

    if all_match:
        print(f"✅ All {len(matching)} towns from data.gov.sg are in the enum!")
    else:
        print(f"⚠️  Found discrepancies:")

    print()

    if missing_in_enum:
        print(f"❌ Towns in DATA.GOV.SG but MISSING from enum ({len(missing_in_enum)}):")
        print("   ACTION REQUIRED: Add these to HDBTown enum!")
        print()
        for town in sorted(missing_in_enum):
            count = town_counts[town]
            enum_name = town.replace(" ", "_").replace("/", "_")
            print(f"   - {town} ({count:,} blocks)")
            print(f"     Add to enum: {enum_name} = \"{town}\"")
        print()

    if missing_in_api:
        print(f"ℹ️  Towns in enum but not in API sample ({len(missing_in_api)}):")
        print("   (These are OK - they may appear in full dataset or be valid HDB towns)")
        print()
        for town in sorted(missing_in_api):
            print(f"   - {town}")
        print()

    if matching:
        print(f"✅ Matching towns ({len(matching)}):")
        for town in sorted(matching):
            count = town_counts[town]
            print(f"   ✓ {town} ({count:,} blocks)")
        print()

    # Summary
    print("=" * 70)
    print("Summary:")
    print(f"  Enum towns:        {len(enum_towns)}")
    print(f"  API towns:         {len(api_towns)}")
    print(f"  Matching:          {len(matching)}")
    print(f"  Missing in enum:   {len(missing_in_enum)}")
    print(f"  Not in API sample: {len(missing_in_api)}")
    print("=" * 70)

    if not all_match:
        print()
        print("⚠️  ACTION REQUIRED: Update HDBTown enum to include all towns!")
        return False

    print()
    print("✅ Enum is complete and matches live data!")
    return True


if __name__ == "__main__":
    success = verify_against_api()
    sys.exit(0 if success else 1)
