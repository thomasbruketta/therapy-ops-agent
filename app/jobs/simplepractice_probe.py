"""Probe authenticated SimplePractice pages and dump DOM metadata for selector discovery."""

from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def _page_snapshot(page) -> dict:
    return page.evaluate(
        """() => {
      const fields = Array.from(document.querySelectorAll('input,select,textarea')).slice(0, 150).map((el, idx) => ({
        idx,
        tag: el.tagName.toLowerCase(),
        type: el.getAttribute('type') || null,
        id: el.id || null,
        name: el.getAttribute('name'),
        placeholder: el.getAttribute('placeholder'),
        dataTestid: el.getAttribute('data-testid'),
      }));
      const links = Array.from(document.querySelectorAll('a')).slice(0, 200).map((el, idx) => ({
        idx,
        text: (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
        href: el.getAttribute('href'),
        dataTestid: el.getAttribute('data-testid'),
      })).filter(item => item.text || item.href);
      return {
        title: document.title,
        url: location.href,
        bodyStart: (document.body?.innerText || '').slice(0, 1800),
        fields,
        links,
      };
    }"""
    )


def main() -> None:
    out_dir = Path(
        os.environ.get(
            "SIMPLEPRACTICE_PROBE_OUTPUT_DIR",
            "/tmp/therapy-ops-agent/artifacts/selector_probe",
        )
    )
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(out_dir, 0o700)
    state_path = Path(
        os.environ.get(
            "SIMPLEPRACTICE_SESSION_STATE_PATH",
            "/tmp/therapy-ops-agent/browser/simplepractice_session.json",
        )
    )
    if not state_path.exists():
        raise FileNotFoundError(f"Session state not found at {state_path}. Run simplepractice_session first.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()

        targets = [
            "https://secure.simplepractice.com/calendar",
            "https://secure.simplepractice.com/clients",
        ]
        results = []
        for url in targets:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(2_000)
            snap = _page_snapshot(page)
            tag = "calendar" if "calendar" in url else "clients"
            screenshot_path = out_dir / f"sp_authenticated_{tag}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            os.chmod(screenshot_path, 0o600)
            results.append(snap)

        probe_path = out_dir / "sp_authenticated_probe.json"
        probe_path.write_text(
            json.dumps(results, indent=2),
            encoding="utf-8",
        )
        os.chmod(probe_path, 0o600)

        context.close()
        browser.close()

    print(f"Wrote {out_dir / 'sp_authenticated_probe.json'}")


if __name__ == "__main__":
    main()
