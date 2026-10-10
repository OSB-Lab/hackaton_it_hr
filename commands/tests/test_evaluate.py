"""Harness unit tests only: these invented labels are NOT a DS evaluation dataset."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("evaluate", Path(__file__).parents[1] / "evaluate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixtures = self.root / "fixtures.json"
        self.labels = self.root / "labels.json"
        self.cases = [{"id": f"case{i}", "scenario": scenario, "profileId": "same-profile",
                       "variant": variant, "candidateIds": ["a", "b", "c"], "input": {}}
                      for i, (scenario, variant) in enumerate(zip(["weak", "medium", "strong"], "ABC"))]
        self.data = {"schemaVersion": 1, "version": "UNIT-TEST-ONLY", "blueprintVersions": ["test"], "cases": self.cases}
        self.truth = {"schemaVersion": 1, "version": "UNIT-TEST-ONLY", "fixtureVersion": "UNIT-TEST-ONLY",
                      "provenance": {"independentOfTuning": True, "reference": "UNIT-TEST-ONLY"},
                      "labels": {c["id"]: {"a": True, "b": False, "c": True} for c in self.cases}}

    def run_eval(self, orders=None):
        self.fixtures.write_text(json.dumps(self.data))
        self.labels.write_text(json.dumps(self.truth))
        values = orders or [["a", "b", "c"]] * 9
        outputs = [SimpleNamespace(stdout=json.dumps({"algorithmVersion": "unit-test", "orderedCandidateIds": v})) for v in values]
        with patch.object(module.subprocess, "run", side_effect=outputs):
            return module.evaluate(self.fixtures, self.labels, ["unit-test-adapter"])

    def test_missing_is_blocked_not_perfect_precision(self):
        result = module.evaluate()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["precisionAt3"])

    def test_hand_calculated_precision(self):
        result = self.run_eval()
        self.assertAlmostEqual(result["precisionAt3"], 2 / 3)
        self.assertEqual(result["determinism"], "PASS")

    def test_short_list_keeps_denominator_three(self):
        self.assertAlmostEqual(self.run_eval([["a"]] * 9)["precisionAt3"], 1 / 3)

    def test_nondeterminism_fails(self):
        with self.assertRaisesRegex(ValueError, "Non-deterministic"):
            self.run_eval([["a", "b", "c"], ["b", "a", "c"], ["a", "b", "c"]])

    def test_duplicate_ids_fail(self):
        with self.assertRaisesRegex(ValueError, "Invalid ranked"):
            self.run_eval([["a", "a"]])

    def test_incomplete_labels_fail(self):
        del self.truth["labels"]["case0"]["c"]
        with self.assertRaisesRegex(ValueError, "every candidate"):
            self.run_eval()

    def test_tuning_labels_rejected(self):
        self.truth["provenance"]["independentOfTuning"] = False
        with self.assertRaisesRegex(ValueError, "Independent"):
            self.run_eval()

    def test_missing_pairs_blocked(self):
        for case in self.cases:
            case["variant"] = None
        self.assertEqual(self.run_eval()["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
