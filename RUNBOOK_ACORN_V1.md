# ACORN v1 Operations Runbook

This runbook describes how to configure, run, and troubleshoot the ACORN workflow that reads appointment/client data and produces triage outputs.

## 1) Setup

### Prerequisites
- Python 3.10+
- Installed dependencies from `requirements.txt`
- Credentials/session details for source and destination systems
- Writable local paths for artifacts, browser session state, and idempotency store

### Initial bootstrap
1. Copy environment template:
   ```bash
   cp .env.example .env
   ```
2. Fill in credentials and environment values in `.env`.
3. Ensure runtime can read `.env`.
4. Create required directories:
   ```bash
   mkdir -p artifacts/runs state browser
   ```

## 2) Credentials and Environment Variables

Reference `.env.example` for required keys, including:
- `SIMPLEPRACTICE_*`
- `ACORN_*`
- `ACORN_ARTIFACT_ROOT`
- `ACORN_IDEMPOTENCY_STORE_PATH`

## 3) Scheduler Operation

### Recommended cadence
- Daily at 08:00 America/Los_Angeles via `python -m app.jobs.scheduler`
- For frequent checks, use process manager scheduling around `python -m app.jobs.acorn_daily_send --dry-run`

### Example cron (UTC)
```cron
*/15 * * * * cd /workspace/therapy-ops-agent && /usr/bin/env bash -lc 'source .env && python -m app.jobs.acorn_daily_send --date "$(date -u +\%F)" --dry-run >> artifacts/runs/scheduler.log 2>&1'
```

## 4) Manual CLI Examples

### Dry-run (safe preview)
```bash
python -m app.jobs.acorn_daily_send --date 2026-02-13 --dry-run
```

### Confirm-send (writes/sends)
```bash
python -m app.jobs.acorn_daily_send --date 2026-02-13 --confirm-send
```

## 5) Safety Notes: Dry-Run vs Confirm-Send

### `dry-run`
- Produces summary/triage artifacts.
- **Does not send/create/update records in Acorn**.
- Should be default for unattended schedules.

### `confirm-send`
- Executes outbound actions.
- Writes idempotency markers to prevent duplicate sends.
- Use only after reviewing the latest dry-run triage output.

## 6) Troubleshooting

### Symptom: Empty run but expected records
- Confirm source loader and credentials/session are configured.
- Re-run dry-run and inspect generated triage artifacts.

### Symptom: Duplicate sends or dedupe misses
- Inspect `ACORN_IDEMPOTENCY_STORE_PATH` availability and permissions.
- Ensure scheduler jobs are not overlapping.

### Symptom: Artifact write errors
- Verify `ACORN_ARTIFACT_ROOT` exists and is writable.
- Check disk space and permissions.

## 7) Validation and Promotion

Use `docs/validation.md` as the promotion checklist from dry-run confidence to confirm-send.
