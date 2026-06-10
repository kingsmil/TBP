"""Test that _direct_answer_overrides correctly extracts town from user messages."""

# Mock the pipeline module functions we need
import sys
sys.path.insert(0, '/Users/khor/development/GitHub/TBP/backend')

from app.homeos.pipeline import _direct_answer_overrides


def test_town_extraction():
    """Test town extraction from various user messages."""
    print("=" * 70)
    print("Testing Direct Answer Override - Town Extraction")
    print("=" * 70)
    print()

    # Simulate a pipeline with a town question
    pipeline = [
        {
            "event": "clarifying_question",
            "question": "Could you name a preferred town or estate? (e.g. Tampines, Bishan, Toa Payoh, Jurong East)"
        }
    ]

    test_cases = [
        {
            "input": "jun hong wants to stay in central",
            "expected_town": "CENTRAL AREA",
            "description": "Full sentence with name + 'stay in central'"
        },
        {
            "input": "central",
            "expected_town": "CENTRAL AREA",
            "description": "Just 'central'"
        },
        {
            "input": "I prefer tampines",
            "expected_town": "TAMPINES",
            "description": "'I prefer tampines'"
        },
        {
            "input": "bishan area please",
            "expected_town": "BISHAN",
            "description": "'bishan area please'"
        },
        {
            "input": "kallang",
            "expected_town": "KALLANG/WHAMPOA",
            "description": "'kallang' (should map to KALLANG/WHAMPOA)"
        },
        {
            "input": "maybe punggol?",
            "expected_town": "PUNGGOL",
            "description": "'maybe punggol?'"
        },
        {
            "input": "we want to live in jurong east",
            "expected_town": "JURONG EAST",
            "description": "'we want to live in jurong east'"
        },
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        overrides = _direct_answer_overrides(test["input"], pipeline)
        actual_town = overrides.get("town")

        success = actual_town == test["expected_town"]
        status = "✅" if success else "❌"

        if success:
            passed += 1
        else:
            failed += 1

        print(f"{status} {test['description']}")
        print(f"   Input: '{test['input']}'")
        print(f"   Expected: {test['expected_town']}")
        print(f"   Got: {actual_town}")
        print()

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = test_town_extraction()
    exit(0 if success else 1)
