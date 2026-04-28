from __future__ import annotations

import json

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.references.venue_scoring import (
    get_venue_spec, build_review_schema,
)
from research_harness.utils import call_with_schema

from research_harness.stages.review._review_prose_codex import (
    generate_review_text,
)

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def _stage2_freeform_codex(*, venue_name: str, venue_criteria: str,
                           paper_content: str, review_text: dict,
                           schema: dict, model: str = "gpt-5.5",
                           timeout_s: int = 300) -> dict:
    """Fallback when call_with_schema's tool-use path fails (e.g. on
    CLI-based runtimes that ignore tool_choice). Asks codex CLI to
    write a JSON object containing only the structured fields the
    schema requires, then parses it.
    """
    if shutil.which("codex") is None:
        raise RuntimeError(
            "stage 2 fallback needs codex CLI but it's not on PATH"
        )

    # Tempdir under cwd so codex sandbox (nested via Claude Code Bash)
    # can write to it.
    import os as _os
    workdir = Path(tempfile.mkdtemp(prefix="review_stage2_",
                                    dir=_os.getcwd()))
    try:
        out_path = workdir / "structured.json"
        prompt = (
            f"You are a senior reviewer for {venue_name}. The free-text "
            f"portion of the review is already written (shown below). "
            f"Your task: write a single JSON object containing ONLY the "
            f"structured fields from the schema below — no free text, no "
            f"markdown fences, no commentary. Write the JSON object to "
            f"the file at {out_path}.\n\n"
            f"## Schema (JSON Schema)\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```\n\n"
            f"## Venue criteria\n{venue_criteria}\n\n"
            f"## Already-written free-text portion of the review\n"
            f"{_format_review_text_for_prompt(review_text)}\n\n"
            f"## Paper under review (for reference)\n{paper_content}\n\n"
            f"Now write the JSON object to {out_path}. Use {venue_name}'s "
            f"exact `sub_scores` dimension names (do not substitute names "
            f"from other venues). Do not write anything else."
        )
        # Strip NUL bytes — fork_exec rejects argv with embedded \x00.
        prompt = prompt.replace("\x00", "")
        cmd = [
            "codex", "exec",
            "--sandbox", "workspace-write",
            "--skip-git-repo-check",
            "--cd", str(workdir),
            "-c", 'model_reasoning_effort="medium"',
            "--model", model,
            prompt,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout_s)
        if r.returncode != 0:
            raise RuntimeError(
                f"stage2 codex exec failed (rc={r.returncode}): "
                f"{r.stderr[-400:] or r.stdout[-400:]}"
            )
        if not out_path.exists():
            raise RuntimeError(
                f"stage2 codex did not write {out_path}; "
                f"stderr: {r.stderr[-400:]}"
            )
        text = out_path.read_text().strip()
        # Strip ```json fences if codex added them despite the instruction.
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise RuntimeError(
                f"stage2 codex output had no JSON object; first 200: "
                f"{text[:200]!r}"
            )
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"stage2 codex JSON parse failed: {e}; first 200: "
                f"{text[:200]!r}"
            )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _format_review_text_for_prompt(review_text: dict) -> str:
    """Render the dynamic stage-1 dict (per-venue field names) for the
    stage-2 prompt — just dumps each field as a `## <field>` section.
    """
    out: list[str] = []
    for fname, content in review_text.items():
        if isinstance(content, list):
            body = "\n".join(f"- {c}" for c in content)
        else:
            body = str(content or "").strip()
        if body:
            out.append(f"## Already-written `{fname}`\n{body}")
    return "\n\n".join(out)


def _build_structured_instructions(*, venue_name: str, venue_criteria: str,
                                   paper_content: str,
                                   review_text: dict[str, object]) -> str:
    """Stage-2 prompt: numeric / enum / boolean fields only.

    All free-text fields (whatever the venue's form needs) have already
    been written by stage 1. We show them here so the score/verdict line
    up with the prose. Stage 2 must not regenerate them.
    """
    return (
        f"You are a senior reviewer for {venue_name}. The full free-text "
        f"portion of the review has already been written (shown below). "
        f"Your task now is to call the `submit_review` tool to produce ONLY "
        f"the numeric / enum / boolean fields the schema requires: `score`, "
        f"`verdict`, `sub_scores` (using {venue_name}'s exact dimension "
        f"names — do NOT substitute names from other venues), `confidence`, "
        f"`best_paper_candidate` (if applicable). The free-text fields will "
        f"be merged in automatically — do NOT regenerate them.\n\n"
        f"## Venue criteria\n{venue_criteria}\n\n"
        f"{_format_review_text_for_prompt(review_text)}\n\n"
        f"## Paper under review (for reference)\n{paper_content}\n\n"
        f"Now call `submit_review`. Use {venue_name}'s exact `sub_scores` "
        f"dimension names. Do NOT respond with free text — the tool call "
        f"IS your submission."
    )


