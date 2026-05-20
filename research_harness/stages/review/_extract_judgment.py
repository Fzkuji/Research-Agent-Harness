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
                     timeout_s: int = 180,
                     runtime=None) -> dict:
    """Compress a review draft into structured judgment.

    Two backends: pass ``runtime=`` to use the OpenAICodexRuntime API
    (recommended); leave None to fall back to the legacy codex CLI
    subprocess.

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
    # Drop lone surrogates anywhere upstream let in.
    draft_text = re.sub(r"[\ud800-\udfff]", "", draft_text)

    # Tempdir only needed for CLI sandbox path.
    workdir = Path(tempfile.mkdtemp(prefix="extract_judgment_",
                                    dir=os.getcwd()))
    try:
        out_path = workdir / "judgment.json"
        if runtime is None:
            (workdir / "draft.md").write_text(draft_text)
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
            "RULES for bullets — English telegraph-style S+V+O skeleton:\n"
            "- HARD CAPS:\n"
            "  * strengths: AT MOST 6 bullets\n"
            "  * weaknesses: AT MOST 8 bullets\n"
            "  * summary: AT MOST 8 bullets\n"
            "  * review: AT MOST 12 bullets\n"
            "  * fit_justification: AT MOST 5 bullets\n"
            "  If the draft has more, drop the weakest and merge "
            "near-duplicates.\n"
            "\n"
            "- Each bullet is a compressed grammatical skeleton with "
            "ALL specific tokens preserved: the subject (what/which "
            "component/section/table the bullet is about), the verb "
            "(what action or state: 'drops', 'lacks', 'reports', "
            "'inconsistent with', 'unjustified', 'missing'), the "
            "object (what is affected or compared), and the key "
            "modifiers (numbers, equation/table/figure/section refs, "
            "baseline names, dataset names, hyperparameter names, "
            "exact percentages, conditions). Strip articles ('the', "
            "'a'), most prepositions, transitions, hedges, "
            "first-person, and stop words. Use slashes and '+' to "
            "join. Phase 3 will inflate this skeleton back into a "
            "real reviewer sentence using its own style — your job "
            "is to deliver the SVO + specifics so Phase 3 has all "
            "the load-bearing content to build the sentence around.\n"
            "\n"
            "- A skeleton has enough detail when a human reading it "
            "can tell exactly what the bullet will say in the final "
            "review. Bad: 'experiments lack detail' (no subject, no "
            "object, no specifics). Good: 'Table 4 hyperparameter "
            "grid range / τ + γ1 + γ2 + λ choice criterion missing' "
            "(subject = Table 4 grid + criterion; verb = missing; "
            "object = criterion for τ,γ1,γ2,λ).\n"
            "\n"
            "- DROP a point entirely if you cannot extract a "
            "specific subject + verb + object + at least one "
            "concrete modifier from the draft for it. Do NOT pad "
            "with phantom specifics that the draft didn't carry. "
            "Empty skeletons are worse than fewer bullets.\n"
            "\n"
            "- Sort by importance, strongest first. The downstream "
            "prose generator keeps your 1-to-1 mapping; what you "
            "keep IS the final review.\n"
            "- One bullet per OBSERVATION / POINT. Multi-sentence "
            "elaboration of one observation collapses into ONE "
            "skeleton.\n"
            "- Merge near-duplicate observations into ONE skeleton.\n"
            "- Do NOT invent tokens not in the draft.\n"
            "- Plain ASCII; no curly quotes; no em dashes.\n"
            "\n"
            "Compression examples (telegraph form, SVO + specifics, "
            "no fluff):\n"
            "  draft sentence: 'Table 5 reports a -7.2% drop in "
            "metric A when module X is removed, but Section 6.1 "
            "reports only +3.1% from X over the baseline; the "
            "explanation that the two have different starting points "
            "is unclear, and the numbers read as inconsistent.'\n"
            "  → skeleton: 'Table 5 -7.2% w/o X (metric A) vs Sec "
            "6.1 +3.1% over baseline / different-starting-point "
            "explanation unclear / numbers inconsistent'.\n"
            "\n"
            "  draft: 'On three datasets Yelp, Amazon-book, and "
            "Steam, MCLLMRec outperforms ONCE, LLM4IDRec, HFAR, "
            "SCRec, UIST, and AutoGraph for Recall@N and NDCG@N, "
            "with improvements of 2.48% to 10.54% across "
            "backbones.'\n"
            "  → skeleton: 'MCLLMRec beats ONCE+LLM4IDRec+HFAR+"
            "SCRec+UIST+AutoGraph on Yelp+Amazon-book+Steam / R@N + "
            "N@N / 2.48-10.54% improvement / multiple backbones'.\n"
            "\n"
            "  draft: 'No hyperparameter selection procedure is "
            "given for τ, γ1, γ2, λ; Table 4 only reports a grid "
            "but not how the chosen values were picked.'\n"
            "  → skeleton: 'τ + γ1 + γ2 + λ selection procedure "
            "missing / Table 4 grid given but no choice criterion'.\n"
            "\n"
            "  draft: 'Eq. (29) and Algorithm 1 use inconsistent "
            "notation for the loss term; L_rec appears in one but "
            "L_MCS in the other without explanation.'\n"
            "  → skeleton: 'Eq. (29) vs Algorithm 1 loss notation "
            "inconsistent / L_rec vs L_MCS unexplained'.\n"
            "\n"
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

        if runtime is not None:
            prompt_for_api = prompt
            for marker in (f"`{out_path}`", str(out_path)):
                prompt_for_api = prompt_for_api.replace(
                    marker, "your response"
                )
            prompt_for_api += (
                "\n\nIMPORTANT: output ONLY the JSON object as your "
                "response — no markdown fences, no preamble, no other "
                "text. Do NOT attempt to write any file."
            )
            try:
                resp = runtime.exec(
                    content=[{"type": "text", "text": prompt_for_api}]
                )
            except Exception as e:
                raise RuntimeError(f"extract_judgment runtime.exec failed: {e}")
            text = (str(resp) if resp is not None else "").strip()
            if text.startswith("```"):
                text = re.sub(r"^```[a-zA-Z]*\n", "", text, count=1)
                text = re.sub(r"\n```\s*$", "", text, count=1)
        else:
            if shutil.which("codex") is None:
                raise RuntimeError(
                    "extract_judgment needs codex CLI on PATH or a "
                    "runtime= argument"
                )
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
