from __future__ import annotations

import os
from pathlib import Path
import tempfile


def runtime_root() -> Path:
    configured = os.getenv("ACORN_RUNTIME_ROOT", "").strip()
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "therapy-ops-agent"


def runtime_path(*parts: str) -> Path:
    return runtime_root().joinpath(*parts)

