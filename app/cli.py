"""Top-level ACORN command line interface."""

from __future__ import annotations

import argparse
import json
from datetime import date as Date
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from app.jobs.acorn_daily_send import run as run_daily_send


MODE_CHOICES = ("dry-run", "confirm-send")


def _date_from_since(value: str) -> Date:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--since must be an ISO-8601 datetime (example: 2026-02-13T00:00:00Z)"
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acorn", description="ACORN operations CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute the daily ACORN send workflow")
    run_parser.add_argument(
        "--mode",
        choices=MODE_CHOICES,
        default="dry-run",
        help="Execution mode: dry-run (safe preview) or confirm-send (writes/sends)",
    )
    run_parser.add_argument("--date", type=Date.fromisoformat, help="Target date in YYYY-MM-DD format")
    run_parser.add_argument(
        "--since",
        type=_date_from_since,
        help="Target ISO-8601 datetime; date portion is used when --date is omitted",
    )
    run_parser.add_argument("--window-minutes", type=int, help="Optional lookback window for scheduler mode")
    run_parser.add_argument("--summary-out", type=Path, help="Optional explicit summary artifact path")
    run_parser.add_argument("--triage-out", type=Path, help="Optional explicit triage artifact path")
    run_parser.add_argument("--client-id", help="Optional filter to a single client")
    run_parser.add_argument("--practitioner-id", help="Optional filter to a single practitioner")
    run_parser.set_defaults(handler=_handle_run)

    auth_parser = subparsers.add_parser("auth", help="Authentication/session commands")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)
    sp_parser = auth_subparsers.add_parser(
        "simplepractice",
        help="Bootstrap a SimplePractice browser automation session state file",
    )
    sp_parser.add_argument(
        "--interactive-login",
        action="store_true",
        help="Require interactive bootstrap flow to continue",
    )
    sp_parser.add_argument("--save-session", type=Path, required=True, help="Path to save session state")
    sp_parser.set_defaults(handler=_handle_auth_simplepractice)

    return parser


def _resolve_target_date(args: argparse.Namespace) -> Date:
    if args.date:
        return args.date
    if args.since:
        return args.since
    return datetime.now(tz=timezone.utc).date()


def _handle_run(args: argparse.Namespace) -> int:
    target_date = _resolve_target_date(args)
    confirm_send = args.mode == "confirm-send"
    dry_run = not confirm_send

    run_daily_send(date=target_date, dry_run=dry_run, confirm_send=confirm_send)

    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(
            json.dumps(
                {
                    "mode": args.mode,
                    "date": target_date.isoformat(),
                    "window_minutes": args.window_minutes,
                    "client_id": args.client_id,
                    "practitioner_id": args.practitioner_id,
                },
                indent=2,
            )
            + "\n"
        )
    if args.triage_out:
        args.triage_out.parent.mkdir(parents=True, exist_ok=True)
        args.triage_out.write_text(
            "# ACORN run triage\n"
            f"- mode: {args.mode}\n"
            f"- date: {target_date.isoformat()}\n"
            f"- window_minutes: {args.window_minutes}\n"
            f"- client_id: {args.client_id}\n"
            f"- practitioner_id: {args.practitioner_id}\n"
        )
    return 0


def _handle_auth_simplepractice(args: argparse.Namespace) -> int:
    if not args.interactive_login:
        raise SystemExit("--interactive-login is required for session bootstrap")

    args.save_session.parent.mkdir(parents=True, exist_ok=True)
    args.save_session.write_text(
        json.dumps(
            {
                "provider": "simplepractice",
                "interactive_login": True,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Saved SimplePractice session bootstrap at {args.save_session}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
