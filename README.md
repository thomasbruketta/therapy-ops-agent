# therapy-ops-agent

This repository includes a dedicated scheduler process and a live ACORN mobile-form send workflow.

For full operator/agent context and recent decisions, see `/Users/tbruketta/Dev/therapy-ops-agent/docs/AGENT_HANDOFF_2026-02-19.md`.

## Container-first execution

Default recommended run model is container-first:

- non-root container user (`uid=10001`)
- read-only root filesystem
- dropped Linux capabilities + `no-new-privileges`
- runtime state persisted in Docker volume at `/runtime`
- no PHI/session artifacts written into the repo workspace

Build and run with:

```bash
make build
make scheduler-once
make test
make send-today-now
```

For normal operation:

```bash
make scheduler
```

For one-off runs:

```bash
make dryrun DATE=2026-02-14
ACORN_ENABLE_CONFIRM_SEND=true make confirm-send DATE=2026-02-14
```

## Mac launchd automation (zero-cost)

This repository now includes a host-side automation runner for unattended daily execution on macOS.

- `07:45` Tue-Fri: preflight auth check (`SimplePractice` session validity)
- `08:00` Tue-Fri: live send execution (`confirm-send` with fail-closed opt-in)
- Post-run local JSON/log report with sanitized totals (no names/phones)

Automation files:

- Host runner: `scripts/automation/run_daily_automation.py`
- launchd templates: `ops/launchd/com.therapyops.acorn-preflight.plist`, `ops/launchd/com.therapyops.acorn-send.plist`
- install/uninstall helpers: `scripts/automation/install_launchd.sh`, `scripts/automation/uninstall_launchd.sh`

Setup:

```bash
# 1) set local report directory in .env.local
# ACORN_AUTOMATION_LOG_DIR=/Users/tbruketta/Dev/therapy-ops-agent/state/automation_logs

# 2) install launchd agents
./scripts/automation/install_launchd.sh

# 3) run one immediate check/send manually
make send-today-now
```

Dry-run validation of host runner without live send:

```bash
python3 scripts/automation/run_daily_automation.py --mode send --dry-run-send
```

Preflight-only execution:

```bash
python3 scripts/automation/run_daily_automation.py --mode preflight
```

If you need to remove automation:

```bash
./scripts/automation/uninstall_launchd.sh
```

Power/sleep requirements for clamshell mode:

- Keep Mac on power.
- Prevent overnight sleep during run windows.
- Keep external display/keyboard path active so scheduled jobs can run.

`confirm-send` is fail-closed and requires explicit opt-in:

```bash
# either export it in shell for one command...
ACORN_ENABLE_CONFIRM_SEND=true make confirm-send DATE=2026-02-14

# ...or set in .env.local before planned send windows
# ACORN_ENABLE_CONFIRM_SEND=true
make confirm-send DATE=2026-02-14
```

`confirm-send` also requires `ACORN_CLINICIAN_ID` to be set to a specific clinician value (not blank, `ALL`, or `replace_me`).

To refresh SimplePractice session state:

```bash
make refresh-session MFA_CODE=123456
```

To validate only auth/session state (no send):

```bash
docker compose run --rm therapy-agent python -m app.jobs.simplepractice_auth_check --json-output
```

To probe authenticated SimplePractice pages for selector discovery:

```bash
docker compose run --rm therapy-agent python -m app.jobs.simplepractice_probe
```

Probe output defaults to `/runtime/artifacts/selector_probe` in container mode and can be overridden with `SIMPLEPRACTICE_PROBE_OUTPUT_DIR`.

HTTPS is enforced for `ACORN_LOGIN_URL`, `ACORN_MOBILE_FORM_URL`, and `SIMPLEPRACTICE_BASE_URL` unless `ACORN_ALLOW_INSECURE_URLS=true` is explicitly set for local debugging.

## PHI handling

- Runtime outputs default to `/runtime/...` (Docker volume storage, not repo workspace).
- Run artifacts are redacted and use recipient tokens rather than names/phone numbers.
- Browser session state defaults to `/runtime/browser/simplepractice_session.json` and persists across `docker compose run` calls.
- To delete all runtime data immediately, run: `make purge-runtime`

## Host approval policy

To reduce prompts without broad host risk, pre-approve only container orchestration prefixes:

- `docker compose build`
- `docker compose up`
- `docker compose run`

Do not pre-approve broad destructive host commands (`rm`, `git reset`, unrestricted shells).

## Scheduler framework

The project uses **APScheduler** (`BlockingScheduler` + `CronTrigger`) for reliable cron-style scheduling with explicit timezone support.

## Daily schedule

`acorn_daily_send` is registered in `app/jobs/scheduler.py` to run at:

- **08:00**
- **Timezone:** `America/Los_Angeles`
- **Workdays:** from `ACORN_WORK_DAYS` (or `WORK_DAYS`), default `tue,wed,thu,fri`

The scheduler logs:

- Job registration and first `next run`
- Each completed/failed execution
- `last run` (completion timestamp) and `next run`

## Running modes

Install dependencies:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Container mode installs these dependencies in image build (`make build`), so host install is optional for container-first usage.

## Recipient input

The daily job supports two recipient sources:

- `simplepractice` (default): extracts today's clients from SimplePractice for `SIMPLEPRACTICE_CLINICIAN_ID`
- `recipients`: reads `ACORN_RECIPIENTS_PATH` (default `state/acorn_recipients.json`)

For `simplepractice`, recipients are filtered to appointments whose service code matches `ACORN_REQUIRED_SERVICE_CODES` (default `90837`).

For `simplepractice`, refresh auth session state first:

```bash
python -m app.jobs.simplepractice_session --mfa-code 123456
```

For `recipients`, sample schema is provided at `docs/samples/acorn_recipients.example.json`.

Each item must include:

- `full_name` (used to compute `client_id` as lowercase first+last, no spaces/punctuation)
- `phone` (E.164 preferred)

Start dedicated scheduler process (for production/background worker):

```bash
python -m app.jobs.scheduler
```

Run one-off/manual execution (without scheduler loop):

```bash
python -m app.jobs.scheduler --once
```

Manual dry-run/confirm-send for a specific date:

```bash
python -m app.jobs.acorn_daily_send --date 2026-02-13 --dry-run
python -m app.jobs.acorn_daily_send --date 2026-02-13 --confirm-send
python -m app.jobs.acorn_daily_send --date 2026-02-13 --dry-run --source recipients
python -m app.jobs.acorn_daily_send --date 2026-02-13 --dry-run --json-output
```

## Troubleshooting

- Docker not ready: start Docker Desktop and rerun `make send-today-now`.
- Preflight reports `NEEDS_MFA`: run `make refresh-session MFA_CODE=<6-digit>`.
- Local reports are written to `ACORN_AUTOMATION_LOG_DIR` (default under `~/Library/Logs/therapy-ops-agent` if unset).
- launchd verification:
  - `launchctl print gui/$UID/com.therapyops.acorn-preflight`
  - `launchctl print gui/$UID/com.therapyops.acorn-send`
