# therapy-ops-agent

This repository now includes a dedicated scheduler process for recurring jobs.

## Scheduler framework

The project uses **APScheduler** (`BlockingScheduler` + `CronTrigger`) for reliable cron-style scheduling with explicit timezone support.

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

Run one-off/manual execution (without scheduler loop):

```bash
python -m app.jobs.scheduler --once
```
