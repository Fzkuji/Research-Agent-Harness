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
import tempfile
from pathlib import Path

from research_harness.stages.review._codex_run import run_codex


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
            "RULES for bullets — one bullet per point, key-phrase form:\n"
            "- HARD CAPS on bullet counts per field:\n"
            "  * strengths: AT MOST 6 bullets\n"
            "  * weaknesses: AT MOST 8 bullets\n"
            "  * summary: AT MOST 8 bullets\n"
            "  * review: AT MOST 12 bullets\n"
            "  * fit_justification: AT MOST 5 bullets\n"
            "  If the draft has more, you MUST drop the weakest ones "
            "and merge near-duplicates. Do NOT 1:1 transcribe. "
            "Aggressive culling is the point of this stage.\n"
            "- Drop a bullet if ANY of these apply: it is a platitude "
            "that could be pasted into a review of any other paper in "
            "the venue ('the motivation is good', 'experiments are "
            "solid', 'writing is clear', 'more experiments would "
            "help'); it states only a label without saying what or "
            "why ('important problem' without naming what makes it "
            "important; 'limited analysis' without naming what is "
            "missing); it is a near-duplicate of another bullet.\n"
            "- Keep a bullet only if a reader can tell from it what "
            "specifically the paper did or failed to do — name the "
            "problem, the component, the dataset, the baseline, the "
            "design choice, the missing experiment, etc. Eq./Table/"
            "Figure refs are nice but not required; what matters is "
            "specific content, not specific citation format.\n"
            "- Sort the remaining bullets by importance, strongest "
            "first. The downstream prose generator will keep the "
            "1-to-1 mapping you give it, so what you keep IS the final "
            "review's bullet count.\n"
            "- One bullet per OBSERVATION / POINT. Not per sentence. If "
            "the draft has a category subsection with three sentences "
            "elaborating one point, that is ONE bullet. Multi-sentence "
            "elaboration of the same observation collapses into one "
            "compressed phrase.\n"
            "- The bullet itself is a key-phrase compression, not a "
            "rewritten sentence. Strip articles, transitions, hedges, "
            "first-person. Keep specific tokens (numbers, table/figure/"
            "equation refs, model names, dataset names, hyperparameter "
            "names) — those are the load-bearing content. Phase 3 "
            "expands each compressed bullet back into a sentence using "
            "real-human sentence templates; your job is to give it a "
            "tight, unambiguous skeleton, not a finished sentence.\n"
            "- Merge near-duplicate observations from the draft into "
            "ONE bullet, even if they appeared in different sentences "
            "or different category subsections. The downstream prose "
            "generator should not see two near-duplicate bullets.\n"
            "- Skip pure filler with no specific content "
            "(e.g. 'overall the paper is interesting', 'this is a good "
            "submission', 'the strengths are as follows: Strength 1...').\n"
            "- Do NOT invent tokens not in the draft.\n"
            "- Use plain ASCII. No quoted phrases from the draft.\n\n"
            "Compression examples:\n"
            "  source paragraph: 'Table 5 reports a -7.2% drop in metric "
            "A when module X is removed, but Section 6.1 reports only "
            "+3.1% from module X over the baseline; the authors say the "
            "two have different starting points, but as written the "
            "section is unclear and the two numbers read as "
            "inconsistent.'\n"
            "  → ONE bullet: 'Table 5 -7.2% w/o X vs Sec 6.1 +3.1% over "
            "baseline; different-starting-point explanation unclear, "
            "numbers inconsistent'.\n\n"
            "  source category subsection (Experimental rigor) with 3 "
            "sentences praising 'multi-model coverage', 'multi-dataset', "
            "'ablation design':\n"
            "  → ONE bullet: 'multi-model + multi-dataset + ablation '"
            "design'.\n\n"
            "  source two near-duplicate strengths: 'The paper targets "
            "an important topic of unsupervised multimodal intent "
            "discovery.' AND 'This paper tackles a timely and "
            "interesting topic, and contains several insights and "
            "useful contributions.':\n"
            "  → ONE bullet: 'timely / important problem '"
            "(unsupervised multimodal intent discovery)'.\n\n"
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
        r = run_codex(cmd, timeout_s=timeout_s)
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

        # Light cleanup only — no length truncation. The prompt is the
        # only mechanism enforcing compression; defensive truncation
        # would silently drop content the model deliberately preserved.
        bullets = judgment.get("bullets") or {}
        cleaned: dict[str, list[str]] = {}
        for field, items in bullets.items():
            if not isinstance(items, list):
                continue
            kept: list[str] = []
            for it in items:
                if not isinstance(it, str):
                    continue
                it = it.strip().rstrip(".").strip()
                if not it:
                    continue
                kept.append(it)
            if kept:
                cleaned[field] = kept
        judgment["bullets"] = cleaned
        return judgment
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
