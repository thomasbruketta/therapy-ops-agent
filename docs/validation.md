# Validation Matrix

This matrix defines confidence gates for promoting runs from dry-run to confirm-send.

## Stage 1: Static and packaging sanity
- **Command:** `python -m compileall app tests`
- **Pass criteria:** No syntax/import compile errors.
- **Blockers:** Any compile failure.

## Stage 2: Unit and workflow integration tests
- **Command:** `pytest tests/test_unit_behaviors.py tests/test_dispatch_workflow.py tests/test_integration_smoke.py`
- **Pass criteria:** All tests pass.
- **Blockers:** Any failing behavior around idempotency, masking, dispatch, or triage generation.

## Stage 3: E2E dry-run smoke test
- **Command:** `pytest -m e2e tests/e2e/test_daily_send_dry_run.py`
- **Pass criteria:**
  - Dry-run does not call outbound sender.
  - Triage JSON and Markdown artifacts are produced.
  - Summary counts match fixture records.
  - Idempotency store is untouched in dry-run.
- **Blockers:** Any send side effect in dry-run or missing artifacts.

## Stage 4: Manual confirm-send rehearsal (gated)
- **Command:**
  - Dry-run first: `python -m app.jobs.acorn_daily_send --date YYYY-MM-DD --dry-run`
  - Confirm-send after approval: `python -m app.jobs.acorn_daily_send --date YYYY-MM-DD --confirm-send`
- **Pass criteria:**
  - Dry-run triage reviewed and accepted.
  - Credentials/session are valid.
  - Confirm-send has expected volume and no critical failures.
- **Blockers:** Any critical triage item, auth/session issues, or unexpected send volume.
