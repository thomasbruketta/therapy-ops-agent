# Agent Handoff (2026-02-19)

## Purpose
This file is the current-state handoff for future agents/operators so they can work in this repo without additional verbal context.

## System Summary
- Product: automated ACORN text/form sends using SimplePractice as recipient source.
- Runtime model: container-first (`docker compose`) with hardened container config.
- Scheduler: APScheduler job in `/Users/tbruketta/Dev/therapy-ops-agent/app/jobs/scheduler.py` (08:00 America/Los_Angeles, Tue-Fri by default).
- Sensitive runtime state is stored in Docker volume-backed `/runtime` (not repo workspace).

## Current Deployment/Run Model
- Local machine operation is active and validated.
- Main service command for continuous mode:
  - `make scheduler`
- One-off send commands:
  - Dry-run: `make dryrun DATE=YYYY-MM-DD`
  - Confirm-send: see "Live Send Controls" below.
- Host automation command:
  - `make send-today-now`

## Host Automation (Mac launchd)
- Objective: unattended Tue-Fri morning operations at near-zero cost.
- Runner:
  - `/Users/tbruketta/Dev/therapy-ops-agent/scripts/automation/run_daily_automation.py`
- launchd templates:
  - `/Users/tbruketta/Dev/therapy-ops-agent/ops/launchd/com.therapyops.acorn-preflight.plist` (07:45)
  - `/Users/tbruketta/Dev/therapy-ops-agent/ops/launchd/com.therapyops.acorn-send.plist` (08:00)
- Installer/uninstaller:
  - `/Users/tbruketta/Dev/therapy-ops-agent/scripts/automation/install_launchd.sh`
  - `/Users/tbruketta/Dev/therapy-ops-agent/scripts/automation/uninstall_launchd.sh`

Expected statuses from runner:
- `SUCCESS`
- `NEEDS_MFA` (requires `make refresh-session MFA_CODE=<code>`)
- `FAILED`

Host env vars:
- `ACORN_DOCKER_READY_TIMEOUT_SEC` (default `120`)
- `ACORN_AUTOMATION_LOG_DIR` (recommended: repo-local state directory)

## Live Send Controls (Fail-Closed)
- `ACORN_ENABLE_CONFIRM_SEND` must be `true` for live sends.
- `ACORN_CLINICIAN_ID` must be present and specific (cannot be blank, `ALL`, or `replace_me`).
- Code guard is in:
  - `/Users/tbruketta/Dev/therapy-ops-agent/app/jobs/acorn_daily_send.py`

## Recipient Eligibility Rules (Current)
- Recipient source `simplepractice` is filtered to service code(s) in `ACORN_REQUIRED_SERVICE_CODES`.
- Default is `90837` only.
- This prevents consults/assessments/other calendar event types from being sent ACORN.
- Filter logic is in:
  - `/Users/tbruketta/Dev/therapy-ops-agent/app/adapters/simplepractice_adapter_ui.py`

## Client ID Normalization Rules (Current)
- Client ID generation now uses first and last names only.
- Middle initials/middle names are excluded.
- Hyphens are preserved (critical fix for names like `DREWMICHAUD-GOETZ`).
- Logic is in:
  - `/Users/tbruketta/Dev/therapy-ops-agent/app/utils/identity.py`

Examples:
- `John C. Doe` -> `johndoe`
- `DREW MICHAUD-GOETZ` -> `drewmichaud-goetz`

## Known Operational Learnings From This Thread
1. Docker daemon availability is a common blocker.
   - Symptom: cannot connect to `docker.sock`.
   - Fix: start Docker Desktop and verify with `docker info`.

2. SimplePractice MFA/session handling:
   - Session state now persists across runs via volume `/runtime/browser/simplepractice_session.json`.
   - MFA may still be required when upstream session expires.
   - `make refresh-session MFA_CODE=<code>` refreshes state.

3. `make confirm-send` caveat:
   - The Makefile checks `ACORN_ENABLE_CONFIRM_SEND=true` on host before running.
   - Depending on shell/env propagation, the container may still not see this variable.
   - Reliable one-off pattern:
     - `docker compose run --rm -e ACORN_ENABLE_CONFIRM_SEND=true therapy-agent python -m app.jobs.acorn_daily_send --date YYYY-MM-DD --confirm-send --source simplepractice`

