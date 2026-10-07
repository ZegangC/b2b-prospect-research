import copy
import json
import unittest
from pathlib import Path

from src.research_rules import evaluate_batch, grade_for


class ResearchRuleTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "synthetic_batch.json"
        self.records = json.loads(path.read_text(encoding="utf-8"))

    def rejected(self, fragment):
        result = evaluate_batch(self.records)
        self.assertFalse(result["passed"])
        self.assertTrue(any(fragment in e for e in result["errors"]), result)

    def test_fixture_covers_all_grades(self):
        result = evaluate_batch(self.records)
        self.assertTrue(result["passed"])
        self.assertEqual(result["grades"], {"A": 1, "B": 1, "C": 1, "D": 1})
        self.assertTrue(result["all_research_terminal"])
        self.assertEqual(len(result["contact_routes_needing_review"]), 2)

    def test_grade_boundaries(self):
        for total, expected in [(0, "D"), (44, "D"), (45, "C"), (64, "C"), (65, "B"), (79, "B"), (80, "A"), (100, "A")]:
            with self.subTest(total=total):
                self.assertEqual(grade_for(total), expected)

    def test_grade_change_does_not_restart_terminal_research(self):
        self.records[2]["scores"]["reachability"] = 15
        self.records[2]["grade"] = "B"
        result = evaluate_batch(self.records)
        self.assertTrue(result["passed"])
        self.assertEqual(result["pending_research_ids"], [])

    def test_only_nonterminal_records_enter_queue(self):
        self.records[1]["status"] = "pending"
        result = evaluate_batch(self.records)
        self.assertTrue(result["passed"])
        self.assertEqual(result["pending_research_ids"], ["DEMO-002"])
        self.assertFalse(result["all_research_terminal"])

    def test_grade_mismatch_rejected(self):
        self.records[0]["grade"] = "D"
        self.rejected("grade must be A")

    def test_invalid_scores_rejected(self):
        for invalid in (36, -1, True, "35", float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                self.records[0]["scores"]["process_fit"] = invalid
                self.rejected("invalid score")

    def test_duplicate_company_id_rejected(self):
        self.records[1]["company_id"] = "DEMO-001"
        self.rejected("duplicate company_id")

    def test_duplicate_entity_rejected(self):
        self.records[1]["entity_key"] = " AURORA-COMPOUNDS "
        self.rejected("duplicate country/entity_key")

    def test_evidence_date_required(self):
        del self.records[0]["evidence"][0]["checked_on"]
        self.rejected("source URL and ISO date")

    def test_broken_contact_evidence_reference_rejected(self):
        self.records[0]["contacts"][0]["source_id"] = "NONEXISTENT"
        self.rejected("references missing evidence")

    def test_generic_inbox_cannot_be_assigned_to_person(self):
        self.records[0]["contacts"][0]["person_name"] = "Fictional Person"
        self.rejected("must not be assigned to a person")

    def test_person_contact_requires_explicit_attribution(self):
        self.records[1]["contacts"][0]["attribution"] = "guessed"
        self.rejected("explicit source attribution")

    def test_public_email_does_not_prove_delivery(self):
        self.records[0]["contacts"][0]["delivery_status"] = "confirmed"
        self.rejected("separate evidence")

    def test_repeated_contact_rejected(self):
        self.records[0]["contacts"].append(copy.deepcopy(self.records[0]["contacts"][0]))
        self.rejected("duplicate contact route")

    def test_missing_contact_can_be_terminal(self):
        result = evaluate_batch([self.records[2]])
        self.assertTrue(result["passed"])
        self.assertTrue(result["all_research_terminal"])

    def test_empty_batch_is_not_completion(self):
        result = evaluate_batch([])
        self.assertFalse(result["passed"])
        self.assertFalse(result["all_research_terminal"])


if __name__ == "__main__":
    unittest.main()
