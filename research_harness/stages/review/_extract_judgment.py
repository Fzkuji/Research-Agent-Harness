"""Extract structured judgment from an existing review draft.

The 2-stage humanize pipeline:
  Stage A (this module): codex CLI reads the LLM-written draft and emits
    a strictly structured JSON {score, verdict, sub_scores, confidence,
    bullets-per-field}. Bullets are short fragments only — full LLM-prose
    sentences are explicitly forbidden in the prompt and any bullet that
    looks like prose gets truncated.
  Stage B (review_paper.py): the structured judgment feeds into stage 1
    of from-scratch review generation. The LLM never sees the draft's
    prose, only paper + numbers + short bullets, so the output prose
    carries no LLM signature from the draft.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def extract_judgment(draft_text: str, *,
                     model: str = "gpt-5.5",
                     reasoning_effort: str = "medium",
                     timeout_s: int = 180) -> dict:
    """Run codex CLI to compress a review draft into structured judgment.

    Returns:
      {
        "score": float | int | None,
        "verdict": str | None,
        "sub_scores": {str: float|int},
        "confidence": float | int | None,
        "bullets": {field_name: [str, ...]},  # short fragments only
      }

    Raises RuntimeError if codex fails or output cannot be parsed.
    """
    if shutil.which("codex") is None:
        raise RuntimeError(
            "extract_judgment needs codex CLI but it's not on PATH"
        )

    # Tempdir under cwd so codex sandbox (when called from a Bash tool
    # inside another agent like Claude Code) can write to it without
    # tripping workspace-write restrictions on /var/folders/.
    workdir = Path(tempfile.mkdtemp(prefix="extract_judgment_",
                                    dir=os.getcwd()))
    try:
        draft_path = workdir / "draft.md"
        draft_path.write_text(draft_text)
        out_path = workdir / "judgment.json"
        prompt = (
            "Read the review draft below and write a single JSON object "
            f"to the file at {out_path}. The JSON must contain only "
            "structured judgment, no prose. Schema:\n\n"
            "```json\n"
            "{\n"
            '  "score":      <number or null>,\n'
            '  "verdict":    <short label string or null, e.g. "Reject", "Accept", "Borderline">,\n'
            '  "sub_scores": {<dimension name>: <number>, ...},\n'
            '  "confidence": <number or null>,\n'
            '  "bullets": {\n'
            '    "<field name>": [<short fragment>, ...],\n'
            "    ...\n"
            "  }\n"
            "}\n"
            "```\n\n"
            "STRICT RULES for bullets — ANY VIOLATION makes the output "
            "useless:\n"
            "- Each bullet ≤ 60 characters. NOT a full sentence. A "
            "fragment / noun phrase / verb phrase that captures one "
            "observation.\n"
            "- Use plain ASCII. No quoted phrases from the draft, no "
            "transitions, no hedges, no first-person.\n"
            "- One observation per bullet. Split a draft sentence with "
            "multiple points into multiple bullets.\n"
            "- Examples of GOOD bullets: 'method section is empty', "
            "'no datasets or baselines', 'fit to multimedia weak', "
            "'duplicate \\end{document}'.\n"
            "- Examples of BAD bullets (too long / too prose-like): "
            "'The method section says that the proposed method is "
            "described, but no method is actually given.', 'I think the "
            "experiments are inadequate because there are no real "
            "results.'\n\n"
            "Field-name keys must come from the draft's section headers "
            "(`## Summary`, `## Strengths`, `## Weaknesses`, `## Review`, "
            "`## Fit Justification`, etc — lowercase + underscore them, "
            "e.g. 'summary', 'strengths', 'weaknesses', 'review', "
            "'fit_justification'). Numeric fields go at the top level, "
            "not under bullets.\n\n"
            f"Write only valid JSON to {out_path}. No commentary, no "
            "fences. The draft is below:\n\n---\n\n"
            f"{draft_text}\n"
        )
        # Strip NUL bytes — fork_exec rejects argv with embedded \x00,
        # which sometimes leaks in from upstream markdown sources.
        prompt = prompt.replace("\x00", "")
        cmd = [
            "codex", "exec",
            "--sandbox", "workspace-write",
            "--skip-git-repo-check",
            "--cd", str(workdir),
            "-c", f'model_reasoning_effort="{reasoning_effort}"',
            "--model", model,
            prompt,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout_s)
        if r.returncode != 0:
            raise RuntimeError(
                f"extract_judgment codex failed (rc={r.returncode}): "
                f"{r.stderr[-400:] or r.stdout[-400:]}"
            )
        if not out_path.exists():
            raise RuntimeError(
                f"extract_judgment codex did not write {out_path}; "
                f"stderr: {r.stderr[-400:]}"
            )
        text = out_path.read_text().strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise RuntimeError(
                f"extract_judgment output had no JSON object; first "
                f"200: {text[:200]!r}"
            )
        try:
            judgment = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"extract_judgment JSON parse failed: {e}; "
                f"first 200: {text[:200]!r}"
            )

        # Defensive: enforce bullet brevity in case the model ignored
        # the prompt rule. Truncate at 80 chars and drop full-stop
        # period to discourage prose-looking bullets.
        bullets = judgment.get("bullets") or {}
        cleaned: dict[str, list[str]] = {}
        for field, items in bullets.items():
            if not isinstance(items, list):
                continue
            kept: list[str] = []
            for it in items:
                if not isinstance(it, str):
                    continue
                it = it.strip()
                if not it:
                    continue
                # Drop trailing period to make it look fragment-like.
                it = it.rstrip(".").strip()
                if len(it) > 80:
                    it = it[:77] + "…"
                kept.append(it)
            if kept:
                cleaned[field] = kept
        judgment["bullets"] = cleaned
        return judgment
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
