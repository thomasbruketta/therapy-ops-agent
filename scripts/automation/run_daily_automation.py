"""Host-level automation runner for daily ACORN operations."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
REPO_ROOT = Path(__file__).resolve().parents[2]
APPLE_SCRIPT_PATH = REPO_ROOT / "scripts" / "automation" / "send_outlook_report.applescript"

CommandRunner = Callable[[list[str], Optional[Path], Optional[dict[str, str]]], "CommandResult"]
SleepFn = Callable[[float], None]


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


def _resolve_log_dir() -> Path:
    configured = os.getenv("ACORN_AUTOMATION_LOG_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Library" / "Logs" / "therapy-ops-agent"


def configure_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(tz=PACIFIC_TZ).strftime("%Y-%m-%d")
    log_path = log_dir / f"automation_{today}.log"

    logger = logging.getLogger()
    logger.handlers = []
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return log_path


def run_command(
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _extract_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def ensure_docker_ready(
    *,
    timeout_sec: int,
    command_runner: CommandRunner,
    sleep_fn: SleepFn,
) -> tuple[bool, str]:
    probe = command_runner(["docker", "info"], None, None)
    if probe.exit_code == 0:
        return True, "Docker already available"

    logging.info("Docker not ready; starting Docker Desktop")
    command_runner(["open", "-a", "Docker"], None, None)

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        sleep_fn(2.0)
        probe = command_runner(["docker", "info"], None, None)
        if probe.exit_code == 0:
            return True, "Docker became ready after startup"

    return False, f"Docker not ready after {timeout_sec} seconds"


def run_preflight_check(command_runner: CommandRunner) -> tuple[str, dict[str, Any], int]:
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "therapy-agent",
        "python",
        "-m",
        "app.jobs.simplepractice_auth_check",
        "--json-output",
    ]
    result = command_runner(command, REPO_ROOT, None)
    payload = _extract_json_payload(result.stdout)
    status = str(payload.get("status", "")).upper()

    if result.exit_code == 0 and status == "AUTHENTICATED":
        return "AUTHENTICATED", payload, result.exit_code

    if status == "MFA_REQUIRED" or "MFA" in f"{result.stdout}\n{result.stderr}".upper():
        return "MFA_REQUIRED", payload, result.exit_code

    return "FAILED", payload, result.exit_code


def run_send_for_date(
    *,
    target_date: str,
    dry_run_send: bool,
    command_runner: CommandRunner,
) -> tuple[str, dict[str, Any], int]:
    command = ["docker", "compose", "run", "--rm"]
    if not dry_run_send:
        command.extend(["-e", "ACORN_ENABLE_CONFIRM_SEND=true"])
    command.extend(
        [
            "therapy-agent",
            "python",
            "-m",
            "app.jobs.acorn_daily_send",
            "--date",
            target_date,
            "--source",
            "simplepractice",
            "--json-output",
        ]
    )
    command.append("--dry-run" if dry_run_send else "--confirm-send")

    result = command_runner(command, REPO_ROOT, None)
    payload = _extract_json_payload(result.stdout)

    if result.exit_code == 0:
        return "SUCCESS", payload, result.exit_code

    if "MFA" in f"{result.stdout}\n{result.stderr}".upper():
        return "MFA_REQUIRED", payload, result.exit_code

    return "FAILED", payload, result.exit_code


def _next_action(status: str) -> str:
    if status == "NEEDS_MFA":
        return "Run `make refresh-session MFA_CODE=<6-digit>` and re-run send."
    if status == "FAILED":
        return "Inspect automation logs and rerun `make send-today-now`."
    return "No action required."


def _build_email_body(report: dict[str, Any]) -> str:
    lines = [
        "ACORN automation report",
        "",
        f"Date: {report['date']}",
        f"Mode: {report['mode']}",
        f"Status: {report['status']}",
        f"Docker: {report['docker']['detail']}",
    ]

    preflight = report.get("preflight") or {}
    if preflight:
        lines.append(f"Preflight status: {preflight.get('status', 'unknown')}")

    send = report.get("send") or {}
    totals = send.get("totals") if isinstance(send, dict) else None
    if totals:
        lines.append(
            "Send totals: "
            f"evaluated={totals.get('evaluated', 0)} "
            f"eligible={totals.get('eligible', 0)} "
            f"sent_or_would_send={totals.get('sent_or_would_send', 0)} "
            f"skipped={totals.get('skipped', 0)} "
            f"errors={totals.get('errors', 0)}"
        )

    if send.get("summary_path"):
        lines.append(f"Summary artifact: {send['summary_path']}")
    if send.get("triage_path"):
        lines.append(f"Triage artifact: {send['triage_path']}")

    lines.extend(["", f"Next action: {report['next_action']}"])
    return "\n".join(lines)


def send_outlook_report(*, report_to: str, subject: str, body: str, command_runner: CommandRunner) -> bool:
    if not report_to:
        logging.warning("ACORN_AUTOMATION_REPORT_TO is empty; skipping Outlook report send")
        return False
    command = ["osascript", str(APPLE_SCRIPT_PATH), report_to, subject, body]
    result = command_runner(command, REPO_ROOT, None)
    if result.exit_code != 0:
        logging.error("Failed to send Outlook report: %s", result.stderr.strip())
        return False
    return True


def _normalize_status(preflight_status: str, send_status: str | None, mode: str) -> str:
    if mode == "preflight":
        if preflight_status == "AUTHENTICATED":
            return "SUCCESS"
        if preflight_status == "MFA_REQUIRED":
            return "NEEDS_MFA"
        return "FAILED"

    if preflight_status == "MFA_REQUIRED":
        return "NEEDS_MFA"
    if preflight_status != "AUTHENTICATED":
        return "FAILED"
    if send_status == "SUCCESS":
        return "SUCCESS"
    if send_status == "MFA_REQUIRED":
        return "NEEDS_MFA"
    return "FAILED"


def _write_report(log_dir: Path, report: dict[str, Any]) -> Path:
    stamp = datetime.now(tz=PACIFIC_TZ).strftime("%Y%m%dT%H%M%S")
    report_path = log_dir / f"report_{report['date']}_{report['mode']}_{stamp}.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report_path


def execute(
    *,
    mode: str,
    target_date: str,
    dry_run_send: bool,
    report_to: str,
    skip_email: bool,
    timeout_sec: int,
    command_runner: CommandRunner = run_command,
    sleep_fn: SleepFn = time.sleep,
) -> tuple[int, dict[str, Any]]:
    log_dir = _resolve_log_dir()
    configure_logging(log_dir)

    docker_ready, docker_detail = ensure_docker_ready(
        timeout_sec=timeout_sec,
        command_runner=command_runner,
        sleep_fn=sleep_fn,
    )

    report: dict[str, Any] = {
        "timestamp": datetime.now(tz=PACIFIC_TZ).isoformat(),
        "date": target_date,
        "mode": mode,
        "status": "FAILED",
        "next_action": "",
        "docker": {"ready": docker_ready, "detail": docker_detail},
        "preflight": {},
        "send": {},
    }

    if not docker_ready:
        report["status"] = "FAILED"
        report["next_action"] = _next_action("FAILED")
        report_path = _write_report(log_dir, report)
        logging.error("Docker unavailable; report saved to %s", report_path)
        if not skip_email:
            subject = f"[ACORN] FAILED - {target_date}"
            send_outlook_report(
                report_to=report_to,
                subject=subject,
                body=_build_email_body(report),
                command_runner=command_runner,
            )
        return 1, report

    preflight_status, preflight_payload, preflight_exit = run_preflight_check(command_runner)
    report["preflight"] = {
        "status": preflight_status,
        "exit_code": preflight_exit,
        "message": preflight_payload.get("message", ""),
    }

    send_status: str | None = None
    send_exit = None
    send_payload: dict[str, Any] = {}
    if mode == "send" and preflight_status == "AUTHENTICATED":
        send_status, send_payload, send_exit = run_send_for_date(
            target_date=target_date,
            dry_run_send=dry_run_send,
            command_runner=command_runner,
        )
        report["send"] = {
            "status": send_status,
            "exit_code": send_exit,
            "totals": send_payload.get("totals", {}),
            "summary_path": send_payload.get("summary_path", ""),
            "triage_path": send_payload.get("triage_path", ""),
        }

    status = _normalize_status(preflight_status, send_status, mode)
    report["status"] = status
    report["next_action"] = _next_action(status)

    report_path = _write_report(log_dir, report)
    logging.info("Automation report saved to %s", report_path)

    if not skip_email:
        subject = f"[ACORN] {status} - {target_date}"
        sent = send_outlook_report(
            report_to=report_to,
            subject=subject,
            body=_build_email_body(report),
            command_runner=command_runner,
        )
        report["report_email_sent"] = sent

    if status == "SUCCESS":
        return 0, report
    if status == "NEEDS_MFA":
        return 2, report
    return 1, report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run host automation for ACORN daily operations.")
    parser.add_argument(
        "--mode",
        choices=("preflight", "send"),
        default="send",
        help="Run preflight-only or full send workflow.",
    )
    parser.add_argument(
        "--date",
        default=datetime.now(tz=PACIFIC_TZ).date().isoformat(),
        help="Target date in YYYY-MM-DD format. Default is today's Pacific date.",
    )
    parser.add_argument(
        "--dry-run-send",
        action="store_true",
        help="In send mode, run ACORN job as dry-run instead of confirm-send.",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Skip sending Outlook report email.",
    )
    parser.add_argument(
        "--report-to",
        default=os.getenv("ACORN_AUTOMATION_REPORT_TO", "").strip(),
        help="Destination email for Outlook report.",
    )
    parser.add_argument(
        "--docker-timeout-sec",
        type=int,
        default=int(os.getenv("ACORN_DOCKER_READY_TIMEOUT_SEC", "120")),
        help="Maximum seconds to wait for Docker to become available.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    exit_code, report = execute(
        mode=args.mode,
        target_date=args.date,
        dry_run_send=bool(args.dry_run_send),
        report_to=args.report_to,
        skip_email=bool(args.skip_email),
        timeout_sec=int(args.docker_timeout_sec),
    )
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
