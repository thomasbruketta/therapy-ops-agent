from __future__ import annotations

import tempfile
from pathlib import Path

from app.utils.runtime_paths import runtime_path, runtime_root


def test_runtime_root_uses_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ACORN_RUNTIME_ROOT", "/custom/runtime/root")
    assert runtime_root() == Path("/custom/runtime/root")


def test_runtime_root_defaults_to_system_temp(monkeypatch) -> None:
    monkeypatch.delenv("ACORN_RUNTIME_ROOT", raising=False)
    assert runtime_root() == Path(tempfile.gettempdir()) / "therapy-ops-agent"


def test_runtime_path_joins_parts(monkeypatch) -> None:
    monkeypatch.setenv("ACORN_RUNTIME_ROOT", "/custom/runtime/root")
    assert runtime_path("state", "idempotency.json") == Path("/custom/runtime/root/state/idempotency.json")