4. One-off correction path for bad client_id inputs:
   - If a single recipient needs resend with exact custom client_id, use a one-off script/command to call `AcornAdapterUI.send_mobile_form` directly with that exact `client_id`.
   - This was used to resend `DREWMICHAUD-GOETZ` successfully.

## Key Files For Future Agents
- Scheduler: `/Users/tbruketta/Dev/therapy-ops-agent/app/jobs/scheduler.py`
- Daily send entrypoint: `/Users/tbruketta/Dev/therapy-ops-agent/app/jobs/acorn_daily_send.py`
- SimplePractice auth preflight check: `/Users/tbruketta/Dev/therapy-ops-agent/app/jobs/simplepractice_auth_check.py`
- SimplePractice adapter: `/Users/tbruketta/Dev/therapy-ops-agent/app/adapters/simplepractice_adapter_ui.py`
- ACORN adapter: `/Users/tbruketta/Dev/therapy-ops-agent/app/adapters/acorn_adapter_ui.py`
- Identity/client_id rules: `/Users/tbruketta/Dev/therapy-ops-agent/app/utils/identity.py`
- Runtime purge: `/Users/tbruketta/Dev/therapy-ops-agent/app/jobs/purge_runtime.py`
- Container config: `/Users/tbruketta/Dev/therapy-ops-agent/docker-compose.yml`, `/Users/tbruketta/Dev/therapy-ops-agent/Dockerfile`
- Commands: `/Users/tbruketta/Dev/therapy-ops-agent/Makefile`

## Standard Operating Workflow
1. Validate runtime:
   - `make build`
   - `make test`
2. Refresh SimplePractice session when needed:
   - `make refresh-session MFA_CODE=<6-digit>`
3. Execute day workflow:
   - Dry-run: `make dryrun DATE=YYYY-MM-DD`
   - Review summary/triage.
   - Live send with explicit enable flag:
     - preferred robust form:
       - `docker compose run --rm -e ACORN_ENABLE_CONFIRM_SEND=true therapy-agent python -m app.jobs.acorn_daily_send --date YYYY-MM-DD --confirm-send --source simplepractice`
4. If needed, purge runtime state:
   - `make purge-runtime`

## Automated Morning Workflow (Current)
1. Install launchd agents:
   - `./scripts/automation/install_launchd.sh`
2. 07:45 preflight job runs auth check:
   - `python -m app.jobs.simplepractice_auth_check --json-output`
3. 08:00 send job runs full automation:
   - preflight gate, then `confirm-send` if authenticated
4. Local JSON/log report written after each run (status + totals, no PHI)
5. If `NEEDS_MFA`, run:
   - `make refresh-session MFA_CODE=<6-digit>`

## Security/HIPAA Posture (Implemented)
- Container hardening: non-root, read-only root FS, dropped capabilities, `no-new-privileges`.
- Artifact outputs are redacted (recipient tokens instead of direct name/phone in triage notes).
- Runtime/session data not written to repo.
- Session/screenshot/state files use tightened filesystem permissions.
- HTTPS enforced for integration URLs unless explicitly overridden for debugging.

## Recent High-Impact Commits
- `f8cfd4b` service-code filter (default 90837)
- `f3135dc` hyphen-preserving client IDs + middle-name exclusion
- `d66fb96` persistent runtime volume for session/idempotency/artifacts
- `ba6ec57` fail-closed clinician ID requirement for confirm-send
- `4699ab1` security hardening pass

## Immediate Next-Agent Checklist
- Confirm `.env.local` has:
  - `ACORN_CLINICIAN_ID=<real id>`
  - `SIMPLEPRACTICE_CLINICIAN_ID=<real id>`
  - `ACORN_REQUIRED_SERVICE_CODES=90837` (unless intentionally changed)
- Run:
  - `make build && make test`
- For next live send day:
  - refresh session if needed
  - dry-run, review, then confirm-send
