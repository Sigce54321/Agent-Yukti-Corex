# Docker-to-backend integration validation

Branch: `feature/docker-e2e-validation`. Scope: Member 4 tests and validation notes only. No production, frontend, agent, Dockerfile, sandbox-policy, verification or report-generator code changed.

## Inspection findings

- `core/workflow.py` calls real baseline and regression wrappers, requires a reproduced baseline failure, invokes the independent Challenger before patch application, restores the original complete working-copy file between failed attempts, and allows an initial repair plus two retries (`MAX_REPAIR_RETRIES = 2`). Infrastructure errors stop retries. Verified repairs stop at `awaiting_approval`.
- `verification/test_runner.py` selects language commands and converts Docker execution outcomes into `passed`, `failed`, `error` or `not_run`. Infrastructure failure flags take precedence over apparently passing logs. `verification/verifier.py` requires failed baseline followed by passed regression.
- `sandbox/container_runner.py` mounts only a sanitized disposable copy, applies non-root/offline/resource restrictions, checks the container exit state and attempts cleanup in `finally`. `sandbox/security.py` excludes credentials and Git metadata and rejects unsafe paths, links and other unsafe entries. Container deletion is restricted to owned/managed containers.
- Python uses pytest; Java supports offline Maven or conservative standalone Java assertion contracts; JavaScript supports npm/Jest or Node built-in tests; HTML/CSS use installed Playwright tooling. Image availability alone did not establish adapter/backend integration.
- Existing maintained workflow integration tests mocked patch operations, test results, the final verifier and report generation. Existing sandbox/verifier tests separately cover many fail-closed cases, but did not execute the complete Docker-to-workflow chain.

## Added tests

`tests/test_docker_backend_integration.py` adds isolated temporary repositories and controlled AI/GitHub responses. No real agent is imported by the dispatcher; unexpected external calls fail. The tests initialize only temporary local Git boundaries, with no commits or configured remotes.

| Requirement | Validation |
| --- | --- |
| Failing baseline reproduced inside Docker | Real assertions through the adapters and baseline wrapper for Python, Java, JavaScript, HTML and CSS |
| Same test passes after controlled repair | Real patch manager changes only a separate working copy; same adapter/regression wrapper reruns unchanged tests |
| No reproduced baseline means no verified repair | Verifier rejects actual passing-baseline evidence; deterministic backend test stops before agents and blocks approval |
| Docker errors/security/timeouts fail closed | Actual missing executable and timeout executions, actual host path-policy rejection, and backend boundary fault injection including misleading passing logs |
| Challenger rejection blocks approval | Deterministic real-workflow test checks no patch application, regression or report, and rejected approval |
| Maximum three repair attempts | Real-workflow test checks exactly three proposals/regressions, two retries, original-file restoration before each new proposal, and no report/approval |
| Cleanup and original preservation | Fixtures compare original repository bytes, check disposable mount deletion and absence of test-owned containers after success/error/timeout, and remove their own temporary repositories |
| Accurate Fix Passport handoff | Full workflow passes complete baseline/regression logs, exit codes, commands and outcomes to the real PDF generator; actual PDF creation checked |
| Human approval before PR creation | No Git write/PR path runs automatically; explicit approval without PR works and repeated approval fails; failure cases reject PR-producing approval |

The complete real Docker/workflow/patch/verifier/passport test uses Python. Other languages are validated through the actual adapter + baseline + patch + regression + verifier path. Their AI-driven localization/repair quality is outside these deterministic tests.

## Cross-team defect: Fix Passport rendering

The workflow hands the generator `verification = {passed, summary, baseline: {...}, regression: {...}}` accurately. `reports/fix_passport.py` renders top-level `test_status`, `exit_code`, `logs`/`message` instead of those nested records. Consequently the PDF omits actual baseline/regression logs and exit codes, even though the complete evidence reaches the generator and PDF generation succeeds. Its verification table defaults the test status to `passed` and does not display the actual nested exit codes.

`test_passport_renders_nested_evidence` is an explicit expected failure for the missing rendered logs. It first requires the real workflow to reach approval and generate its report; unrelated setup/workflow failures remain normal failures. The report owner should render both nested evidence records and their status, exit code, command, duration and logs. This component was not silently rewritten.

## Reproduce

Maintained Member 4 tests (no legacy root scripts):

```powershell
.venv/Scripts/python.exe -m pytest tests/test_workflow_integration.py tests/test_verifier.py tests/test_test_runner.py tests/test_security.py tests/test_container_runner.py tests/test_patch_manager.py -q -p no:cacheprovider
```

Opt in to real local Docker tests; use existing images only, with no pull/build:

```powershell
$env:YUKTICOREX_DOCKER_E2E = '1'
.venv/Scripts/python.exe -m pytest tests/test_docker_backend_integration.py -v -ra -p no:cacheprovider
```

Without the environment flag, live tests skip explicitly. Docker/required image failures after opting in fail tests rather than silently skipping them. The new test module requires the project's ReportLab dependency for real passport generation.

## Practical demonstration limits

- Docker Engine and four local image tags were confirmed. The tests use offline, dependency-free sample contracts; this does not prove arbitrary Maven/npm dependencies are cached or arbitrary external repositories work offline.
- Successful, failed and timeout sandbox copies/containers must disappear; the backend's full original clone/repair working copy and task records are intentionally retained for human review/PR creation. Test fixtures remove only their test-owned trees. No production retention/expiry policy is implemented by these tests.
- Live Gemini behavior, real GitHub issue retrieval/cloning, pushing and creating PRs are deliberately untested. No remote GitHub repositories were modified.
- Temporary fixtures have no committed baseline. Their real patch-manager diff exercises the untracked-file fallback; committed-repository diff behavior remains covered by the maintained patch-manager tests.

## Results

Maintained Member 4 suite: **45 passed, 131 subtests passed**.

Final opt-in integration run: **16 passed, 1 xfailed in 200.75 seconds**. All eight live-Docker test cases passed, including five language baseline/repair/regression cases, the complete Python backend-to-passport path, a real timeout and a real execution error. The expected failure is exclusively the documented PDF nested-evidence rendering defect. Container/workspace cleanup and original-repository snapshots passed for every live case.

Final read-only audit: **0 managed containers, 0 `docker-e2e-*` repository trees, 0 `.yuktic-task-*` sanitized trees** remained. Working-tree changes are limited to this report and the new integration test module.

The first integration run exposed an invalid task ID in the new fixture, not a production defect. The fixture was corrected to the backend's `task-` plus twelve-hex-character format before the final passing run. No production workaround was added.
