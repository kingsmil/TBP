import unittest

from app.homeos.pipeline import parse_homeos_profile


class TestHomeOSService(unittest.TestCase):
    def test_parse_family_profile(self):
        avatar = parse_homeos_profile(
            "We are a young family, budget 750k, need 4-room, care about primary schools, "
            "one parent works in Raffles Place, low risk tolerance."
        )

        self.assertEqual(avatar["label"], "Family HomeOS Agent")
        self.assertEqual(avatar["buyer_type"], "family")
        self.assertEqual(avatar["preferences"]["flat_type"], "4 ROOM")
        self.assertEqual(avatar["preferences"]["max_price"], 750000.0)
        self.assertEqual(avatar["preferences"]["school_priority"], "high")
        self.assertEqual(avatar["preferences"]["risk_tolerance"], "low")
        self.assertEqual(avatar["preferences"]["commute_priority"], "medium")

    def test_parse_commute_first_profile(self):
        avatar = parse_homeos_profile(
            "Single professional looking for executive flat below 1.1m, must be close to MRT, "
            "okay with some appreciation risk."
        )

        self.assertEqual(avatar["label"], "Commute HomeOS Agent")
        self.assertEqual(avatar["buyer_type"], "single")
        self.assertEqual(avatar["preferences"]["flat_type"], "EXECUTIVE")
        self.assertEqual(avatar["preferences"]["max_price"], 1100000.0)
        self.assertEqual(avatar["preferences"]["commute_priority"], "high")
        self.assertEqual(avatar["preferences"]["risk_tolerance"], "medium")


if __name__ == "__main__":
    unittest.main()
