from __future__ import annotations

from pathlib import Path

from app.jobs import purge_runtime


def test_purge_contents_removes_files_and_dirs(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("x", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "two.txt").write_text("y", encoding="utf-8")

    removed = purge_runtime._purge_contents(tmp_path)
    assert removed == 2
    assert list(tmp_path.iterdir()) == []


def test_main_reports_missing_runtime(monkeypatch, tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("ACORN_RUNTIME_ROOT", str(missing))
    purge_runtime.main()
    out = capsys.readouterr().out
    assert "No runtime directory present" in out

