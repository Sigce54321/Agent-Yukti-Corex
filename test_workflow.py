import inspect

import core.workflow as workflow


def test_workflow_module_imports():
    """Verify that the backend workflow module imports successfully."""

    assert workflow is not None


def test_workflow_has_public_functions():
    """Verify that workflow exposes callable functions."""

    functions = [
        name
        for name, member in inspect.getmembers(workflow, inspect.isfunction)
        if not name.startswith("_")
    ]

    assert len(functions) > 0, (
        "No public workflow functions found in core/workflow.py"
    )