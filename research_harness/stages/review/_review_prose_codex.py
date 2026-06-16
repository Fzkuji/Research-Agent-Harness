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
            + _FULL_TEMPLATES_PATH.read_text(encoding="utf-8")
        ), ["summary", "strengths", "weaknesses", "questions"]


def _build_prompt(*, venue_name: str, venue_criteria: str,
                  paper_content: str, output_path: str,
                  num_reviewers: int = 10,
                  few_shot_count: int = 2,
                  seed: int | None = None,
                  draft_judgment: dict | None = None
                  ) -> tuple[str, list[str]]:
    """Returns (prompt_string, expected_field_names)."""
    template = _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
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
    # Prose-style fields render as connected paragraphs (one cohesive
    # piece weaving the points together with transitions); bullet-style
    # fields render as separate items 1:1.
    _PROSE_FIELDS = {
        "summary", "review", "fit_justification",
        "reasons_to_accept", "reasons_to_reject",
        "soundness_justification",
    }

    bullets = judgment.get("bullets") or {}
    for field, items in bullets.items():
        if not items:
            continue
        is_prose = field.lower() in _PROSE_FIELDS
        kind = "paragraph points" if is_prose else "list items"
        parts.append(f"\n### Points to make in `{field}` ({kind})")
        for it in items:
            it = (it or "").strip().rstrip(".").strip()
            parts.append(f"- {it}")
        if is_prose:
            parts.append(
                "\nThis is a PROSE field. Compose the bullets into 2-4 "
                "paragraphs (no bullet markers, no `- ` prefixes), "
                "grouping related points within the same paragraph. "
                "RULE 2 STILL APPLIES — every sentence MUST be a "
                "minimal modification of a real-human reviewer "
                "sentence template from the templates block. The "
                "corpus contains transitional templates ('However,', "
                "'In addition,', 'Specifically,', 'For example,', "
                "'On the other hand,', 'The authors should also...') "
                "— pick template sentences that connect to each other "
                "naturally. Do NOT invent free-form transitions or "
                "stitching phrases. Do NOT use 'Furthermore,', "
                "'Moreover,', 'Additionally,' unless those appear in "
                "the templates. The paragraph format is just the "
                "visual arrangement; every sentence in it is still a "
                "template clone with paper-content tokens substituted "
                "in. All bullet content must be covered.")
    parts.append("\nThese bullets are PRE-CULLED telegraph-style "
                 "skeletons: subject + verb + object + key modifiers "
                 "(numbers, equation/table/figure/section refs, "
                 "baseline names, dataset names, component names), "
                 "with articles, transitions, hedges, and first-person "
                 "stripped. Your job: INFLATE each skeleton back into "
                 "a real reviewer-style sentence (1-2 sentences for "
                 "LIST fields; paragraph-form composition for PROSE "
                 "fields per the per-field note above).\n\n"
                 "Mapping rules (LIST fields only — for PROSE fields, "
                 "see the per-field note above):\n"
                 "- 1:1 mapping. Each skeleton -> one output bullet "
                 "(1-2 sentences). Do NOT add bullets not in input. "
                 "Do NOT drop bullets in input. Do NOT split or merge.\n"
                 "- INFLATE the skeleton: insert articles, "
                 "prepositions, connectives that the skeleton "
                 "stripped, so the sentence reads like English. EVERY "
                 "specific token in the skeleton (number, table ref, "
                 "baseline name, etc.) MUST appear in the output. "
                 "Adding paper-grounded context that helps the "
                 "sentence read naturally is fine — for example, "
                 "skeleton 'Table 5 -7.2% w/o X / Sec 6.1 +3.1% / "
                 "explanation unclear / numbers inconsistent' could "
                 "inflate to: 'Table 5 shows a 7.2% drop in metric A "
                 "when module X is removed, but Section 6.1 reports "
                 "only a 3.1% gain from X over the baseline; the "
                 "explanation that the two use different starting "
                 "points is not clearly written and the numbers read "
                 "as inconsistent.'\n"
                 "- RULE 1 (paper grounding) AND content preservation "
                 "override RULE 2 (template fidelity). If a corpus "
                 "template skeleton can host the skeleton's specifics, "
                 "use it. If no template fits without dropping a "
                 "specific, write a plain reviewer sentence that "
                 "keeps the specifics — do not drop the number, table "
                 "ref, baseline name, etc. for template fidelity.\n"
                 "- Do NOT generate filler: no 'this demonstrates the "
                 "thoroughness', 'a notable strength', 'an interesting "
                 "direction'. Every clause in the output sentence "
                 "must come from the skeleton's tokens or trivial "
                 "English glue.\n"
                 "- Style: typical real-reviewer features — varied "
                 "sentence length, occasional hedge ('I think', "
                 "'It seems', 'Perhaps'), mild first-person, plain "
                 "transitions ('However,', 'Specifically,', 'In "
                 "addition,'). NO em dashes, NO 'Furthermore', NO "
                 "'Moreover', NO 'comprehensive', NO 'robust', NO "
                 "'extensive'.\n"
                 "- If a skeleton has so few specifics that you "
                 "cannot inflate it without padding, that is a "
                 "Phase-2 failure — write the shortest faithful "
                 "sentence and move on; do not invent specifics.")
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
                         draft_judgment: dict | None = None,
                         runtime=None,
                         ) -> dict[str, object]:
    """Produce all free-text review fields for the target venue's form.

    Two backends, selected by what's passed:

    - ``runtime`` is given → call ``runtime.exec(prompt)`` directly
      (recommended; same gpt-5.5 model, same prompt, but no codex CLI
      subprocess so it doesn't hang on large prompts or auth contention).
    - ``runtime`` is None → fall back to the legacy ``codex exec`` CLI
      subprocess. Kept for callers that still pass nothing.

    Returns: dict mapping each expected field name (lowercased) to
    either str (prose) or list[str] (bullets). Field names depend on
    the venue's form (see pipeline/sample_for_venue.VENUE_FORM).

    Raises RuntimeError if codex fails or output cannot be parsed.
    """
    # Tempdir under cwd so codex sandbox (when nested via Claude Code /
    # opencode Bash tool) can write to it. /var/folders is sometimes
    # outside workspace-write scope.
    import os as _os
    # Strip lone UTF-16 surrogate code points anywhere upstream let in;
    # write_text would crash on them and the model doesn't need them.
    paper_content = re.sub(r"[\ud800-\udfff]", "", paper_content)

    workdir = Path(tempfile.mkdtemp(prefix="review_artifact_"))
    try:
        output_path = workdir / "review.md"
        if runtime is None:
            # CLI-mode only needs paper on disk for the sandbox.
            (workdir / "paper.md").write_text(paper_content, encoding="utf-8")

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

        # Strip NUL bytes — fork_exec rejects argv with embedded \x00,
        # which leaks in from upstream PDF/docx conversions and from
        # zero-padded markdown writers.
        prompt = prompt.replace("\x00", "")

        if runtime is not None:
            # API path. Strip all variants of write-to-file so the
            # model emits the artifact inline (no codex sandbox here).
            prompt_for_api = prompt
            for marker in (f"`{output_path}`", str(output_path)):
                prompt_for_api = prompt_for_api.replace(
                    marker, "your response"
                )
            prompt_for_api += (
                "\n\nIMPORTANT: emit the markdown artifact directly as "
                "your response text — no preamble, no code fences. "
                "Do NOT attempt to write any file."
            )
            try:
                resp = runtime.exec(
                    content=[{"type": "text", "text": prompt_for_api}]
                )
            except Exception as e:
                raise RuntimeError(f"runtime.exec failed: {e}")
            artifact = (str(resp) if resp is not None else "").strip()
            # Strip code fences if the model wrapped the artifact.
            if artifact.startswith("```"):
                artifact = re.sub(r"^```[a-zA-Z]*\n", "", artifact, count=1)
                artifact = re.sub(r"\n```\s*$", "", artifact, count=1)
        else:
            if shutil.which("codex") is None:
                raise RuntimeError(
                    "codex CLI not on PATH and no runtime passed; "
                    "either install codex or pass runtime="
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
            from research_harness.stages.review._codex_run import run_codex
            result = run_codex(cmd, timeout_s=timeout_s)
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
            artifact = output_path.read_text(encoding="utf-8").strip()

        if len(artifact) < 1500:
            raise RuntimeError(
                f"codex produced only {len(artifact)} chars "
                f"(expected ~6000); first 200: {artifact[:200]!r}"
            )

        # Save a debug copy regardless of parse outcome.
        try:
            Path("/tmp/last_review_artifact_codex.md").write_text(artifact, encoding="utf-8")
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
        # Sanity for bullet-style fields: a field is only broken when it's
        # ENTIRELY empty (the model skipped it). A single bullet is a thin but
        # valid review — not a parse failure — so don't crash the whole review
        # loop over it (it previously raised at <2, contradicting its own
        # "soft sanity" intent and killing otherwise-usable reviews).
        for f in norm_expected:
            v = parsed.get(f)
            if isinstance(v, list) and len(v) == 0:
                raise RuntimeError(
                    f"field {f!r} produced 0 bullets (model skipped it). "
                    f"Full artifact at /tmp/last_review_artifact_codex.md")
        return parsed
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
