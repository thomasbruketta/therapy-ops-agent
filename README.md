# therapy-ops-agent

This repository includes a dedicated scheduler process and a live ACORN mobile-form send workflow.

## Container-first execution

Default recommended run model is container-first:

- non-root container user (`uid=10001`)
- read-only root filesystem
- dropped Linux capabilities + `no-new-privileges`
- runtime data only in container tmpfs (`/tmp/therapy-ops-agent`)
- no PHI/session artifacts written into the repo workspace

Build and run with:

```bash
make build
make scheduler-once
make test
```

For normal operation:

```bash
make scheduler
```

For one-off runs:

```bash
make dryrun DATE=2026-02-14
make confirm-send DATE=2026-02-14
```

To refresh SimplePractice session state:

```bash
make refresh-session MFA_CODE=123456
```

To probe authenticated SimplePractice pages for selector discovery:

```bash
docker compose run --rm therapy-agent python -m app.jobs.simplepractice_probe
```

Probe output defaults to `/tmp/therapy-ops-agent/artifacts/selector_probe` and can be overridden with `SIMPLEPRACTICE_PROBE_OUTPUT_DIR`.

## PHI handling

- Runtime outputs default to `/tmp/therapy-ops-agent/...` (ephemeral storage).
- Run artifacts are redacted and use recipient tokens rather than names/phone numbers.
- Browser session state defaults to `/tmp/therapy-ops-agent/browser/simplepractice_session.json`.
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
```
