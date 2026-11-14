import csv
import tempfile
import unittest
from pathlib import Path

from complaint_system import (
    clean_text, validate_row, load_and_clean, baseline_keyword_classifier,
    classify_with_review_flag, sentence_split, first_k_summary,
    frequency_summary, CATEGORIES, REQUIRED_FIELDS, DATA_DIR, OUTPUT_DIR
)

class ComplaintProjectTests(unittest.TestCase):
    def test_clean_text_lowercases_and_collapses_spaces(self):
        self.assertEqual(clean_text("  NOT   Delivered!!! "), "not delivered")

    def test_clean_text_preserves_negation(self):
        self.assertIn("not", clean_text("NOT delivered"))

    def test_clean_text_removes_html_markup(self):
        self.assertEqual(clean_text("<b>Broken</b> item"), "broken item")

    def test_valid_row_is_accepted(self):
        row = {
            "complaint_id":"T001", "date":"2026-10-01", "channel":"Web",
            "category":"Delivery", "complaint_text":"Parcel is late",
            "status":"Open", "resolution_days":""
        }
        self.assertEqual(validate_row(row, set()), [])

    def test_duplicate_id_is_rejected(self):
        row = {
            "complaint_id":"T001", "date":"2026-10-01", "channel":"Web",
            "category":"Delivery", "complaint_text":"Parcel is late",
            "status":"Open", "resolution_days":""
        }
        self.assertIn("DUPLICATE_ID", validate_row(row, {"T001"}))

    def test_blank_text_is_rejected(self):
        row = {
            "complaint_id":"T002", "date":"2026-10-01", "channel":"Web",
            "category":"Delivery", "complaint_text":" ",
            "status":"Open", "resolution_days":""
        }
        self.assertIn("EMPTY_TEXT", validate_row(row, set()))

    def test_invalid_date_is_rejected(self):
        row = {
            "complaint_id":"T003", "date":"not-a-date", "channel":"Web",
            "category":"Delivery", "complaint_text":"Parcel is late",
            "status":"Open", "resolution_days":""
        }
        self.assertIn("INVALID_DATE", validate_row(row, set()))

    def test_invalid_category_is_rejected(self):
        row = {
            "complaint_id":"T004", "date":"2026-10-01", "channel":"Web",
            "category":"Other", "complaint_text":"Parcel is late",
            "status":"Open", "resolution_days":""
        }
        self.assertIn("INVALID_CATEGORY", validate_row(row, set()))

    def test_baseline_detects_delivery_keywords(self):
        self.assertEqual(baseline_keyword_classifier("The parcel arrived late"), "Delivery")

    def test_negation_triggers_review_flag(self):
        label, reason = classify_with_review_flag("The parcel was not late")
        self.assertEqual(label, "UNCERTAIN")
        self.assertEqual(reason, "NEGATION_REQUIRES_REVIEW")

    def test_sentence_split(self):
        self.assertEqual(sentence_split("First issue. Second issue!"), ["First issue.", "Second issue!"])

    def test_first_k_summary_limits_sentence_count(self):
        summary, ids = first_k_summary("One. Two. Three.", 2)
        self.assertEqual(ids, [0, 1])
        self.assertEqual(summary, "One. Two.")

    def test_frequency_summary_returns_original_order(self):
        summary, ids, scores = frequency_summary(
            "General opening. Battery battery became hot. Battery issue continues.", 2
        )
        self.assertEqual(ids, sorted(ids))
        self.assertTrue(summary)
        self.assertTrue(scores)

    def test_full_fixture_has_expected_accept_reject_counts(self):
        accepted, rejected = load_and_clean()
        self.assertEqual(len(accepted), 48)
        self.assertEqual(len(rejected), 2)

if __name__ == "__main__":
    unittest.main()
