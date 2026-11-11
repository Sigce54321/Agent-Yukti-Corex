
from agents.fix_challenger import challenge_fix

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

print(result.model_dump_json(indent=2))
