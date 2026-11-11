
from unittest.mock import patch

from agents.fix_challenger import challenge_fix


@patch("agents.fix_challenger.generate_text")
def test_challenge_fix_returns_result(mock_generate_text):
    mock_generate_text.return_value = """
{
    "verdict": "APPROVE",
    "findings": [],
    "potential_regressions": [],
    "required_corrections": [],
    "explanation": "The patch handles division by zero."
}
"""

    result = challenge_fix(
        issue_analysis="Division by zero crashes the calculator.",
        bug_location="calculator.py: divide function",
        repository_code="""def divide(a, b):
    return a / b""",
        proposed_patch="""--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,4 @@
 def divide(a, b):
+    if b == 0:
+        raise ValueError("Cannot divide by zero")
     return a / b"""
    )

    assert result.verdict == "APPROVE"
    assert result.findings == []
    assert result.potential_regressions == []
    assert result.required_corrections == []
    assert result.explanation == "The patch handles division by zero."

    mock_generate_text.assert_called_once()
