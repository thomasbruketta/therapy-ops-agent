# ACORN v1 Operations Runbook

This runbook describes how to configure, run, and troubleshoot the ACORN workflow that reads from **SimplePractice via browser automation (human-style login session)** and syncs/queues outbound updates to Acorn.

> Assumption for v1: SimplePractice access is performed through an authenticated web session (not a public vendor API integration).

## 1) Setup

### Prerequisites
- Python 3.10+ (or your runtime for the ACORN CLI/scheduler).
- Browser automation runtime used by your agent (for example, Playwright + Chromium).
- Access to:
  - SimplePractice web user credentials with required permissions.
  - SimplePractice MFA method used by the service account/operator.
  - Acorn API credentials.
- Writable local path for:
  - generated artifacts (summary + triage outputs)
  - browser session/profile state
  - idempotency state store.

### Initial bootstrap
1. Copy environment template:
   ```bash
   cp .env.example .env
   ```
2. Fill in credentials and environment values in `.env`.
3. Ensure runtime can read `.env` (direnv, dotenv loader, process manager env injection, etc.).
4. Create required directories:
   ```bash
   mkdir -p artifacts/runs artifacts/samples state browser
   ```

## 2) Credentials and Environment Variables

Reference `.env.example` for all required keys. At minimum you must provide:

- SimplePractice (web automation):
  - `SIMPLEPRACTICE_BASE_URL`
  - `SIMPLEPRACTICE_ORG_SLUG`
  - `SIMPLEPRACTICE_USERNAME`
  - `SIMPLEPRACTICE_PASSWORD`
  - `SIMPLEPRACTICE_MFA_MODE`
  - `SIMPLEPRACTICE_SESSION_STATE_PATH`
- Acorn:
  - `ACORN_BASE_URL`
  - `ACORN_API_KEY`
  - `ACORN_TIMEOUT_SECONDS`
- Runtime controls:
  - `ACORN_TIMEZONE`
  - `ACORN_ARTIFACT_ROOT`
  - `ACORN_SUMMARY_PATH_TEMPLATE`
  - `ACORN_TRIAGE_PATH_TEMPLATE`
  - `ACORN_IDEMPOTENCY_STORE_PATH`

## 3) Scheduler Operation

### Recommended cadence
- Run every 15 minutes for standard operations.
- Run hourly in low-volume environments.

### Example cron (UTC)
```cron
*/15 * * * * cd /workspace/therapy-ops-agent && /usr/bin/env bash -lc 'set -a; source .env; set +a; acorn run --mode dry-run --window-minutes 20 >> artifacts/runs/scheduler.log 2>&1'
```

### Scheduler mode guidance
- **Normal daily schedule:** use `--mode dry-run` for continuous visibility with zero external side effects.
- **Controlled send windows:** execute a supervised `--mode confirm-send` run (manually or gated job) after triage review.
- **Session hygiene:** refresh browser session state periodically (for example daily) and immediately after credential or MFA policy changes.

## 4) Manual CLI Examples

> Replace `acorn` with the actual executable if your deployment uses a different command.

### Refresh browser session state
```bash
acorn auth simplepractice \
  --interactive-login \
  --save-session "browser/simplepractice_session.json"
```

### Dry-run (safe preview)
```bash
acorn run \
  --mode dry-run \
  --since "2026-02-13T00:00:00Z" \
  --summary-out "artifacts/runs/summary_2026-02-13_dryrun.json" \
  --triage-out "artifacts/runs/triage_2026-02-13_dryrun.md"
```

### Confirm-send (writes/sends)
```bash
acorn run \
  --mode confirm-send \
  --since "2026-02-13T00:00:00Z" \
  --summary-out "artifacts/runs/summary_2026-02-13_confirm.json" \
  --triage-out "artifacts/runs/triage_2026-02-13_confirm.md"
```

### Narrow scope by patient/practitioner (example)
```bash
acorn run --mode dry-run --client-id CL-20491 --practitioner-id PR-001
```

## 5) Safety Notes: Dry-Run vs Confirm-Send

### `dry-run`
- Reads SimplePractice records through the browser automation path.
- Produces summary/triage artifacts.
- **Does not send/create/update records in Acorn**.
- Should be default for unattended schedules unless explicit promotion is approved.

### `confirm-send`
- Executes outbound actions to Acorn.
- Writes idempotency markers to prevent duplicate sends.
- Must be used only after reviewing the most recent dry-run triage output.

### Safety checklist before confirm-send
1. Latest dry-run triage has no **Critical** unresolved issues.
2. Browser login/session state is valid and not near expiration.
3. Credential expiry/rotation checks are green.
4. `ACORN_IDEMPOTENCY_STORE_PATH` is writable and healthy.
5. Expected send volume is within normal range.
6. Operator confirms change window and rollback owner.

## 6) Troubleshooting

### Symptom: SimplePractice login fails
- Verify username/password and org slug.
- Validate MFA mode and that the runner can satisfy challenge requirements.
- Refresh session via interactive login and rerun dry-run.

### Symptom: Browser/session expired mid-run
- Rebuild session state file at `SIMPLEPRACTICE_SESSION_STATE_PATH`.
- Confirm system clock skew is < 60 seconds.
- Check for concurrent jobs invalidating each other's sessions.

### Symptom: Empty run but expected records
- Confirm `--since`/window values and timezone (`ACORN_TIMEZONE`).
- Validate source data exists in SimplePractice for that interval.
- Re-run dry-run with a wider interval.

### Symptom: Duplicate sends or dedupe misses
- Inspect `ACORN_IDEMPOTENCY_STORE_PATH` availability and permissions.
- Ensure scheduler jobs are not overlapping.
- Confirm deterministic idempotency key composition has not changed.

### Symptom: Artifact write errors
- Verify `ACORN_ARTIFACT_ROOT` exists and is writable.
- Ensure path templates resolve to valid directories.
- Check disk space and inode exhaustion.

## 7) Triage Interpretation Guide

Use triage output to decide whether to proceed to confirm-send.

### Severity levels
- **Critical**: stop; do not confirm-send until resolved.
- **High**: resolve unless an explicit exception is approved.
- **Medium**: acceptable for dry-run; assess impact before confirm-send.
- **Low/Info**: operational notes; monitor trends.

### Decision matrix
- **No Critical + no High + expected volume** → safe to schedule/execute confirm-send.
- **Any Critical** → block confirm-send, open incident.
- **High severity extraction/login errors** → block and route to automation owner.
- **Only Medium/Low warnings** → operator discretion with documented approval.

### Triage routing
- Login/session/MFA issues → platform/automation owner.
- Mapping/schema issues → integration engineer.
- Clinical/business rule conflicts → operations lead.
- Repeated idempotency anomalies → data reliability on-call.

## 8) Sample Artifacts Location

Sample outputs are committed under:
- `docs/samples/summary_dry_run.json`
- `docs/samples/triage_dry_run.md`
- `docs/samples/summary_confirm_send.json`
- `docs/samples/triage_confirm_send.md`
