"""File loading, scanning, and report scaffolding shared by writing_lint.

Original code (this repository; the directory as a whole is distributed
under CC BY-NC 4.0 — see LICENSE).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

__all__ = ["load_source", "run_scan"]


def load_source(path_or_text: str) -> str:
    """Return file contents when the argument is an existing path; otherwise
    treat the argument itself as LaTeX text."""
    if "\n" not in path_or_text and len(path_or_text) < 4096:
        try:
            p = Path(os.path.expanduser(path_or_text))
            if p.is_file():
                return p.read_text(encoding="utf-8")
        except (OSError, ValueError):
            pass
    return path_or_text


def run_scan(paper_dir: str, checker: Callable[[str], list[dict]],
             report_name: str, title: str, label: str) -> str:
    """Run `checker` over every .tex under `paper_dir` (or a single .tex
    file), write a markdown report next to the sources, and return a
    one-line summary string."""
    root = Path(os.path.abspath(os.path.expanduser(paper_dir)))
    if root.is_file() and root.suffix == ".tex":
        report_dir, files = root.parent, [root]
    elif root.is_dir():
        report_dir, files = root, sorted(root.rglob("*.tex"))
    else:
        return f"ERROR: no such .tex file or directory: {paper_dir}"
    if not files:
        return f"ERROR: no .tex files found under {paper_dir}"

    findings_by_file = {f: checker(f.read_text(encoding="utf-8"))
                        for f in files}
    total = sum(len(v) for v in findings_by_file.values())
    report_path = report_dir / report_name
    _write_report(report_path, title, root, findings_by_file)

    flagged = [f"{p.name} ({len(v)})"
               for p, v in sorted(findings_by_file.items()) if v]
    parts = [f"Scanned {len(files)} .tex file(s): {total} {label}."]
    if flagged:
        parts.append("Files with findings: " + ", ".join(flagged) + ".")
    parts.append(f"Report saved to {report_path}.")
    return " ".join(parts)


def _write_report(report_path: Path, title: str, source: Path,
                  findings_by_file: dict[Path, list[dict]]) -> None:
    base = source if source.is_dir() else source.parent
    total = sum(len(v) for v in findings_by_file.values())
    lines = [
        f"# {title}",
        "",
        f"Source: `{source}`  ",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"**{total} finding(s) across {len(findings_by_file)} .tex file(s).**",
        "",
    ]
    for path in sorted(findings_by_file):
        findings = findings_by_file[path]
        if not findings:
            continue
        try:
            rel = path.relative_to(base)
        except ValueError:
            rel = path
        lines.append(f"## {rel}")
        lines.append("")
        for f in findings:
            lines.append(f"- line {f['line']}: {f['reason']}")
            lines.append(f"  > {f['sentence']}")
        lines.append("")
    if total == 0:
        lines.append("No findings.")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
