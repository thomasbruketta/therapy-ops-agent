from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable, TypeVar
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


@dataclass
class SendResult:
    success: bool
    context: dict[str, Any]


T = TypeVar("T")


class AcornAdapterUI:
    """UI adapter for Acorn interactions via Playwright."""

    def __init__(
        self,
        page: Page,
        screenshots_dir: Path | str = "/tmp/therapy-ops-agent/artifacts/screenshots",
        login_url: str | None = None,
        mobile_form_url: str | None = None,
    ) -> None:
        self.page = page
        self.screenshots_dir = Path(screenshots_dir) / "acorn"
        self.login_url = login_url or os.getenv("ACORN_LOGIN_URL", "https://www.cci-acorn.org/login.asp")
        self.mobile_form_url = mobile_form_url or os.getenv(
            "ACORN_MOBILE_FORM_URL",
            "https://www.cci-acorn.org/mobileforminit.asp",
        )

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

    def login(self, username: str, password: str) -> None:
        def _login() -> None:
            self.page.goto(self.login_url, wait_until="domcontentloaded")
            self.page.locator("#uid").fill(username, timeout=10_000)
            self.page.locator("#pwd").fill(password, timeout=10_000)
            self.page.locator("#submit1").click(timeout=10_000)
            self.page.wait_for_url("**/index.asp", timeout=20_000)

        self._retry_transient("login", _login)

    def open_mobile_forms(self) -> None:
        def _open() -> None:
            self.page.goto(self.mobile_form_url, wait_until="domcontentloaded")
            self.page.locator("#mform").wait_for(timeout=12_000)

        self._retry_transient("open_mobile_forms", _open)

    def send_mobile_form(
        self,
        *,
        clinician_id: str,
        form_value: str,
        client_id: str,
        phone: str,
        message: str,
        send_via: str = "text",
        start_session: int = 0,
        text_from: str = "ACORN",
    ) -> SendResult:
        def _send() -> SendResult:
            self.open_mobile_forms()

            self.page.locator("#cid").select_option(clinician_id)
            self.page.locator("#mform").select_option(form_value)
            self.page.locator("#client").fill(client_id)
            self.page.locator("input[name='startsess']").fill(str(start_session))
            self.page.locator("#sendvia").select_option(send_via)
            self.page.locator("#submit0").click(timeout=10_000)

            self.page.locator("#textphone").wait_for(timeout=12_000)
            self.page.locator("#textphone").fill(phone)
            self.page.locator("#from").fill(text_from)
            self.page.locator("#emailmsg").fill(message)
            self.page.locator("#submit0").click(timeout=10_000)
            self.page.wait_for_timeout(2_000)

            body_text = self.page.locator("body").inner_text(timeout=10_000)
            success = ("Sending Text to" in body_text) and (phone in body_text)

            return SendResult(
                success=success,
                context={
                    "clinician_id": clinician_id,
                    "form_value": form_value,
                    "client_id": client_id,
                    "phone": phone,
                    "send_via": send_via,
                    "body_snippet": body_text[:800],
                },
            )

        return self._retry_transient("send_mobile_form", _send)

    def verify_send_success(self, send_result_context: dict[str, Any]) -> bool:
        def _verify() -> bool:
            body = self.page.locator("body").inner_text(timeout=8_000)
            phone = str(send_result_context.get("phone", ""))
            return ("Sending Text to" in body) and (phone in body)

        return self._retry_transient("verify_send_success", _verify)
