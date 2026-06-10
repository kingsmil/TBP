"""Verify HDBTown enum against known HDB towns (no DB dependencies).

This script compares the HDBTown enum with the official list of HDB towns
and provides SQL queries to check your database.
"""
from app.core.models import HDBTown


# Official HDB towns from HDB.gov.sg
OFFICIAL_HDB_TOWNS = [
    "ANG MO KIO",
    "BEDOK",
    "BISHAN",
    "BUKIT BATOK",
    "BUKIT MERAH",
    "BUKIT PANJANG",
    "BUKIT TIMAH",
    "CENTRAL AREA",
    "CHOA CHU KANG",
    "CLEMENTI",
    "GEYLANG",
    "HOUGANG",
    "JURONG EAST",
    "JURONG WEST",
    "KALLANG/WHAMPOA",
    "MARINE PARADE",
    "PASIR RIS",
    "PUNGGOL",
    "QUEENSTOWN",
    "SEMBAWANG",
    "SENGKANG",
    "SERANGOON",
    "TAMPINES",
    "TOA PAYOH",
    "WOODLANDS",
    "YISHUN",
]


def verify_enum():
    """Verify the enum against official list."""
    print("=" * 70)
    print("HDB Town Enum Verification")
    print("=" * 70)
    print()

    enum_towns = {town.value for town in HDBTown}
    official_towns = set(OFFICIAL_HDB_TOWNS)

    print(f"📋 HDBTown Enum ({len(enum_towns)} towns):")
    print("-" * 70)
    for i, town in enumerate(sorted(enum_towns), 1):
        print(f"{i:2d}. {town}")
    print()

    print(f"📚 Official HDB Towns ({len(official_towns)} towns):")
    print("-" * 70)
    for i, town in enumerate(sorted(official_towns), 1):
        print(f"{i:2d}. {town}")
    print()

    # Compare
    print("🔍 Comparison:")
    print("-" * 70)

    missing_in_enum = official_towns - enum_towns
    extra_in_enum = enum_towns - official_towns
    matching = enum_towns & official_towns

    all_match = len(missing_in_enum) == 0 and len(extra_in_enum) == 0

    if all_match:
        print(f"✅ Perfect match! All {len(matching)} towns are correct.")
    else:
        print(f"⚠️  Found discrepancies:")

    print()

    if missing_in_enum:
        print(f"❌ Official towns MISSING from HDBTown enum ({len(missing_in_enum)}):")
        for town in sorted(missing_in_enum):
            print(f"   - {town}")
            enum_name = town.replace(" ", "_").replace("/", "_")
            print(f"     Add: {enum_name} = \"{town}\"")
        print()

    if extra_in_enum:
        print(f"⚠️  Towns in enum but NOT in official list ({len(extra_in_enum)}):")
        for town in sorted(extra_in_enum):
            print(f"   - {town}")
        print()

    if matching:
        print(f"✅ Correctly defined towns ({len(matching)}):")
        for town in sorted(matching):
            print(f"   ✓ {town}")
        print()

    # SQL Query for database verification
    print("=" * 70)
    print("SQL Queries to Check Your Database:")
    print("=" * 70)
    print()

    print("-- 1. Get all distinct towns from database:")
    print("SELECT DISTINCT town FROM hdb_blocks ORDER BY town;")
    print()

    print("-- 2. Count records per town:")
    print("SELECT town, COUNT(*) as count")
    print("FROM hdb_blocks")
    print("GROUP BY town")
    print("ORDER BY count DESC;")
    print()

    print("-- 3. Find towns in DB that might not match enum:")
    print("SELECT DISTINCT town")
    print("FROM hdb_blocks")
    print("WHERE town NOT IN (")
    for i, town in enumerate(sorted(enum_towns)):
        sep = "," if i < len(enum_towns) - 1 else ""
        print(f"    '{town}'{sep}")
    print(");")
    print()

    # Summary
    print("=" * 70)
    print("Summary:")
    print(f"  Official towns: {len(official_towns)}")
    print(f"  Enum towns:     {len(enum_towns)}")
    print(f"  Matching:       {len(matching)}")
    print(f"  Missing in enum: {len(missing_in_enum)}")
    print(f"  Extra in enum:   {len(extra_in_enum)}")
    print("=" * 70)

    return all_match


if __name__ == "__main__":
    verify_enum()
