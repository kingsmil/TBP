"""Test fuzzy town matching for search tool."""

from app.homeos.tools.search import _fuzzy_match_town
from app.core.models import HDBTown


def test_fuzzy_match():
    """Test various town name inputs."""
    print("=" * 70)
    print("Testing Fuzzy Town Matching")
    print("=" * 70)
    print()

    test_cases = [
        # Exact matches
        ("TAMPINES", HDBTown.TAMPINES),
        ("BISHAN", HDBTown.BISHAN),
        ("CENTRAL AREA", HDBTown.CENTRAL_AREA),
        ("KALLANG/WHAMPOA", HDBTown.KALLANG_WHAMPOA),

        # Partial matches (the issue)
        ("CENTRAL", HDBTown.CENTRAL_AREA),
        ("KALLANG", HDBTown.KALLANG_WHAMPOA),
        ("WHAMPOA", HDBTown.KALLANG_WHAMPOA),

        # Abbreviations
        ("AMK", HDBTown.ANG_MO_KIO),
        ("CCK", HDBTown.CHOA_CHU_KANG),
        ("JE", HDBTown.JURONG_EAST),
        ("JW", HDBTown.JURONG_WEST),
        ("TPY", HDBTown.TOA_PAYOH),
        ("CBD", HDBTown.CENTRAL_AREA),
        ("DOWNTOWN", HDBTown.CENTRAL_AREA),
        ("CITY", HDBTown.CENTRAL_AREA),

        # Partial word matches
        ("BUKIT", HDBTown.BUKIT_BATOK),  # First BUKIT town
        ("JURONG", HDBTown.JURONG_WEST),  # Defaults to WEST

        # Case variations
        ("tampines", HDBTown.TAMPINES),
        ("Bishan", HDBTown.BISHAN),
        ("central area", HDBTown.CENTRAL_AREA),

        # Edge case: short words should NOT match (THE FIX!)
        ("TO", None),  # Should NOT match "BUKIT BATOK"
        ("IN", None),  # Should NOT match anything
        ("OR", None),  # Should NOT match anything

        # Invalid inputs
        ("INVALID", None),
        ("XYZ", None),
        ("", None),
    ]

    passed = 0
    failed = 0

    for input_town, expected in test_cases:
        result = _fuzzy_match_town(input_town)

        success = result == expected
        status = "✅" if success else "❌"

        if success:
            passed += 1
        else:
            failed += 1

        print(f"{status} Input: {input_town!r:20} -> Expected: {expected!s:30} Got: {result}")

        if not success:
            print(f"   MISMATCH! Expected {expected}, got {result}")

    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = test_fuzzy_match()
    exit(0 if success else 1)
