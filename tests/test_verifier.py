"""Verification decisions must preserve unavailable and failed test outcomes."""

import unittest

from verification.verifier import verify_fix


class VerifierTests(unittest.TestCase):
    def test_only_reproduced_bug_followed_by_pass_verifies(self):
        for before in ("passed", "failed", "error", "not_run"):
            for after in ("passed", "failed", "error", "not_run"):
                with self.subTest(baseline=before, regression=after):
                    baseline = {"test_status": before}
                    regression = {"test_status": after}
                    result = verify_fix(baseline, regression)
                    self.assertEqual(result["passed"], before == "failed" and after == "passed")
                    self.assertIs(result["baseline"], baseline)
                    self.assertIs(result["regression"], regression)
                    self.assertEqual(set(result), {"passed", "summary", "baseline", "regression"})

    def test_malformed_results_never_verify(self):
        for value in (None, [], {}, {"test_status": []}, {"test_status": "unknown"}):
            with self.subTest(value=value):
                self.assertFalse(verify_fix(value, {"test_status": "passed"})["passed"])
                self.assertFalse(verify_fix({"test_status": "failed"}, value)["passed"])