@agentic_function(render_range={"depth": 0, "siblings": 0})
def review_paper(paper_content: str, venue: str, venue_criteria: str,
                 runtime: Runtime,
                 draft_judgment: dict | None = None) -> str:
    """Venue-aware reviewer (no grounding) using a two-stage pipeline.

    Stage 1: free-form codex CLI generates every free-text field of the
    target venue's review form, with each sentence constrained to a
    real-human sentence template (see review_corpus/LESSONS.md, v6).
    The set of fields depends on the venue (e.g. ACM MM has `review`
    and `fit_justification`; COLM uses `reasons_to_accept` instead of
    `strengths`).

    Stage 2: tool-use call_with_schema fills the structured numeric /
    enum / boolean fields (score, verdict, sub_scores, confidence,
    best_paper_candidate). Stage-1 free-text fields are excluded from
    the schema and merged in afterwards.

    Humanize mode (when draft_judgment is provided): stage 1 receives
    the prior reviewer's structured judgment + short bullets as content
    guidance (no LLM-prose from the draft enters the prompt — bullets
    are pre-truncated to ≤80 chars). Stage 2 is skipped: numerics from
    the draft are used as-is, so the user's score / verdict / sub_scores /
    confidence are preserved verbatim. Result: prose entirely re-written
    from corpus templates (0% AI on GPTZero, like vanilla paper-review),
    judgment preserved from the user's draft.

    Returns: JSON string with all venue-required fields.
    """
    spec = get_venue_spec(venue)

    # Stage 1: generate all free-text fields under v6 template constraint.
    # In humanize mode, the draft's structured judgment + short bullets
    # are passed in to guide which paper aspects each section covers
    # (without leaking any draft-prose tokens into the LLM context).
    review_text = generate_review_text(
        paper_content=paper_content,
        venue_name=spec.name,
        venue_criteria=venue_criteria,
        draft_judgment=draft_judgment,
    )

    # Stage 2: numerics. Two paths:
    #   (a) humanize mode — use the draft's numerics verbatim (preserves
    #       the user's judgment, avoids letting any LLM see the draft's
    #       prose to score a second time).
    #   (b) from-scratch mode — call the model to produce score / verdict
    #       / sub_scores / confidence. Tool-use first, codex CLI fallback.
    stage1_fields = tuple(review_text.keys())
    schema = build_review_schema(spec, exclude_fields=stage1_fields)
    if draft_judgment:
        result: dict = {}
        for k in ("score", "verdict", "confidence",
                  "best_paper_candidate"):
            if draft_judgment.get(k) is not None:
                result[k] = draft_judgment[k]
        sub = draft_judgment.get("sub_scores") or {}
        if sub:
            result["sub_scores"] = dict(sub)
    else:
        instructions = _build_structured_instructions(
            venue_name=spec.name,
            venue_criteria=venue_criteria,
            paper_content=paper_content,
            review_text=review_text,
        )
        try:
            result = call_with_schema(
                runtime=runtime,
                instructions=instructions,
                schema_name="submit_review",
                schema_description=(
                    f"Submit the structured numeric / enum / boolean "
                    f"fields for a {spec.name} review. The free-text "
                    f"fields are generated separately and merged in "
                    f"afterwards."
                ),
                parameters=schema,
            )
        except ValueError:
            # CLI-based runtimes (Claude Code, Gemini CLI) ignore
            # tool_choice and sometimes return text instead of a tool
            # call. Fall back to a free-form codex prompt that writes
            # the structured JSON to a file, then parse it.
            result = _stage2_freeform_codex(
                venue_name=spec.name,
                venue_criteria=venue_criteria,
                paper_content=paper_content,
                review_text=review_text,
                schema=schema,
            )

    # Merge stage-1 text fields back in (using whatever field names the
    # venue's form actually has).
    for fname, content in review_text.items():
        result[fname] = content
    result["venue"] = spec.name
    return json.dumps(result, ensure_ascii=False, indent=2)
