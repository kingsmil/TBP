"""Test that the profile agent correctly extracts town from natural language."""

from app.homeos.models.avatar import HomeOSPreferences
from app.core.models import HDBTown


def test_preferences_town_extraction():
    """Test town field validation and fuzzy matching."""
    print("=" * 70)
    print("Testing HomeOSPreferences Town Extraction")
    print("=" * 70)
    print()

    test_cases = [
        # Exact matches
        ("TAMPINES", HDBTown.TAMPINES),
        ("CENTRAL AREA", HDBTown.CENTRAL_AREA),
        ("KALLANG/WHAMPOA", HDBTown.KALLANG_WHAMPOA),

        # Partial/fuzzy matches (the issue!)
        ("CENTRAL", HDBTown.CENTRAL_AREA),
        ("central", HDBTown.CENTRAL_AREA),
        ("Central", HDBTown.CENTRAL_AREA),

        # Abbreviations
        ("AMK", HDBTown.ANG_MO_KIO),
        ("CCK", HDBTown.CHOA_CHU_KANG),

        # Edge cases
        ("", None),
        (None, None),
        ("INVALID_TOWN", None),
    ]

    passed = 0
    failed = 0

    for input_town, expected in test_cases:
        try:
            prefs = HomeOSPreferences(town=input_town, max_price=800000)
            result = prefs.town

            success = result == expected
            status = "✅" if success else "❌"

            if success:
                passed += 1
            else:
                failed += 1

            print(f"{status} Input: {input_town!r:20} -> Expected: {str(expected):30} Got: {result}")

            if not success:
                print(f"   MISMATCH! Expected {expected}, got {result}")
        except Exception as e:
            print(f"❌ Input: {input_town!r:20} -> ERROR: {e}")
            failed += 1

    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


def test_profile_examples():
    """Test real-world profile text examples."""
    print()
    print("=" * 70)
    print("Testing Real-World Examples")
    print("=" * 70)
    print()

    examples = [
        {
            "input": "stay near central",
            "expected_town": HDBTown.CENTRAL_AREA,
            "description": "User says 'near central'"
        },
        {
            "input": "looking in tampines",
            "expected_town": HDBTown.TAMPINES,
            "description": "User says 'in tampines'"
        },
        {
            "input": "bishan area preferred",
            "expected_town": HDBTown.BISHAN,
            "description": "User says 'bishan area'"
        },
        {
            "input": "kallang preferred",
            "expected_town": HDBTown.KALLANG_WHAMPOA,
            "description": "User says 'kallang'"
        },
    ]

    for example in examples:
        # Note: These are manual examples showing what the agent SHOULD extract
        # The actual agent would need to parse the full sentence
        print(f"📝 {example['description']}")
        print(f"   Input text: '{example['input']}'")
        print(f"   Expected town: {example['expected_town'].value}")

        # Extract the town keyword from the input
        input_lower = example['input'].lower()
        town_keyword = None

        if 'central' in input_lower:
            town_keyword = 'CENTRAL'
        elif 'tampines' in input_lower:
            town_keyword = 'TAMPINES'
        elif 'bishan' in input_lower:
            town_keyword = 'BISHAN'
        elif 'kallang' in input_lower:
            town_keyword = 'KALLANG'

        if town_keyword:
            prefs = HomeOSPreferences(town=town_keyword)
            actual = prefs.town
            success = actual == example['expected_town']
            status = "✅" if success else "❌"
            print(f"   {status} Extracted: {actual}")
        else:
            print(f"   ❌ Could not extract town")

        print()


if __name__ == "__main__":
    print()
    success = test_preferences_town_extraction()
    test_profile_examples()

    exit(0 if success else 1)
