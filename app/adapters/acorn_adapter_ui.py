from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


@dataclass(slots=True)
class SendResult:
    success: bool
    context: dict[str, Any]


T = TypeVar("T")


class AcornAdapterUI:
    """UI adapter for Acorn interactions via Playwright."""

    def __init__(self, page: Page, screenshots_dir: Path | str = "artifacts/screenshots") -> None:
        self.page = page
        self.screenshots_dir = Path(screenshots_dir) / "acorn"

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
            self.page.goto("https://app.acorn.com/login", wait_until="domcontentloaded")
            self.page.locator("input[name='email']").fill(email, timeout=10_000)
            self.page.locator("input[name='password']").fill(password, timeout=10_000)
            self.page.locator("button[type='submit']").click(timeout=10_000)
            self.page.locator("[data-testid='dashboard'], .dashboard").first.wait_for(timeout=15_000)

        self._retry_transient("login", _login)

    def open_mobile_forms(self) -> None:
        def _open() -> None:
            self.page.locator("a[href*='mobile-forms'], [data-testid='mobile-forms-nav']").first.click(timeout=10_000)
            self.page.locator("[data-testid='mobile-forms-page'], .mobile-forms-page").first.wait_for(timeout=12_000)

        self._retry_transient("open_mobile_forms", _open)

    def send_mobile_form(self, form_type: str, client_id: str, phone: str, message: str) -> SendResult:
        def _send() -> SendResult:
            self.page.locator("[data-testid='new-mobile-form'], button:has-text('New Form')").first.click(timeout=10_000)
            self.page.locator("select[name='formType'], [data-testid='form-type']").first.select_option(value=form_type)
            self.page.locator("input[name='clientId'], [data-testid='client-id']").first.fill(client_id)
            self.page.locator("input[name='phone'], [data-testid='phone']").first.fill(phone)
            self.page.locator("textarea[name='message'], [data-testid='message']").first.fill(message)
            self.page.locator("button[type='submit'], [data-testid='send-mobile-form']").first.click(timeout=10_000)
            confirmation = self.page.locator("[data-testid='send-success'], .send-success").first
            confirmation.wait_for(timeout=12_000)

            return SendResult(
                success=True,
                context={
                    "form_type": form_type,
                    "client_id": client_id,
                    "phone": phone,
                    "confirmation_text": (confirmation.text_content() or "").strip(),
                },
            )

        return self._retry_transient("send_mobile_form", _send)

    def verify_send_success(self, send_result_context: dict[str, Any]) -> bool:
        def _verify() -> bool:
            confirmation = self.page.locator("[data-testid='send-success'], .send-success").first
            confirmation.wait_for(timeout=8_000)
            text = (confirmation.text_content() or "").lower()
            client_id = str(send_result_context.get("client_id", "")).lower()
            phone = str(send_result_context.get("phone", "")).lower()
            return ("sent" in text) and ((client_id in text) or (phone in text) or (not client_id and not phone))

        return self._retry_transient("verify_send_success", _verify)
