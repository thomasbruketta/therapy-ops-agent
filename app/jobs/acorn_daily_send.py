"""CLI entrypoint for Acorn daily send job."""

from __future__ import annotations

import argparse
from datetime import date as Date

from app.jobs.tasks import acorn_daily_send


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Acorn daily send job.")
    parser.add_argument(
        "--date",
        required=True,
        type=Date.fromisoformat,
        help="Target date in YYYY-MM-DD format.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (default when no mode flag is passed).",
    )
    mode_group.add_argument(
        "--confirm-send",
        action="store_true",
        help="Confirm and execute outbound send.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    confirm_send = bool(args.confirm_send)
    dry_run = bool(args.dry_run) or not confirm_send

    result = acorn_daily_send(run_date=args.date, dry_run=dry_run)
    mode = "DRY-RUN" if dry_run else "CONFIRMED SEND"
    print(
        "acorn_daily_send complete "
        f"[{mode}] attempted={result['summary']['attempted_sends']} "
        f"successful={result['summary']['successful_sends']} "
        f"skipped={result['summary']['skipped']['total']} "
        f"failed={result['summary']['failed']['total']}"
    )


if __name__ == "__main__":
    main()
