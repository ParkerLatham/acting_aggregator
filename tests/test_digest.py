"""Run with:  python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from filters import classify, extract_age, extract_pay, find_terms  # noqa: E402
from main import normalize_url  # noqa: E402
from models import Listing  # noqa: E402

CFG = {
    "include": {
        "role_terms": ["actor", "actors", "audition", "extras"],
        "noise_terms": ["recital"],
        "location_terms": ["Atlanta", "GA"],
        "age_terms": ["18-25"],
    },
    "red_flags": ["pay to audition", "registration fee"],
    "flag_terms": ["unpaid"],
}


def make(text, local=False):
    return Listing(title="Test", source="s", url="http://x", text=text, is_local=local)


class FilterTests(unittest.TestCase):
    def test_whole_word_matching(self):
        self.assertEqual(find_terms("born again in Georgia", ["GA"]), [])
        self.assertEqual(find_terms("Atlanta, GA 30303", ["GA"]), ["GA"])

    def test_keep_needs_role_and_location(self):
        self.assertEqual(classify(make("Actors needed in Atlanta"), CFG), "keep")
        self.assertEqual(classify(make("Actors needed in Boston"), CFG), "exclude")
        self.assertEqual(classify(make("Bake sale in Atlanta"), CFG), "exclude")

    def test_local_sources_skip_location_check(self):
        self.assertEqual(classify(make("Audition for a play", local=True), CFG), "keep")

    def test_red_flag_excluded_unpaid_flagged(self):
        self.assertEqual(classify(make("Actor roles, pay to audition, Atlanta"), CFG), "exclude")
        item = make("Unpaid actor role in Atlanta")
        self.assertEqual(classify(item, CFG), "flag")
        self.assertTrue(item.reasons)

    def test_noise_excluded(self):
        self.assertEqual(classify(make("Piano recital audition Atlanta"), CFG), "exclude")

    def test_pay_extraction(self):
        self.assertEqual(extract_pay("Pay is $150/day for extras"), "$150/day")
        self.assertIsNone(extract_pay("Tickets cost $10 at the door"))
        self.assertIsNone(extract_pay("Open audition"))

    def test_age_extraction(self):
        self.assertEqual(extract_age("Women ages 18-25"), "Ages 18–25")
        self.assertIsNone(extract_age("Event on 2026-10-01"))

    def test_url_normalisation(self):
        self.assertEqual(normalize_url("https://a.com/p?utm_source=x&id=2#top"), "https://a.com/p?id=2")


if __name__ == "__main__":
    unittest.main()
