# therapy-ops-agent

This repository includes:
- a dedicated scheduler process for recurring jobs
- a top-level `acorn` CLI for manual operations (`run` and `auth simplepractice`)

## Install

```bash
pip install -r requirements.txt
pip install -e .
```

`pip install -e .` exposes the `acorn` console command via `pyproject.toml`.

## Runnable commands

### Scheduler process

Start dedicated scheduler process (production/background worker):

```bash
python -m app.jobs.scheduler
```

Run one-off/manual execution (without scheduler loop):

```bash
python -m app.jobs.scheduler --once
```

### Daily-send module entrypoint

```bash
python -m app.jobs.acorn_daily_send --date 2026-02-13 --dry-run
python -m app.jobs.acorn_daily_send --date 2026-02-13 --confirm-send
```

### ACORN CLI

```bash
acorn run --mode dry-run --window-minutes 20
acorn run --mode confirm-send --since 2026-02-13T00:00:00Z
acorn auth simplepractice --interactive-login --save-session browser/simplepractice_session.json
```

Equivalent module entrypoint:

```bash
python -m app.cli run --mode dry-run --window-minutes 20
```

## Scheduler framework

The project uses **APScheduler** (`BlockingScheduler` + `CronTrigger`) for reliable cron-style scheduling with explicit timezone support.

`acorn_daily_send` is registered in `app/jobs/scheduler.py` to run at:
- **08:00**
- **Timezone:** `America/Los_Angeles`
