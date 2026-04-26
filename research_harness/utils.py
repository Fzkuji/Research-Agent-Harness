"""Shared utilities."""

from __future__ import annotations

import json
import re


def parse_json(text: str) -> dict:
    """Extract the first JSON object from text, handling markdown fences."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError("No valid JSON found in response")


# ---------------------------------------------------------------------------
# Fallback: extract review fields from markdown when LLM ignores the JSON
# block requirement (common with Codex models that prefer narrative output).
# ---------------------------------------------------------------------------

# Verdict keywords → score. Listed MOST-SPECIFIC FIRST so substring lookup
# matches the most informative keyword (e.g. prefer "weak reject" over
# "borderline" when both appear in the verdict).
_VERDICT_TO_SCORE = [
    # Strong accept territory
    ("strong accept", 9),
    ("borderline accept", 6),
    ("weak accept", 6),
    ("accept", 7),  # plain "accept" — only matched if no "weak/strong/borderline" qualifier hit first
    # Reject side: more specific first
    ("desk reject", 1),
    ("strong reject", 2),
    ("borderline reject", 4),
    ("weak reject", 4),
    ("reject", 3),
    # Borderline (least specific — only if no accept/reject keyword found)
    ("borderline", 5),
    # ARR-style
    ("ready for submission", 7),
    ("almost ready", 5),
    ("not ready", 3),
]


def extract_review_from_markdown(text: str, venue: str = "") -> dict:
    """Best-effort extraction of structured review fields from markdown text.

    Used when the reviewer LLM ignores the strict JSON-block requirement and
    instead returns a narrative review with markdown-formatted scores like
    `**Soundness:** 2.5 / 5`.

    Args:
        text:  The reviewer's markdown output.
        venue: Optional venue name. When provided, verdict-keyword mapping
               uses the venue's specific vocabulary (e.g. ARR's
               "Conference acceptance" = 4, not the generic 1-10 scale).
               Falls back to GENERIC spec when empty/unknown.

    Returns a dict matching the schema of a parsed review:
      {"score": float, "sub_scores": {...}, "weaknesses": [...],
       "strengths": [...], "verdict": str, "confidence": float | None}
    """
    result = {
        "score": 0,
        "sub_scores": {},
        "weaknesses": [],
        "strengths": [],
        "verdict": "",
        "confidence": None,
    }

    # ── Sub-scores: match "**<Name>:** <number>[ / <max>]" with optional
    # leading bullet (markdown lists) or numbered list. Handles both
    #   - **Soundness:** 2.5 / 5
    #   **Soundness:** 2.5 / 5
    #   1. **Soundness:** 2.5 ──
    score_pat = re.compile(
        r"(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?"
        r"\*\*([A-Za-z][A-Za-z0-9 _-]{1,40}?)[\s:]*\*\*"
        r"\s*[:：]?\s*"
        r"([0-9]+(?:\.[0-9]+)?)(?:\s*/\s*[0-9]+)?",
        re.MULTILINE,
    )
    for m in score_pat.finditer(text):
        name = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
        # Skip non-score keys that happen to match the pattern.
        skip_keys = {
            "round", "page", "section", "table", "figure", "equation",
            "appendix", "fig", "tab", "venue", "model", "epoch", "step",
            "answer", "question",
        }
        if name in skip_keys or len(name) > 35:
            continue
        try:
            val = float(m.group(2))
        except ValueError:
            continue
        # Reasonable score range
        if 0 <= val <= 10:
            result["sub_scores"][name] = val

    # Common sub-dim aliases
    for alias, canonical in [("soundness", "soundness"),
                             ("novelty", "novelty"),
                             ("originality", "originality"),
                             ("clarity", "clarity"),
                             ("presentation", "presentation"),
                             ("contribution", "contribution"),
                             ("excitement", "excitement"),
                             ("significance", "significance"),
                             ("reproducibility", "reproducibility")]:
        if alias in result["sub_scores"]:
            result["sub_scores"][canonical] = result["sub_scores"][alias]

    # ── Verdict: three formats covered ──
    #   (1) "- **Overall recommendation:** Weak Reject"     (bulleted bold)
    #   (2) "## Recommendation: Weak Accept"                 (heading inline)
    #   (3) "### Recommendation\n**Reject**"                 (heading + body)
    # Format 3 is handled later as a fallback.
    verdict_patterns = [
        # (1) bold inline split: "- **Recommendation:** Value"
        re.compile(
            r"(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?"
            r"\*\*(?:Overall\s+)?(?:Recommendation|Verdict|Decision|Assessment)[\s:]*\*\*"
            r"\s*[:：]?\s*"
            r"([^\n*]{3,80})",
            re.IGNORECASE | re.MULTILINE,
        ),
        # (2) heading inline: "## Recommendation: Value" / "### Recommendation: Value"
        re.compile(
            r"(?im)^#+\s+(?:Overall\s+)?(?:Recommendation|Verdict|Decision|Assessment)\s*[:：]\s*"
            r"([^\n#]{3,80})",
        ),
        # (3) FULLY-BOLD inline: "**Recommendation: Value**" or
        #     "**Recommendation: Value**, assuming..."
        re.compile(
            r"(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?"
            r"\*\*(?:Overall\s+)?(?:Recommendation|Verdict|Decision|Assessment)\s*[:：]\s*"
            r"([^\n*]{3,80})\*\*",
            re.IGNORECASE | re.MULTILINE,
        ),
    ]
    for pat in verdict_patterns:
        vm = pat.search(text)
        if vm:
            v = vm.group(1).strip()
            # Trim trailing punctuation/markup
            v = re.sub(r"[,;:.\s]+$", "", v).strip("*").strip()
            if v:
                result["verdict"] = v
                break

    # ── Confidence ──
    conf_pat = re.compile(
        r"\*?\*?(?:Reviewer\s+)?Confidence\*?\*?\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    cm = conf_pat.search(text)
    if cm:
        try:
            result["confidence"] = float(cm.group(1))
        except ValueError:
            pass

    # ── Strengths / Weaknesses ──
    def _extract_section(heading_pat: str) -> list[str]:
        # Heading may have trailing words ("Weaknesses and Concerns") so allow
        # anything after the keyword on the heading line.
        sect = re.search(
            rf"(?im)^(#+)\s*(?:{heading_pat})[^\n]*$\n+(.*?)(?=^\1\s|\Z)",
            text, re.DOTALL | re.MULTILINE,
        )
        if not sect:
            return []
        body = sect.group(2) or ""
        if not body.strip():
            return []
        # Two patterns: bulleted list, OR sub-headings ("#### 1. Title\nBody")
        items: list[str] = []
        # Sub-heading style (common in long reviews)
        for m in re.finditer(
            r"(?m)^#{3,}\s+(?:\d+\.\s+)?(.+?)\s*$",
            body,
        ):
            items.append(m.group(1).strip())
        if items:
            return [re.sub(r"\s+", " ", x) for x in items if x]
        # Bullet style fallback
        bullets = re.findall(
            r"(?m)^\s*(?:[-*]|\d+\.)\s+(.+?)(?=\n\s*(?:[-*]|\d+\.)\s|\n\s*\n|\Z)",
            body, re.DOTALL,
        )
        out = [b.strip().replace("\n", " ") for b in bullets if b.strip()]
        return [re.sub(r"\s+", " ", b) for b in out]

    result["strengths"] = _extract_section(
        r"(?:Main\s+|Key\s+|Major\s+)?Strengths?|Pros"
    )
    result["weaknesses"] = _extract_section(
        r"(?:Main\s+|Key\s+|Major\s+)?(?:Weaknesses?|Concerns?|Issues?)|Cons"
    )

    # ── Verdict fallback: "### Recommendation\n**Reject**" pattern ──
    if not result["verdict"]:
        rec_sect = re.search(
            r"(?im)^#+\s*(?:Recommendation|Decision|Verdict|Final\s+Decision)\s*$\n+(.*?)(?=^#+\s|\Z)",
            text, re.DOTALL | re.MULTILINE,
        )
        if rec_sect:
            body = rec_sect.group(1) or ""
            # First non-empty line, stripped of ** markers
            for line in body.splitlines():
                s = line.strip().strip("*").strip()
                if s and len(s) < 100:
                    result["verdict"] = s
                    break

    # ── Final score ──
    # Priority order:
    #   1. Explicit "Overall: X" / "Score: X" / "Rating: X" line
    #   2. sub_scores["overall"] / ["score"] / ["rating"] — model's own total
    #   3. Mean of remaining sub-scores (excluding confidence + total fields)
    #   4. Verdict keyword mapping (longest/most-specific match wins)
    overall_pat = re.compile(
        r"(?:^|\n)\s*\*?\*?(?:Overall\s+score|Overall|Final\s+score|Score|Rating)\s*\*?\*?\s*[:：]\s*"
        r"([0-9]+(?:\.[0-9]+)?)(?:\s*/\s*([0-9]+))?",
        re.IGNORECASE | re.MULTILINE,
    )
    om = overall_pat.search(text)
    score_set = False
    if om:
        try:
            result["score"] = float(om.group(1))
            score_set = True
        except ValueError:
            pass

    # If model put a total in sub_scores, use that — don't average it with sub-dims
    TOTAL_KEYS = ("overall", "overall_score", "score", "rating",
                  "final_score", "recommendation")
    CONFIDENCE_KEYS = ("confidence", "reviewer_confidence")
    if not score_set and result["sub_scores"]:
        for tk in TOTAL_KEYS:
            if tk in result["sub_scores"]:
                result["score"] = result["sub_scores"][tk]
                score_set = True
                break

    if not score_set and result["sub_scores"]:
        # Mean of remaining sub-scores (exclude totals + confidence)
        nums = [v for k, v in result["sub_scores"].items()
                if k not in TOTAL_KEYS and k not in CONFIDENCE_KEYS]
        if nums:
            result["score"] = round(sum(nums) / len(nums), 2)
            score_set = True

    if not score_set and result["verdict"]:
        # Try venue-specific verdict mapping first (uses the venue's vocabulary
        # like "Conference acceptance" = 4 on ARR rather than ICLR's "weak accept").
        venue_score = None
        if venue:
            try:
                from research_harness.references.venue_scoring import (
                    get_venue_spec, map_verdict_to_score,
                )
                venue_score = map_verdict_to_score(get_venue_spec(venue),
                                                   result["verdict"])
            except Exception:
                venue_score = None
        if venue_score is not None:
            result["score"] = venue_score
        else:
            # Fall back to generic 1-10 scale verdict mapping
            v = result["verdict"].lower()
            for kw, sc in _VERDICT_TO_SCORE:
                if kw in v:
                    result["score"] = sc
                    break

    return result


def parse_review_or_extract(text: str, venue: str = "") -> dict:
    """Try parse_json first; on failure, fall back to markdown extraction.

    Args:
        text:  Reviewer output (JSON or markdown).
        venue: Optional venue name passed through to extract_review_from_markdown
               for venue-aware verdict mapping.
    """
    try:
        return parse_json(text)
    except ValueError:
        return extract_review_from_markdown(text, venue=venue)


# ---------------------------------------------------------------------------
# Structured output via tool use — works on every LLM that supports tools
# (OpenAI, Anthropic, Gemini, Bedrock, etc.). The pattern: define a single
# "submit" tool whose parameters ARE the desired schema; force the model to
# call it (tool_choice='required'); capture the args.
#
# This avoids depending on provider-specific JSON-mode features
# (response_format=json_schema is OpenAI-only). Tool use is the cross-provider
# common denominator.
# ---------------------------------------------------------------------------

def call_with_schema(
    runtime,
    instructions: str,
    schema_name: str,
    schema_description: str,
    parameters: dict,
    *,
    max_attempts: int = 2,
) -> dict:
    """Force structured LLM output by exposing a single "submit" tool.

    Args:
        runtime:            An openprogram Runtime (any provider that supports tool use).
        instructions:       The user-facing prompt (task description + input data).
        schema_name:        Tool name shown to the model (e.g. "submit_queries").
        schema_description: One-sentence description of what the tool does.
        parameters:         JSON Schema for the tool's parameters. The keys here
                            become the keys of the returned dict.
        max_attempts:       Retry budget if the model fails to call the tool.
                            Default 2 (try once, retry once with stronger prompt).

    Returns:
        dict matching the `parameters` schema — exactly the args the model
        passed to the submit tool.

    Raises:
        ValueError if the model never called the tool after max_attempts.

    Example:
        result = call_with_schema(
            runtime=rt,
            instructions="Pick the capital of France.",
            schema_name="submit_capital",
            schema_description="Submit the chosen capital city.",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "country": {"type": "string"},
                },
                "required": ["city", "country"],
            },
        )
        # result == {"city": "Paris", "country": "France"}
    """
    captured: dict = {}

    def _executor(**args):
        captured.clear()
        captured.update(args)
        return "OK"

    tool = {
        "spec": {
            "type": "function",
            "name": schema_name,
            "description": schema_description,
            "parameters": parameters,
        },
        "execute": _executor,
    }

    last_error = None
    prompt = instructions
    for attempt in range(1, max_attempts + 1):
        try:
            runtime.exec(
                content=[{"type": "text", "text": prompt}],
                tools=[tool],
                tool_choice="required",
                parallel_tool_calls=False,
                max_iterations=2,
            )
            if captured:
                return dict(captured)
            last_error = "model did not call the submit tool"
        except Exception as e:
            last_error = str(e)

        # Strengthen the prompt for retry
        if attempt < max_attempts:
            prompt = (
                f"{instructions}\n\n"
                f"IMPORTANT: You MUST call the {schema_name!r} tool "
                f"with the required arguments. Do not respond with text."
            )

    raise ValueError(
        f"call_with_schema({schema_name!r}) failed after {max_attempts} attempts: "
        f"{last_error}"
    )
