"""CLI and runtime entrypoint for Acorn daily send workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.utils.identity import compute_client_id
from app.utils.idempotency import IdempotencyStore, build_idempotency_key
from app.utils.phone import validate_phone

MESSAGE_TEMPLATE = "Good morning! Please complete your Acorn assessment before session today. See you soon!"
FORM_VALUE = "Adult-Ver14-UNIV-28236-Online.pdf"
SEND_VIA = "text"
DEFAULT_ARTIFACT_ROOT = "/tmp/therapy-ops-agent/artifacts/runs"
DEFAULT_RECIPIENTS_PATH = "state/acorn_recipients.json"
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


@dataclass
class Recipient:
    full_name: str
    phone: str


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
        help="Confirm and execute the send.",
    )
    parser.add_argument(
        "--recipients-path",
        default=os.getenv("ACORN_RECIPIENTS_PATH", DEFAULT_RECIPIENTS_PATH),
        help="JSON file path containing recipients. Default: state/acorn_recipients.json",
    )
    parser.add_argument(
        "--recipient",
        action="append",
        default=[],
        help="Inline recipient in the format 'First Last|+15551234567'. May be repeated.",
    )
    parser.add_argument(
        "--source",
        choices=("recipients", "simplepractice"),
        default=os.getenv("ACORN_RECIPIENT_SOURCE", "simplepractice"),
        help="Recipient source: recipients file/inline or SimplePractice extraction.",
    )
    return parser.parse_args()


def _build_run_id(mode: str) -> str:
    suffix = "dryrun" if mode == "dry-run" else "confirm"
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"{stamp}_{suffix}_001"


def _recipient_token(full_name: str, phone: str) -> str:
    salt = os.getenv("ACORN_PRIVACY_SALT", "therapy-ops")
    raw = f"{salt}|{full_name}|{phone}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def _parse_inline_recipient(value: str) -> Recipient:
    try:
        full_name, phone = [segment.strip() for segment in value.split("|", 1)]
    except ValueError as exc:
        raise ValueError(f"Invalid --recipient format: {value!r}") from exc
    if not full_name or not phone:
        raise ValueError(f"Invalid --recipient format: {value!r}")
    return Recipient(full_name=full_name, phone=phone)


def _load_recipients(path: str | Path, inline: list[str]) -> list[Recipient]:
    recipients = [_parse_inline_recipient(item) for item in inline]
    if recipients:
        return recipients

    payload_path = Path(path)
    if not payload_path.exists():
        return []

    raw = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Recipients JSON must be a list of objects.")

    loaded: list[Recipient] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        full_name = str(item.get("full_name", "")).strip()
        phone = str(item.get("phone", "")).strip()
        if full_name and phone:
            loaded.append(Recipient(full_name=full_name, phone=phone))
    return loaded


def _load_recipients_from_simplepractice(target_date: Date) -> list[Recipient]:
    clinician_id = os.getenv("SIMPLEPRACTICE_CLINICIAN_ID", "").strip()
    if not clinician_id:
        raise ValueError("SIMPLEPRACTICE_CLINICIAN_ID is required for --source simplepractice.")

    from playwright.sync_api import sync_playwright
    from app.adapters.simplepractice_adapter_ui import SimplePracticeAdapterUI

    username = os.getenv("SIMPLEPRACTICE_USERNAME", "").strip() or None
    password = os.getenv("SIMPLEPRACTICE_PASSWORD", "").strip() or None
    mfa_code = os.getenv("SIMPLEPRACTICE_MFA_CODE", "").strip() or None
    state_path = Path(os.getenv("SIMPLEPRACTICE_SESSION_STATE_PATH", "browser/simplepractice_session.json"))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=os.getenv("SIMPLEPRACTICE_HEADLESS", "true").lower() != "false"
        )
        context_kwargs: dict[str, Any] = {}
        if state_path.exists():
            context_kwargs["storage_state"] = str(state_path)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        adapter = SimplePracticeAdapterUI(page=page, session_state_path=state_path)

        authenticated = adapter.ensure_authenticated(
            username=username,
            password=password,
            mfa_code=mfa_code,
        )
        if not authenticated:
            raise RuntimeError(
                "SimplePractice session is not authenticated. "
                "Run `python -m app.jobs.simplepractice_session --mfa-code <code>` to refresh session state."
            )
        adapter.save_session_state()

        extracted = adapter.fetch_daily_recipients(
            target_date=target_date,
            clinician_id=clinician_id,
            timezone_name=os.getenv("ACORN_TIMEZONE", "America/Los_Angeles"),
        )
        context.close()
        browser.close()

    return [Recipient(full_name=item["full_name"], phone=item["phone"]) for item in extracted]


def _render_output_path(default_name: str, env_template_key: str, *, mode: str, date: Date) -> Path:
    template = os.getenv(env_template_key, "").strip()
    if template:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return Path(
            template.format(
                date=date.isoformat(),
                mode=mode.replace("-", "_"),
                timestamp=timestamp,
            )
        )
    root = Path(os.getenv("ACORN_ARTIFACT_ROOT", "/tmp/therapy-ops-agent/artifacts/runs"))
    return root / default_name


def _write_artifacts(
    *,
    run_id: str,
    mode: str,
    target_date: Date,
    evaluated: int,
    eligible: int,
    sent: int,
    skipped: int,
    errors: int,
    idempotency_store_path: str,
    new_keys_written: int,
    findings: list[str],
) -> tuple[Path, Path]:
    summary_default = f"summary_{target_date.isoformat()}_{mode.replace('-', '_')}.json"
    triage_default = f"triage_{target_date.isoformat()}_{mode.replace('-', '_')}.md"
    summary_path = _render_output_path(
        summary_default,
        "ACORN_SUMMARY_PATH_TEMPLATE",
        mode=mode,
        date=target_date,
    )
    triage_path = _render_output_path(
        triage_default,
        "ACORN_TRIAGE_PATH_TEMPLATE",
        mode=mode,
        date=target_date,
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    triage_path.parent.mkdir(parents=True, exist_ok=True)

    start_iso = datetime.combine(target_date, time(8, 0), tzinfo=PACIFIC_TZ).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    end_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    totals_key = "sent" if mode == "confirm-send" else "would_send"

    payload = {
        "run_id": run_id,
        "mode": mode,
        "source": {
            "system": "acorn",
            "access_method": "browser-automation",
        },
        "window": {
            "since": start_iso,
            "until": end_iso,
        },
        "totals": {
            "evaluated": evaluated,
            "eligible": eligible,
            totals_key: sent,
            "skipped": skipped,
            "errors": errors,
        },
        "idempotency": {
            "store_path": idempotency_store_path,
            "new_keys_written": new_keys_written,
        },
        "notes": findings,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    disposition = "SUCCESS" if errors == 0 else "REVIEW_REQUIRED"
    md_lines = [
        f"# Triage Report - {'Confirm Send' if mode == 'confirm-send' else 'Dry Run'}",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Mode:** `{mode}`",
        "- **Source Access:** `acorn/browser-automation`",
        f"- **Disposition:** `{disposition}`",
        "",
        "## Findings",
    ]
    if findings:
        for idx, line in enumerate(findings, start=1):
            md_lines.append(f"{idx}. {line}")
    else:
        md_lines.append("1. **Info** - No findings.")
    triage_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return summary_path, triage_path


def run(
    *,
    date: Date,
    dry_run: bool,
    confirm_send: bool,
    recipients_path: str | Path = DEFAULT_RECIPIENTS_PATH,
    inline_recipients: list[str] | None = None,
    recipient_source: str = "simplepractice",
) -> dict[str, str]:
    """Run Acorn daily send with dry-run/confirm-send controls."""
    inline_recipients = inline_recipients or []
    if recipient_source == "simplepractice":
        recipients = _load_recipients_from_simplepractice(date)
    else:
        recipients = _load_recipients(recipients_path, inline_recipients)
    if not recipients:
        raise ValueError(
            "No recipients available. Provide --recipient or populate ACORN_RECIPIENTS_PATH JSON."
        )

    mode = "confirm-send" if confirm_send else "dry-run"
    run_id = _build_run_id(mode)
    idempotency_store_path = os.getenv(
        "ACORN_IDEMPOTENCY_STORE_PATH",
        "/tmp/therapy-ops-agent/state/acorn_idempotency_store.json",
    )
    store = IdempotencyStore(idempotency_store_path)

    evaluated = len(recipients)
    eligible = 0
    sent = 0
    skipped = 0
    errors = 0
    new_keys_written = 0
    findings: list[str] = []

    def _process_recipient(recipient: Recipient, sender: Any | None) -> None:
        nonlocal eligible, sent, skipped, errors, new_keys_written
        name_parts = recipient.full_name.strip().split()
        if len(name_parts) < 2:
            skipped += 1
            token = _recipient_token(recipient.full_name, recipient.phone)
            findings.append(f"**High** - Skipped recipient `{token}` due to missing first/last name parts.")
            return

        normalized_phone = validate_phone(recipient.phone)
        if not normalized_phone:
            skipped += 1
            token = _recipient_token(recipient.full_name, recipient.phone)
            findings.append(f"**High** - Skipped recipient `{token}` due to invalid phone.")
            return

        client_id = compute_client_id([name_parts[0], name_parts[-1]])
        idempotency_key = build_idempotency_key(date.isoformat(), client_id)
        token = _recipient_token(recipient.full_name, recipient.phone)
        if store.has_been_sent(idempotency_key):
            skipped += 1
            findings.append(f"**Low** - Skipped recipient `{token}` by idempotency dedupe.")
            return

        eligible += 1
        if dry_run:
            sent += 1
            findings.append(f"**Info** - Would send to recipient `{token}`.")
            return

        if sender is None:
            errors += 1
            findings.append(f"**Critical** - Sender unavailable for recipient `{token}`.")
            return

        result = sender.send_mobile_form(
            clinician_id=os.getenv("ACORN_CLINICIAN_ID", "ALL"),
            form_value=FORM_VALUE,
            client_id=client_id,
            phone=normalized_phone,
            message=MESSAGE_TEMPLATE,
            send_via=SEND_VIA,
            start_session=0,
            text_from=os.getenv("ACORN_TEXT_FROM", "ACORN"),
        )
        if result.success and sender.verify_send_success(result.context):
            sent += 1
            store.mark_sent(idempotency_key)
            new_keys_written += 1
            findings.append(f"**Info** - Sent successfully to recipient `{token}`.")
            return

        errors += 1
        findings.append(f"**Critical** - Send failed or unverified for recipient `{token}`.")

    if dry_run:
        for recipient in recipients:
            _process_recipient(recipient, sender=None)
    else:
        acorn_user = os.getenv("ACORN_USERNAME", "").strip()
        acorn_password = os.getenv("ACORN_PASSWORD", "").strip()
        if not acorn_user or not acorn_password:
            raise ValueError("ACORN_USERNAME and ACORN_PASSWORD are required for confirm-send mode.")

        from playwright.sync_api import sync_playwright
        from app.adapters.acorn_adapter_ui import AcornAdapterUI

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=os.getenv("ACORN_HEADLESS", "true").lower() != "false")
            context = browser.new_context()
            page = context.new_page()
            sender = AcornAdapterUI(page=page)
            sender.login(username=acorn_user, password=acorn_password)
            for recipient in recipients:
                _process_recipient(recipient, sender=sender)
            context.close()
            browser.close()

    summary_path, triage_path = _write_artifacts(
        run_id=run_id,
        mode=mode,
        target_date=date,
        evaluated=evaluated,
        eligible=eligible,
        sent=sent,
        skipped=skipped,
        errors=errors,
        idempotency_store_path=idempotency_store_path,
        new_keys_written=new_keys_written,
        findings=findings,
    )

    return {
        "run_id": run_id,
        "summary_path": str(summary_path),
        "triage_path": str(triage_path),
    }


def main() -> None:
    args = _parse_args()
    confirm_send = bool(args.confirm_send)
    dry_run = bool(args.dry_run) or not confirm_send
    result = run(
        date=args.date,
        dry_run=dry_run,
        confirm_send=confirm_send,
        recipients_path=args.recipients_path,
        inline_recipients=args.recipient,
        recipient_source=args.source,
    )
    print(
        f"Run {result['run_id']} complete. "
        f"summary={result['summary_path']} triage={result['triage_path']}"
    )


if __name__ == "__main__":
    main()
