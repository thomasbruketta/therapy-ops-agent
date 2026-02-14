DC := docker compose
DATE ?= $(shell date +%F)
MFA_CODE ?=

.PHONY: build scheduler scheduler-once dryrun confirm-send refresh-session purge-runtime test

build:
	$(DC) build therapy-agent

scheduler:
	$(DC) up therapy-agent

scheduler-once:
	$(DC) run --rm therapy-agent python -m app.jobs.scheduler --once

dryrun:
	$(DC) run --rm therapy-agent python -m app.jobs.acorn_daily_send --date $(DATE) --dry-run --source simplepractice

confirm-send:
	$(DC) run --rm therapy-agent python -m app.jobs.acorn_daily_send --date $(DATE) --confirm-send --source simplepractice

refresh-session:
	@if [ -z "$(MFA_CODE)" ]; then echo "MFA_CODE is required"; exit 1; fi
	$(DC) run --rm therapy-agent python -m app.jobs.simplepractice_session --mfa-code $(MFA_CODE) --headless

purge-runtime:
	$(DC) run --rm therapy-agent python -m app.jobs.purge_runtime

test:
	$(DC) run --rm therapy-agent python -m pytest -q -p no:cacheprovider
