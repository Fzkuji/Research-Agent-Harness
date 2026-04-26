from __future__ import annotations

import json

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.utils import call_with_schema


_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "description": (
                "One entry per response in the rebuttal draft, in order. "
                "Each verdict checks evidence + argument quality + concession "
                "appropriateness."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "weakness_id": {
                        "type": "string",
                        "description": "e.g. 'R1.W2' or 'R2-baseline-missing'.",
                    },
                    "original_weakness": {
                        "type": "string",
                        "description": "Quote from the original review (max 200 chars).",
                    },
                    "author_response_summary": {
                        "type": "string",
                        "description": "1-2 sentence summary of what the rebuttal said.",
                    },
                    "stance": {
                        "type": "string",
                        "enum": ["accept", "partial", "reject", "defer"],
                        "description": (
                            "What the author did: accept = agreed and fixed; "
                            "partial = partially conceded; reject = pushed back; "
                            "defer = pushed to future work."
                        ),
                    },
                    "evidence_check": {
                        "type": "string",
                        "enum": ["verified", "evidence_missing", "n_a"],
                        "description": (
                            "verified = author's pointed-to evidence (Section X / "
                            "Table N) actually exists in the paper; "
                            "evidence_missing = claimed evidence not found; "
                            "n_a = response didn't reference paper evidence."
                        ),
                    },
                    "evidence_note": {
                        "type": "string",
                        "description": (
                            "Specifics: 'Author claimed Table 3 has X but Table 3 "
                            "shows only Y'. Required when evidence_check == "
                            "'evidence_missing'."
                        ),
                    },
                    "argument_check": {
                        "type": "string",
                        "enum": ["sound", "dodges_concern", "over_conceded",
                                 "improper_defer"],
                        "description": (
                            "sound = response actually addresses concern; "
                            "dodges_concern = changes subject / non-sequitur; "
                            "over_conceded = author conceded but reviewer was "
                            "wrong / could have pushed back; "
                            "improper_defer = pushed in-scope work to future work."
                        ),
                    },
                    "argument_note": {
                        "type": "string",
                        "description": "One-sentence justification for argument_check.",
                    },
                    "verdict": {
                        "type": "string",
                        "enum": ["sustained", "overruled", "partially_sustained",
                                 "over_conceded"],
                        "description": (
                            "Final ruling: sustained = response stands; "
                            "overruled = response fails (evidence missing OR "
                            "dodges OR improper defer); "
                            "partially_sustained = response valid but should "
                            "narrow scope; "
                            "over_conceded = author should push back instead."
                        ),
                    },
                    "suggested_rewrite": {
                        "type": "string",
                        "description": (
                            "When verdict != sustained: a concrete rewritten "
                            "paragraph showing what the response SHOULD say. "
                            "When sustained: empty string."
                        ),
                    },
                },
                "required": ["weakness_id", "original_weakness",
                             "author_response_summary", "stance",
                             "evidence_check", "argument_check", "verdict"],
            },
        },
        "summary": {
            "type": "object",
            "properties": {
                "total_responses":         {"type": "integer"},
                "sustained":               {"type": "integer"},
                "overruled":               {"type": "integer"},
                "partially_sustained":     {"type": "integer"},
                "over_conceded":           {"type": "integer"},
                "evidence_missing_count":  {"type": "integer"},
                "improper_defer_count":    {"type": "integer"},
                "needs_revision":          {
                    "type": "boolean",
                    "description": "True if rebuttal needs significant rework.",
                },
                "overall_assessment": {
                    "type": "string",
                    "description": (
                        "One paragraph: how strong is the rebuttal overall? "
                        "Which responses most threaten its credibility?"
                    ),
                },
            },
            "required": ["total_responses", "sustained", "overruled",
                         "partially_sustained", "over_conceded",
                         "evidence_missing_count", "improper_defer_count",
                         "needs_revision", "overall_assessment"],
        },
    },
    "required": ["verdicts", "summary"],
}


