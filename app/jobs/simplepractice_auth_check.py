"""Check whether the persisted SimplePractice session is still authenticated."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from app.adapters.simplepractice_adapter_ui import SimplePracticeAdapterUI
from app.utils.runtime_paths import runtime_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate SimplePractice auth session state.")
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit machine-readable JSON payload.",
    )
    parser.set_defaults(headless=None)
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Run browser in headless mode.",
    )
    parser.add_argument(
        "--headed",
        dest="headless",
        action="store_false",
        help="Run browser in headed mode.",
    )
    return parser.parse_args()


def _emit(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, sort_keys=True))
        return
    print(payload["message"])


def _resolve_headless(arg_value: bool | None) -> bool:
    if arg_value is not None:
        return arg_value
    return os.getenv("SIMPLEPRACTICE_HEADLESS", "true").strip().lower() != "false"


def run_auth_check(*, headless: bool | None = None) -> tuple[int, dict[str, Any]]:
    state_path = Path(
        os.getenv(
            "SIMPLEPRACTICE_SESSION_STATE_PATH",
            str(runtime_path("browser", "simplepractice_session.json")),
        )
    )

    if not state_path.exists():
        return 2, {
            "status": "MFA_REQUIRED",
            "message": (
                f"SimplePractice session state not found at {state_path}. "
                "Run `python -m app.jobs.simplepractice_session --mfa-code <code>` to refresh session state."
            ),
            "state_path": str(state_path),
        }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=_resolve_headless(headless))
            context = browser.new_context(storage_state=str(state_path))
            page = context.new_page()
            adapter = SimplePracticeAdapterUI(page=page, session_state_path=state_path)
            authenticated = adapter.has_authenticated_session()
            context.close()
            browser.close()
    except Exception as exc:
        return 1, {
            "status": "ERROR",
            "message": f"SimplePractice auth check failed: {exc}",
            "state_path": str(state_path),
        }

    if authenticated:
        return 0, {
            "status": "AUTHENTICATED",
            "message": "SimplePractice session state is authenticated.",
            "state_path": str(state_path),
        }

    return 2, {
        "status": "MFA_REQUIRED",
        "message": (
            "SimplePractice session is not authenticated. "
            "Run `python -m app.jobs.simplepractice_session --mfa-code <code>` to refresh session state."
        ),
        "state_path": str(state_path),
    }


def main() -> int:
    args = _parse_args()
    exit_code, payload = run_auth_check(headless=args.headless)
    _emit(payload, json_output=bool(args.json_output))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
