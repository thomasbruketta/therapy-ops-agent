"""Utilities for writing triage artifacts in JSON and Markdown."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def write_triage_outputs(
    *,
    artifacts_dir: str | Path,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
    report_date: date | None = None,
) -> tuple[Path, Path]:
    """Write JSON and Markdown triage output files for the provided date."""
    report_date = report_date or date.today()
    out_dir = Path(artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = report_date.isoformat()
    json_path = out_dir / f"triage_{slug}.json"
    md_path = out_dir / f"triage_{slug}.md"

    payload = {
        "date": slug,
        "summary": summary,
        "records": records,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        f"# Triage Report ({slug})",
        "",
        "## Summary",
        f"- Total appointments: {summary['total_appointments']}",
        f"- Attempted sends: {summary['attempted_sends']}",
        f"- Successful sends: {summary['successful_sends']}",
        f"- Skipped: {summary['skipped']['total']}",
        f"- Failed: {summary['failed']['total']}",
        "",
        "## Skipped Reasons",
    ]

    if summary["skipped"]["reasons"]:
        for reason, count in summary["skipped"]["reasons"].items():
            md_lines.append(f"- {reason}: {count}")
    else:
        md_lines.append("- none")

    md_lines.append("")
    md_lines.append("## Failed Reasons")
    if summary["failed"]["reasons"]:
        for reason, count in summary["failed"]["reasons"].items():
            md_lines.append(f"- {reason}: {count}")
    else:
        md_lines.append("- none")

    md_lines.extend(["", "## Records", ""])
    for record in records:
        client = record.get("client_name", "")
        status = record.get("status", "")
        reason = record.get("reason")
        reason_part = f" ({reason})" if reason else ""
        md_lines.append(f"- {client}: {status}{reason_part}")

    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path
