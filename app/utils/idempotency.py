from __future__ import annotations

import json
from pathlib import Path


DEFAULT_STORE_PATH = Path("/tmp/therapy-ops-agent/state/acorn_idempotency_store.json")


def build_idempotency_key(date: str, client_id: str) -> str:
    return f"acorn:{date}:{client_id}:v14"


class IdempotencyStore:
    def __init__(self, path: Path | str = DEFAULT_STORE_PATH) -> None:
        self.path = Path(path)

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return set()
        if not isinstance(payload, list):
            return set()
        return {item for item in payload if isinstance(item, str)}

    def _save(self, keys: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sorted(keys), indent=2),
            encoding="utf-8",
        )

    def has_been_sent(self, key: str) -> bool:
        return key in self._load()

    def mark_sent(self, key: str) -> None:
        keys = self._load()
        keys.add(key)
        self._save(keys)
