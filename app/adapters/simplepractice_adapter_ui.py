from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import os
from pathlib import Path
from typing import Any, Callable, TypeVar
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


@dataclass
class Appointment:
    client_ref: str
    starts_at: str
    ends_at: str
    status: str


@dataclass
class ClientDetails:
    client_ref: str
    full_name: str
    phone: str | None = None
    email: str | None = None


T = TypeVar("T")


class SimplePracticeAdapterUI:
    """UI adapter for SimplePractice interactions via Playwright."""

    def __init__(
        self,
        page: Page,
        screenshots_dir: Path | str = "/tmp/therapy-ops-agent/artifacts/screenshots",
        base_url: str | None = None,
        session_state_path: str | Path | None = None,
    ) -> None:
        self.page = page
        self.screenshots_dir = Path(screenshots_dir) / "simplepractice"
        self.base_url = (base_url or os.getenv("SIMPLEPRACTICE_BASE_URL", "https://account.simplepractice.com/")).rstrip("/")
        self.session_state_path = Path(
            session_state_path
            or os.getenv("SIMPLEPRACTICE_SESSION_STATE_PATH", "/tmp/therapy-ops-agent/browser/simplepractice_session.json")
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

    def login(
        self,
        *,
        username: str,
        password: str,
        mfa_code: str | None = None,
        remember_device: bool = True,
    ) -> None:
        def _login() -> None:
            self.page.goto(f"{self.base_url}/", wait_until="domcontentloaded")
            if self.page.locator("#cookie-consent-accept").count():
                self.page.locator("#cookie-consent-accept").click(timeout=3_000)

            self.page.locator("#user_email").fill(username, timeout=10_000)
            self.page.locator("#user_password").fill(password, timeout=10_000)
            self.page.locator("#submitBtn").click(timeout=10_000)
            self.page.wait_for_timeout(2_000)

            if "multi_factor/challenge_responses/new_request" in self.page.url:
                if not mfa_code:
                    raise RuntimeError("SimplePractice MFA required. Provide mfa_code to continue.")
                if remember_device and self.page.locator("#remember_me").count():
                    self.page.locator("#remember_me").check(timeout=3_000)
                self.page.locator("#code_single").fill(mfa_code, timeout=10_000)
                self.page.locator("input[name='commit'][type='submit']").click(timeout=10_000)
                self.page.wait_for_timeout(2_000)

        self._retry_transient("login", _login)

    def save_session_state(self) -> Path:
        self.session_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.page.context.storage_state(path=str(self.session_state_path))
        return self.session_state_path

    def has_authenticated_session(self) -> bool:
        # Secure area redirects to account sign-in when session is invalid.
        self.page.goto("https://secure.simplepractice.com/calendar", wait_until="domcontentloaded")
        self.page.wait_for_timeout(1_000)
        return "account.simplepractice.com" not in self.page.url

    def ensure_authenticated(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        mfa_code: str | None = None,
    ) -> bool:
        """Ensure the current page context is authenticated for secure.simplepractice.com."""
        if self.has_authenticated_session():
            return True
        if not username or not password:
            return False
        self.login(username=username, password=password, mfa_code=mfa_code, remember_device=True)
        return self.has_authenticated_session()

    def _frontend_get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = urlencode(params, doseq=True)
        url = f"https://secure.simplepractice.com{path}?{query}"
        response = self.page.context.request.get(url)
        if response.status >= 400:
            raise RuntimeError(f"SimplePractice frontend request failed ({response.status}) for {path}")
        return response.json()

    @staticmethod
    def _time_range_for_date(target_date: date, tz_name: str = "America/Los_Angeles") -> tuple[str, str]:
        tz = ZoneInfo(tz_name)
        start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=tz)
        end = start + timedelta(days=1)
        return start.isoformat(), end.isoformat()

    def fetch_daily_recipients(
        self,
        *,
        target_date: date,
        clinician_id: str,
        timezone_name: str = "America/Los_Angeles",
        max_clients: int = 200,
    ) -> list[dict[str, str]]:
        """Fetch unique {full_name, phone} recipients for a clinician's day schedule."""
        start_iso, end_iso = self._time_range_for_date(target_date, timezone_name)

        appointments_payload = self._frontend_get(
            "/frontend/appointments",
            params={
                "fields[appointments]": "client,title,startTime,endTime,thisType,clinicianId,attendanceStatus",
                "filter[timeRange]": f"{start_iso},{end_iso}",
                "filter[clinicianId]": clinician_id,
            },
        )
        client_ids: set[str] = set()
        for item in appointments_payload.get("data", []):
            if item.get("type") != "appointments":
                continue
            relationships = item.get("relationships", {})
            rel_client = (relationships.get("client") or {}).get("data")
            if not rel_client:
                continue
            rel_type = str(rel_client.get("type", ""))
            if rel_type not in {"clients", "clientCouples"}:
                continue
            rel_id = str(rel_client.get("id", "")).strip()
            if rel_id:
                client_ids.add(rel_id)

        if not client_ids:
            return []

        recipients: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        # SimplePractice enforces max page size 50 for base-clients.
        page_size = min(max_clients, 50)
        page_num = 1
        while True:
            clients_payload = self._frontend_get(
                "/frontend/base-clients",
                params={
                    "fields[clients]": "name,firstName,lastName,defaultPhoneNumber,status,clinician",
                    "fields[clientCouples]": "name,firstName,lastName,defaultPhoneNumber,status,clinician",
                    "filter[composite]": "active",
                    "page[number]": str(page_num),
                    "page[size]": str(page_size),
                    "sort": "lastName",
                },
            )

            data = clients_payload.get("data", [])
            if not data:
                break

            for client in data:
                client_id = str(client.get("id", ""))
                if client_id not in client_ids:
                    continue
                attrs = client.get("attributes", {})
                full_name = str(attrs.get("name", "")).strip()
                phone = str(attrs.get("defaultPhoneNumber", "")).strip()
                if not full_name or not phone:
                    continue
                key = (full_name, phone)
                if key in seen:
                    continue
                seen.add(key)
                recipients.append({"full_name": full_name, "phone": phone})

            if len(recipients) >= len(client_ids):
                break
            if len(data) < page_size:
                break
            page_num += 1
        return recipients

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
