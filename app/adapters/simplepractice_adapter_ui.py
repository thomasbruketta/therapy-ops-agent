from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, TypeVar
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


@dataclass(slots=True)
class Appointment:
    client_ref: str
    starts_at: str
    ends_at: str
    status: str


@dataclass(slots=True)
class ClientDetails:
    client_ref: str
    full_name: str
    phone: str | None = None
    email: str | None = None


T = TypeVar("T")


class SimplePracticeAdapterUI:
    """UI adapter for SimplePractice interactions via Playwright."""

    def __init__(self, page: Page, screenshots_dir: Path | str = "artifacts/screenshots") -> None:
        self.page = page
        self.screenshots_dir = Path(screenshots_dir) / "simplepractice"

    def _capture_failure_screenshot(self, action: str) -> Path:
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshots_dir / f"{int(time.time() * 1000)}_{action}.png"
        self.page.screenshot(path=str(path), full_page=True)
        return path

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        if isinstance(exc, PlaywrightTimeoutError):
            return True
        if isinstance(exc, PlaywrightError):
            message = str(exc).lower()
            return "selector" in message or "timeout" in message
        return False

    def _retry_transient(self, action: str, fn: Callable[[], T], attempts: int = 3, delay_s: float = 0.6) -> T:
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as exc:
                if not self._is_transient(exc):
                    self._capture_failure_screenshot(f"{action}_fatal")
                    raise
                last_exc = exc
                if attempt == attempts:
                    self._capture_failure_screenshot(f"{action}_retries_exhausted")
                    raise
                time.sleep(delay_s)
        raise RuntimeError(f"Unreachable retry state for action={action}") from last_exc

    def login(self, email: str, password: str) -> None:
        def _login() -> None:
            self.page.goto("https://www.simplepractice.com/signin", wait_until="domcontentloaded")
            self.page.locator("input[name='email']").fill(email, timeout=10_000)
            self.page.locator("input[name='password']").fill(password, timeout=10_000)
            self.page.locator("button[type='submit']").click(timeout=10_000)
            self.page.locator("[data-testid='calendar-view'], .calendar-view").first.wait_for(timeout=15_000)

        self._retry_transient("login", _login)

    def get_today_appointments(self, date: date) -> list[Appointment]:
        def _load_rows() -> list[Appointment]:
            self.page.goto(f"https://www.simplepractice.com/calendar?date={date.isoformat()}", wait_until="domcontentloaded")
            self.page.locator("[data-testid='appointment-row'], .appointment-row").first.wait_for(timeout=12_000)
            rows = self.page.locator("[data-testid='appointment-row'], .appointment-row")
            items: list[Appointment] = []
            for i in range(rows.count()):
                row = rows.nth(i)
                items.append(
                    Appointment(
                        client_ref=row.get_attribute("data-client-ref") or "",
                        starts_at=row.get_attribute("data-start") or "",
                        ends_at=row.get_attribute("data-end") or "",
                        status=row.get_attribute("data-status") or "",
                    )
                )
            return items

        return self._retry_transient("get_today_appointments", _load_rows)

    def get_client_details(self, client_ref: str) -> ClientDetails:
        def _open_client() -> ClientDetails:
            self.page.goto(f"https://www.simplepractice.com/clients/{client_ref}", wait_until="domcontentloaded")
            self.page.locator("[data-testid='client-profile'], .client-profile").first.wait_for(timeout=12_000)

            full_name = (
                self.page.locator("[data-testid='client-name'], .client-name").first.text_content()
                or ""
            ).strip()
            phone = self.page.locator("[data-testid='client-phone'], .client-phone").first.text_content()
            email = self.page.locator("[data-testid='client-email'], .client-email").first.text_content()

            return ClientDetails(
                client_ref=client_ref,
                full_name=full_name,
                phone=(phone or "").strip() or None,
                email=(email or "").strip() or None,
            )

        return self._retry_transient("get_client_details", _open_client)
