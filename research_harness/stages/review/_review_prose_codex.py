"""Free-form codex CLI driver for the v6 review-text stage.

This stage produces ALL free-text fields of a reviewer assessment in
one shot: the long REVIEW prose, the STRENGTHS bullets, the
WEAKNESSES bullets, and the FIT_JUSTIFICATION paragraph. Every
sentence in every section is constrained to reuse a real-human
sentence template, which is the only mechanism that drives GPTZero
AI% to ≤20% on long English prose (see review_corpus/LESSONS.md, v6).

Why a separate module: review_paper.py uses call_with_schema (tool-use)
for the structured numeric fields, but tool-use mode does not
reliably produce template-constrained text — codex tends to bypass the
constraint and write LLM-default English when the field is just a
string in a JSON schema. The free-form mode (codex exec writing to a
file) is what reproduces the verified GPTZero-clean output.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_CORPUS_ROOT = Path(__file__).resolve().parent / "review_corpus"
_PROMPT_TEMPLATE_PATH = _CORPUS_ROOT / "prompt_template.md"
# Full pre-baked pool — fallback if reviewer-batch sampling fails.
_FULL_TEMPLATES_PATH = _CORPUS_ROOT / "processed" / "sentence_templates.txt"


def _sample_for_venue(venue_name: str,
                      num_reviewers: int = 10,
                      few_shot_count: int = 2,
                      seed: int | None = None
                      ) -> tuple[str, list[str]]:
    """Return (rendered_templates_block, expected_field_names).

    Calls the venue-aware sampler. When the target venue has its own
    corpus, prefers same-venue same-field sentences. Otherwise falls
    back to cross-venue sentences from the same canonical bucket. Also
    attaches 1-2 complete reviewer JSONs as few-shot examples.

    expected_field_names is the ordered list of fields the codex artifact
    should produce — used by the parser to map sections back to the
    venue's structured fields.

    Falls back to the legacy full pre-baked pool if the sampler errors
    out, so the pipeline keeps working even if review_corpus changes.
    """
    try:
        from research_harness.stages.review.review_corpus.pipeline import (
            sample_for_venue,
        )
        sample = sample_for_venue.sample_for_venue(
            venue=venue_name,
            num_reviewers=num_reviewers,
            few_shot_count=few_shot_count,
            seed=seed,
        )
        rendered = sample_for_venue.render_for_prompt(sample)
        field_names = list(sample["fields"].keys())
        return rendered, field_names
    except Exception as e:
        # Last-resort fallback: legacy static pool with generic sections.
        return (
            f"# Sampler failed: {type(e).__name__}: {e}. Using full pre-baked pool.\n\n"
            + _FULL_TEMPLATES_PATH.read_text()
        ), ["summary", "strengths", "weaknesses", "questions"]


def _build_prompt(*, venue_name: str, venue_criteria: str,
                  paper_content: str, output_path: str,
                  num_reviewers: int = 10,
                  few_shot_count: int = 2,
                  seed: int | None = None,
                  draft_judgment: dict | None = None
                  ) -> tuple[str, list[str]]:
    """Returns (prompt_string, expected_field_names)."""
    template = _PROMPT_TEMPLATE_PATH.read_text()
    sentence_templates, field_names = _sample_for_venue(
        venue_name, num_reviewers=num_reviewers,
        few_shot_count=few_shot_count, seed=seed)
    judgment_block = (
        _format_draft_judgment(draft_judgment) if draft_judgment else ""
    )
    prompt = (template
            .replace("{{VENUE_NAME}}", venue_name)
            .replace("{{VENUE_CRITERIA}}", venue_criteria)
            .replace("{{SENTENCE_TEMPLATES}}", sentence_templates)
            .replace("{{PAPER_CONTENT}}", paper_content)
            .replace("{{DRAFT_JUDGMENT}}", judgment_block)
            .replace("{{OUTPUT_PATH}}", output_path))
    return prompt, field_names


def _format_draft_judgment(judgment: dict) -> str:
    """Render the prior reviewer judgment as a guidance block. Strict
    rule: bullets get truncated to short fragments so the LLM treats
    them as content guidance and writes new prose from the templates
    instead of paraphrasing draft sentences.
    """
    parts = ["## Reviewer's prior judgment (use as content guidance, "
             "do NOT copy wording — write new prose from the templates)"]
    score = judgment.get("score")
    verdict = judgment.get("verdict")
    sub_scores = judgment.get("sub_scores") or {}
    confidence = judgment.get("confidence")
    if score is not None:
        parts.append(f"- score: {score}")
    if verdict:
        parts.append(f"- verdict: {verdict}")
    if sub_scores:
        for k, v in sub_scores.items():
            parts.append(f"- {k}: {v}")
    if confidence is not None:
        parts.append(f"- confidence: {confidence}")
    bullets = judgment.get("bullets") or {}
    for field, items in bullets.items():
        if not items:
            continue
        parts.append(f"\n### Points to make in `{field}`")
        for it in items:
            it = (it or "").strip().rstrip(".").strip()
            if len(it) > 80:
                it = it[:77] + "…"
            parts.append(f"- {it}")
    parts.append("\nThese bullets are the reviewer's own observations. "
                 "Use them to choose which paper aspects to discuss in "
                 "each section, but write every sentence by picking a "
                 "template from the templates block above and slotting "
                 "in paper facts. Do not copy any phrasing from these "
                 "bullets.")
    return "\n".join(parts)


# Section header regex: matches "## section_name" or "## SECTION_NAME"
# at start of line. Captures the raw header text (case preserved).
_SECTION_RE = re.compile(r"(?ms)^##\s+([\w_][\w_ \-]*)\s*$")

# Bullet line regex: a line that starts with "-", "*", or a number+dot.
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$")

# Fields that are usually rendered as bulleted lists (vs paragraph prose).
# Used to decide whether to parse a section as list[str] or str.
_LIST_FIELDS = {
    "strengths", "weaknesses", "questions", "limitations",
    "reasons_to_accept", "reasons_to_reject",
    "questions_to_authors", "questions_for_authors",
    "ethics_concerns",
}


def _normalize_field_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _parse_artifact(text: str,
                    expected_fields: list[str] | None = None
                    ) -> dict[str, object]:
    """Parse the codex-generated markdown into a dict of text fields.

    Returns a dict mapping each expected field name (lowercased,
    underscored) to its content:
      - list[str] when the field name suggests bullets (strengths,
        weaknesses, questions, etc.)
      - str when it's paragraph prose (summary, review, fit_justification, ...)

    If expected_fields is None, returns whatever sections were found
    (caller can post-validate). Otherwise raises ValueError if any
    expected field is missing.
    """
    sections: dict[str, str] = {}
    last_idx = 0
    last_name: str | None = None
    for m in _SECTION_RE.finditer(text):
        if last_name is not None:
            sections[last_name] = text[last_idx:m.start()].strip()
        last_name = _normalize_field_name(m.group(1))
        last_idx = m.end()
    if last_name is not None:
        sections[last_name] = text[last_idx:].strip()

    if expected_fields:
        normalized_expected = [_normalize_field_name(f) for f in expected_fields]
        missing = [f for f in normalized_expected
                   if not sections.get(f, "").strip()]
        if missing:
            snippet = text[:400].replace("\n", " ")
            raise ValueError(
                f"codex artifact missing expected sections: {missing}. "
                f"Found: {list(sections.keys())}. Head: {snippet!r}")

    def _bullets(body: str) -> list[str]:
        items: list[str] = []
        for line in body.splitlines():
            m = _BULLET_RE.match(line)
            if m:
                items.append(m.group(1).strip())
        if not items:
            items = [p.strip() for p in re.split(r"\n\s*\n", body)
                     if p.strip()]
        return items

    out: dict[str, object] = {}
    keys = (expected_fields and [_normalize_field_name(f) for f in expected_fields]
            or list(sections.keys()))
    for k in keys:
        body = sections.get(k, "").strip()
        if k in _LIST_FIELDS:
            out[k] = _bullets(body)
        else:
            out[k] = body
    return out


def generate_review_text(*, paper_content: str, venue_name: str,
                         venue_criteria: str,
                         num_reviewers: int = 10,
                         few_shot_count: int = 2,
                         seed: int | None = None,
                         model: str = "gpt-5.5",
                         reasoning_effort: str = "medium",
                         timeout_s: int = 600,
                         draft_judgment: dict | None = None
                         ) -> dict[str, object]:
    """Drive codex CLI to produce all free-text review fields for the
    target venue's review form.

    Returns: dict mapping each expected field name (lowercased) to
    either str (prose) or list[str] (bullets). Field names depend on
    the venue's form (see pipeline/sample_for_venue.VENUE_FORM).

    Raises RuntimeError if codex fails or output cannot be parsed.
    """
    if shutil.which("codex") is None:
        raise RuntimeError("codex CLI not on PATH; install or fix PATH")

    workdir = Path(tempfile.mkdtemp(prefix="review_artifact_"))
    try:
        paper_path = workdir / "paper.md"
        paper_path.write_text(paper_content)
        output_path = workdir / "review.md"

        prompt, expected_fields = _build_prompt(
            venue_name=venue_name,
            venue_criteria=venue_criteria,
            paper_content=paper_content,
            output_path=str(output_path),
            num_reviewers=num_reviewers,
            few_shot_count=few_shot_count,
            seed=seed,
            draft_judgment=draft_judgment,
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
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"codex exec failed (rc={result.returncode}): "
                f"{result.stderr[-500:] or result.stdout[-500:]}"
            )

        if not output_path.exists():
            raise RuntimeError(
                f"codex did not write {output_path}; "
                f"last stderr: {result.stderr[-500:]}"
            )
        artifact = output_path.read_text().strip()
        if len(artifact) < 1500:
            raise RuntimeError(
                f"codex produced only {len(artifact)} chars "
                f"(expected ~6000); first 200: {artifact[:200]!r}"
            )

        # Save a debug copy regardless of parse outcome.
        try:
            shutil.copy(output_path, "/tmp/last_review_artifact_codex.md")
        except OSError:
            pass

        parsed = _parse_artifact(artifact, expected_fields=expected_fields)
        # Sanity checks on the most common fields (best effort — not all
        # venue forms have these specific ones).
        from research_harness.stages.review._review_prose_codex import (
            _normalize_field_name as _norm,
        )
        norm_expected = [_norm(f) for f in expected_fields]
        if "summary" in norm_expected:
            s = parsed.get("summary") or ""
            if isinstance(s, str) and len(s) < 200:
                raise RuntimeError(
                    f"summary section only {len(s)} chars (expected longer). "
                    f"Full artifact saved to /tmp/last_review_artifact_codex.md")
        # Soft sanity for bullet-style fields if they're in this venue's form.
        for f in norm_expected:
            v = parsed.get(f)
            if isinstance(v, list) and len(v) < 2:
                raise RuntimeError(
                    f"field {f!r} only produced {len(v)} bullets "
                    f"(expected ≥2). Full artifact at "
                    f"/tmp/last_review_artifact_codex.md")
        return parsed
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
