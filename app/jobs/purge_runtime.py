"""Purge ephemeral runtime data from local disk."""

from __future__ import annotations

import shutil
from pathlib import Path


def main() -> None:
    root = Path("/tmp/therapy-ops-agent")
    if root.exists():
        shutil.rmtree(root)
        print(f"Purged {root}")
    else:
        print(f"No runtime directory present at {root}")


if __name__ == "__main__":
    main()
