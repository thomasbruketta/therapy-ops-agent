# therapy-ops-agent

This repository includes a scheduler process and a runnable daily send workflow with dry-run support.

## Scheduler framework

The project uses **APScheduler** (`BlockingScheduler` + `CronTrigger`) for cron-style scheduling with explicit timezone support.

## Daily schedule

`acorn_daily_send` is registered in `app/jobs/scheduler.py` to run at:

- **08:00**
- **Timezone:** `America/Los_Angeles`

The scheduler logs:

- Job registration and first `next run`
- Each completed/failed execution
- `last run` (completion timestamp) and `next run`

## Running modes

Install dependencies:

```bash
pip install -r requirements.txt
```

Start dedicated scheduler process (for production/background worker):

```bash
python -m app.jobs.scheduler
```

Run one-off/manual execution through scheduler task (defaults to dry-run):

```bash
python -m app.jobs.scheduler --once
```

Run daily workflow directly in dry-run mode:

```bash
python -m app.jobs.acorn_daily_send --date 2026-01-15 --dry-run
```

Run daily workflow directly in confirm-send mode:

```bash
python -m app.jobs.acorn_daily_send --date 2026-01-15 --confirm-send
```

## Validation gates

Use the staged validation matrix before promotion to confirm-send:

- `docs/validation.md`
