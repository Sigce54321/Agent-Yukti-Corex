
from core.workflow import run_repair_workflow

result = run_repair_workflow(
    issue_text="""
    The calculator crashes when dividing a number by zero.
    Expected: Handle division by zero safely.
    Actual: ZeroDivisionError.
    """,
    repository_code="""
    File: calculator.py

    def divide(a, b):
        return a / b
    """,
)

print("========== YUKTIC-OREX WORKFLOW ==========")

for stage, output in result.items():
    print(f"\n--- {stage.upper()} ---")
    print(output)