def _render_audit_markdown(audit: dict) -> str:
    """Render structured audit as human-readable markdown."""
    s = audit.get("summary", {})
    lines = [
        "# Anti-Sycophancy Audit",
        "",
        "## Summary",
        f"- **Total responses**: {s.get('total_responses', 0)}",
        f"- **Sustained**: {s.get('sustained', 0)}",
        f"- **Overruled**: {s.get('overruled', 0)}",
        f"- **Partially sustained**: {s.get('partially_sustained', 0)}",
        f"- **Over-conceded**: {s.get('over_conceded', 0)}",
        f"- **Evidence missing**: {s.get('evidence_missing_count', 0)}",
        f"- **Improper defers**: {s.get('improper_defer_count', 0)}",
        f"- **Needs revision**: {'**YES**' if s.get('needs_revision') else 'no'}",
        "",
        f"### Overall assessment",
        s.get("overall_assessment", ""),
        "",
        "## Per-response verdicts",
        "",
    ]
    for v in audit.get("verdicts", []):
        verdict_emoji = {
            "sustained": "✓ SUSTAINED",
            "overruled": "✗ OVERRULED",
            "partially_sustained": "~ PARTIAL",
            "over_conceded": "⚠ OVER-CONCEDED",
        }.get(v.get("verdict"), v.get("verdict", ""))
        lines.append(f"### {v.get('weakness_id', '?')} — {verdict_emoji}")
        lines.append(f"- **Original weakness**: {v.get('original_weakness', '')}")
        lines.append(f"- **Author's response**: {v.get('author_response_summary', '')}")
        lines.append(f"- **Stance**: {v.get('stance', '')}")
        lines.append(f"- **Evidence check**: {v.get('evidence_check', '')} "
                     f"— {v.get('evidence_note', '')}")
        lines.append(f"- **Argument check**: {v.get('argument_check', '')} "
                     f"— {v.get('argument_note', '')}")
        if v.get("suggested_rewrite"):
            lines.append("- **Suggested rewrite**:")
            lines.append("  > " + v["suggested_rewrite"].replace("\n", "\n  > "))
        lines.append("")

    lines.append("---")
    lines.append("```json")
    lines.append(json.dumps(audit, ensure_ascii=False, indent=2))
    lines.append("```")
    return "\n".join(lines)


@agentic_function(render_range={"depth": 0, "siblings": 0})
def anti_sycophancy_guard(rebuttal_draft: str, original_reviews: str,
                          paper_content: str, venue: str,
                          runtime: Runtime) -> str:
    """Audit a rebuttal draft for sycophancy / evidence gaps / improper defers.

    Schema-enforced output (tool-use). Returns markdown with embedded JSON
    block for downstream programmatic consumption.

    Counters the well-documented LLM bias (ReviewerToo paper, 2510.08867):
    LLM authors writing rebuttals tend to over-concede when the reviewer
    pushes back, even when the original criticism was wrong or addressable.
    This stage acts as a second-opinion check before the rebuttal is sent.
    """
    instructions = (
        f"You are a second-opinion auditor of an author's rebuttal draft for "
        f"{venue}. Your job is NOT to rewrite the rebuttal — it is to check "
        f"each response against three criteria:\n\n"
        f"  1. **Evidence**: When the author claims 'see Section X' or "
        f"     'Table N shows Y', verify those references actually exist in "
        f"     the paper. Mark evidence_missing if not.\n\n"
        f"  2. **Argument quality**: Does the response actually answer the "
        f"     reviewer's concern, or does it dodge / change subject / give "
        f"     non-sequiturs?\n\n"
        f"  3. **Concession appropriateness**: Did the author over-concede "
        f"     when the reviewer's concern was actually invalid? Did they "
        f"     improperly defer in-scope work to 'future work'?\n\n"
        f"For each response in the rebuttal, call submit_audit with one "
        f"verdict entry per weakness. Use these verdict categories:\n"
        f"  - sustained:           response is solid, no change needed\n"
        f"  - overruled:           response fails one of the three checks\n"
        f"  - partially_sustained: response valid but should narrow scope\n"
        f"  - over_conceded:       author should push back instead of conceding\n\n"
        f"For non-sustained verdicts, give a CONCRETE suggested rewrite "
        f"showing what the response should say.\n\n"
        f"=== ORIGINAL REVIEWS ===\n{original_reviews}\n\n"
        f"=== AUTHOR'S REBUTTAL DRAFT ===\n{rebuttal_draft}\n\n"
        f"=== PAPER CONTENT (for evidence verification) ===\n{paper_content}\n\n"
        f"Now call submit_audit with the structured verdicts."
    )

    audit = call_with_schema(
        runtime=runtime,
        instructions=instructions,
        schema_name="submit_audit",
        schema_description=(
            "Submit a per-response audit of the rebuttal draft. Each verdict "
            "checks evidence, argument quality, and concession appropriateness."
        ),
        parameters=_AUDIT_SCHEMA,
    )
    return _render_audit_markdown(audit)
