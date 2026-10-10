import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("validate", Path(__file__).parents[1] / "validate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RunnerStatusTests(unittest.TestCase):
    def test_all_pass(self):
        self.assertEqual(module.exit_code([{"status": "PASS"}]), 0)

    def test_blocked_is_not_success(self):
        self.assertEqual(module.exit_code([{"status": "PASS"}, {"status": "BLOCKED"}]), 2)

    def test_failure_takes_precedence(self):
        self.assertEqual(module.exit_code([{"status": "BLOCKED"}, {"status": "FAIL"}]), 1)
