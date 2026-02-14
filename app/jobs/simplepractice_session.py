"""Refresh and persist a SimplePractice authenticated browser session."""

from __future__ import annotations

import argparse
import os

from playwright.sync_api import sync_playwright

from app.adapters.simplepractice_adapter_ui import SimplePracticeAdapterUI


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh SimplePractice session state.")
    parser.add_argument(
        "--mfa-code",
        default=os.getenv("SIMPLEPRACTICE_MFA_CODE", ""),
        help="6-digit MFA code from authenticator app (if prompted).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode. Default is headed for easier MFA troubleshooting.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    username = os.getenv("SIMPLEPRACTICE_USERNAME", "").strip()
    password = os.getenv("SIMPLEPRACTICE_PASSWORD", "").strip()
    if not username or not password:
        raise ValueError("SIMPLEPRACTICE_USERNAME and SIMPLEPRACTICE_PASSWORD are required.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=bool(args.headless))
        context = browser.new_context()
        page = context.new_page()
        adapter = SimplePracticeAdapterUI(page=page)

        adapter.login(
            username=username,
            password=password,
            mfa_code=args.mfa_code or None,
            remember_device=True,
        )
        if not adapter.has_authenticated_session():
            raise RuntimeError("SimplePractice login did not reach authenticated session.")

        state_path = adapter.save_session_state()
        print(f"Saved SimplePractice session state to {state_path}")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
