from __future__ import annotations

from pathlib import Path

from app.jobs import simplepractice_auth_check


class _FakeContext:
    def new_page(self):
        return object()

    def close(self) -> None:
        return None


class _FakeBrowser:
    def __init__(self, capture: dict[str, str]) -> None:
        self.capture = capture

    def new_context(self, **kwargs):
        self.capture.update({k: str(v) for k, v in kwargs.items()})
        return _FakeContext()

    def close(self) -> None:
        return None


class _FakePlaywrightCM:
    def __init__(self, capture: dict[str, str]) -> None:
        self.capture = capture

    def __enter__(self):
        class _FakePlaywright:
            def __init__(self, capture: dict[str, str]) -> None:
                self.chromium = type("_Chromium", (), {"launch": lambda _, headless: _FakeBrowser(capture)})()

        return _FakePlaywright(self.capture)

    def __exit__(self, exc_type, exc, tb):
        return False


class _AdapterAuthenticated:
    def __init__(self, page, session_state_path):
        self.page = page
        self.session_state_path = session_state_path

    def has_authenticated_session(self) -> bool:
        return True


class _AdapterExpired(_AdapterAuthenticated):
    def has_authenticated_session(self) -> bool:
        return False


def test_auth_check_returns_mfa_required_when_state_missing(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "missing_session.json"
    monkeypatch.setenv("SIMPLEPRACTICE_SESSION_STATE_PATH", str(state_path))

    exit_code, payload = simplepractice_auth_check.run_auth_check()

    assert exit_code == 2
    assert payload["status"] == "MFA_REQUIRED"
    assert "not found" in payload["message"]


def test_auth_check_returns_authenticated_when_session_valid(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "session.json"
    state_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SIMPLEPRACTICE_SESSION_STATE_PATH", str(state_path))

    capture: dict[str, str] = {}
    monkeypatch.setattr(simplepractice_auth_check, "sync_playwright", lambda: _FakePlaywrightCM(capture))
    monkeypatch.setattr(simplepractice_auth_check, "SimplePracticeAdapterUI", _AdapterAuthenticated)

    exit_code, payload = simplepractice_auth_check.run_auth_check(headless=True)

    assert exit_code == 0
    assert payload["status"] == "AUTHENTICATED"
    assert capture["storage_state"] == str(state_path)


def test_auth_check_returns_mfa_required_when_session_expired(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "session.json"
    state_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SIMPLEPRACTICE_SESSION_STATE_PATH", str(state_path))

    monkeypatch.setattr(simplepractice_auth_check, "sync_playwright", lambda: _FakePlaywrightCM({}))
    monkeypatch.setattr(simplepractice_auth_check, "SimplePracticeAdapterUI", _AdapterExpired)

    exit_code, payload = simplepractice_auth_check.run_auth_check(headless=True)

    assert exit_code == 2
    assert payload["status"] == "MFA_REQUIRED"
    assert "not authenticated" in payload["message"]
