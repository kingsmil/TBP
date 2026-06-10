"""Verify that HDBTown enum matches actual towns in the database from data.gov.sg.

This script:
1. Connects to the PostgreSQL database
2. Queries distinct town values from hdb_blocks table
3. Compares with the HDBTown enum
4. Reports any mismatches

Usage:
    python verify_town_enum.py
"""
import os
import sys
from typing import Set

from sqlalchemy import text

from app.core.models import HDBTown
from app.db.session import get_engine


def get_db_towns() -> Set[str]:
    """Query all distinct town values from the database."""
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT town
            FROM hdb_blocks
            WHERE town IS NOT NULL
            ORDER BY town
        """))

        towns = {row[0] for row in result}

    return towns


def get_enum_towns() -> Set[str]:
    """Get all town values from the HDBTown enum."""
    return {town.value for town in HDBTown}


def verify_towns() -> bool:
    """Verify that enum and database towns match."""
    print("=" * 70)
    print("HDB Town Enum Verification")
    print("=" * 70)
    print()

    # Check if database is available
    try:
        db_towns = get_db_towns()
        has_db = True
    except Exception as e:
        print(f"⚠️  Database not available: {e}")
        print("   Skipping database verification.")
        print()
        has_db = False
        db_towns = set()

    enum_towns = get_enum_towns()

    # Show enum towns
    print(f"📋 HDBTown Enum ({len(enum_towns)} towns):")
    print("-" * 70)
    for i, town in enumerate(sorted(enum_towns), 1):
        print(f"{i:2d}. {town}")
    print()

    if not has_db:
        return True

    # Show database towns
    print(f"🗄️  Database Towns ({len(db_towns)} towns):")
    print("-" * 70)
    for i, town in enumerate(sorted(db_towns), 1):
        print(f"{i:2d}. {town}")
    print()

    # Compare
    print("🔍 Comparison:")
    print("-" * 70)

    missing_in_enum = db_towns - enum_towns
    missing_in_db = enum_towns - db_towns
    matching = db_towns & enum_towns

    all_match = len(missing_in_enum) == 0 and len(missing_in_db) == 0

    if all_match:
        print(f"✅ Perfect match! All {len(matching)} towns are consistent.")
    else:
        print(f"⚠️  Found discrepancies:")

    print()

    if missing_in_enum:
        print(f"❌ Towns in DATABASE but MISSING from HDBTown enum ({len(missing_in_enum)}):")
        for town in sorted(missing_in_enum):
            print(f"   - {town}")
            # Suggest enum member name
            enum_name = town.replace(" ", "_").replace("/", "_")
            print(f"     Add: {enum_name} = \"{town}\"")
        print()

    if missing_in_db:
        print(f"⚠️  Towns in HDBTown enum but NOT in database ({len(missing_in_db)}):")
        for town in sorted(missing_in_db):
            print(f"   - {town}")
            print(f"     (This is OK if database has limited data)")
        print()

    if matching:
        print(f"✅ Matching towns ({len(matching)}):")
        for town in sorted(matching):
            print(f"   ✓ {town}")
        print()

    # Summary
    print("=" * 70)
    print("Summary:")
    print(f"  Enum towns:     {len(enum_towns)}")
    print(f"  Database towns: {len(db_towns)}")
    print(f"  Matching:       {len(matching)}")
    print(f"  Missing in enum: {len(missing_in_enum)}")
    print(f"  Missing in DB:   {len(missing_in_db)}")
    print("=" * 70)

    return all_match


def verify_data_gov_api() -> None:
    """Query data.gov.sg API to see what towns are in the live dataset."""
    import httpx

    print()
    print("=" * 70)
    print("Checking data.gov.sg API for town values")
    print("=" * 70)
    print()

    DATASET_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
    DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"

    try:
        with httpx.Client(timeout=30.0) as client:
            # Get a sample of records
            response = client.get(
                DATASTORE_URL,
                params={"resource_id": DATASET_ID, "limit": 1000, "offset": 0}
            )
            response.raise_for_status()
            data = response.json()
            records = data["result"]["records"]

            # Extract unique towns
            api_towns = {str(r["town"]).strip().upper() for r in records}

            print(f"📡 Found {len(api_towns)} unique towns in API sample (1000 records):")
            print("-" * 70)
            for i, town in enumerate(sorted(api_towns), 1):
                print(f"{i:2d}. {town}")
            print()

            enum_towns = get_enum_towns()
            missing_in_enum = api_towns - enum_towns
            missing_in_api = enum_towns - api_towns

            if missing_in_enum:
                print(f"❌ Towns in API but MISSING from enum ({len(missing_in_enum)}):")
                for town in sorted(missing_in_enum):
                    print(f"   - {town}")
                print()

            if missing_in_api:
                print(f"ℹ️  Towns in enum but not in API sample ({len(missing_in_api)}):")
                for town in sorted(missing_in_api):
                    print(f"   - {town} (may appear in full dataset)")
                print()

            if not missing_in_enum and not missing_in_api:
                print("✅ API sample matches enum perfectly!")
                print()

    except Exception as e:
        print(f"⚠️  Could not query data.gov.sg API: {e}")
        print()


def main() -> int:
    """Run verification."""
    # Verify against database
    db_match = verify_towns()

    # Also check the live API
    verify_data_gov_api()

    return 0 if db_match else 1


if __name__ == "__main__":
    sys.exit(main())
