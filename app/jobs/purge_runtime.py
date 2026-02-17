"""Purge ephemeral runtime data from local disk."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _purge_contents(root: Path) -> int:
    removed = 0
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed


def main() -> None:
    root = Path(os.getenv("ACORN_RUNTIME_ROOT", "/runtime"))
    if root.exists():
        removed = _purge_contents(root)
        print(f"Purged {removed} item(s) under {root}")
    else:
        print(f"No runtime directory present at {root}")


if __name__ == "__main__":
    main()
