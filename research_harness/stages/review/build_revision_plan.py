from __future__ import annotations

import json

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.utils import call_with_schema


_REVISION_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "round_summary": {
            "type": "object",
            "properties": {
                "current_score": {"type": "number"},
                "target_score":  {"type": "number"},
                "scale":         {"type": "string", "description": "e.g. '1-5' or '1-10'"},
                "verdict_from_ac": {"type": "string"},
            },
            "required": ["current_score", "target_score", "scale", "verdict_from_ac"],
        },
        "actions": {
            "type": "array",
            "description": (
                "In-scope action items, ranked CRITICAL → MAJOR → MINOR. "
                "Each one must be specific, located, and executable by a fix agent."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Stable id like 'CRITICAL-1', 'MAJOR-2', 'MINOR-1'.",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "major", "minor"],
                        "description": (
                            "critical = paper rejected without fix; "
                            "major = blocks acceptance but fixable; "
                            "minor = nice-to-have polish."
                        ),
                    },
                    "title": {
                        "type": "string",
                        "description": "One-line summary of the issue.",
                    },
                    "problem": {
                        "type": "string",
                        "description": "Specific problem, quoting reviewer phrasing where useful.",
                    },
                    "location": {
                        "type": "string",
                        "description": (
                            "Specific paper location: 'Section 3.2 paragraph 2', "
                            "'Table 2 row 3', 'Equation (5)', etc. Required precision: "
                            "fix agent must be able to find the spot directly."
                        ),
                    },
                    "fix_action": {
                        "type": "string",
                        "description": (
                            "Concrete action a fix agent can execute. "
                            "'Improve presentation' is NOT acceptable. "
                            "'Split Section 3.2 paragraph 2 into two paragraphs and "
                            "fill in the derivation steps from equation (3) to (7)' IS."
                        ),
                    },
                    "expected_impact": {
                        "type": "string",
                        "description": "Predicted score impact, e.g. 'Soundness +1' or 'Removes R2 main concern'.",
                    },
                    "effort": {
                        "type": "string",
                        "enum": ["trivial", "medium", "heavy"],
                        "description": (
                            "trivial = a few sentences; medium = a section rewrite; "
                            "heavy = new experiment/proof/figure."
                        ),
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Which reviewers raised this. E.g. ['R1', 'R3', 'AC']. "
                            "Used by rebuttal stage to cite back."
                        ),
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of other actions that must complete first. Usually empty.",
                    },
                },
                "required": ["id", "severity", "title", "problem", "location",
                             "fix_action", "effort", "sources"],
            },
        },
        "wont_fix": {
            "type": "array",
            "description": (
                "Issues explicitly NOT addressed this round, with concrete "
                "reasons. Used by the rebuttal stage to argue these aren't "
                "worth blocking acceptance over."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "title":  {"type": "string"},
                    "reason": {
                        "type": "string",
                        "description": (
                            "Concrete reason: 'Needs 4 weeks of GPU time, out of "
                            "scope for this revision' / 'Reviewer misread Section X' / "
                            "'Belongs in future work'. Vague excuses not allowed."
                        ),
                    },
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "reason"],
            },
        },
        "open_questions": {
            "type": "array",
            "description": "Decisions that require author input (conflicting reviewers, scope choices).",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options":  {"type": "array", "items": {"type": "string"}},
                    "sources":  {"type": "array", "items": {"type": "string"}},
                },
                "required": ["question", "options"],
            },
        },
        "execution_order": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Action IDs in the order the fix agent should execute. "
                "Respects depends_on constraints. Typically CRITICAL first."
            ),
        },
    },
    "required": ["round_summary", "actions", "wont_fix", "open_questions",
                 "execution_order"],
}


def _render_plan_markdown(plan: dict, round_num: int = 1) -> str:
    """Render a structured plan as human-readable markdown."""
    rs = plan.get("round_summary", {})
    lines = [
        f"# Revision Plan — Round {round_num}",
        "",
        "## Summary",
        f"- **Current score**: {rs.get('current_score', '?')}/{rs.get('scale', '?')}",
        f"- **Target score**: {rs.get('target_score', '?')}",
        f"- **Verdict from AC**: {rs.get('verdict_from_ac', '?')}",
    ]
    actions = plan.get("actions", [])
    by_sev = {"critical": [], "major": [], "minor": []}
    for a in actions:
        by_sev.setdefault(a.get("severity", "minor"), []).append(a)
    lines.extend([
        f"- **Action items in scope**: "
        f"{len(by_sev['critical'])} CRITICAL + {len(by_sev['major'])} MAJOR + "
        f"{len(by_sev['minor'])} MINOR",
        f"- **Won't Fix this round**: {len(plan.get('wont_fix', []))}",
        f"- **Open Questions**: {len(plan.get('open_questions', []))}",
        "",
        "## Action Items",
        "",
    ])
    for sev_key in ("critical", "major", "minor"):
        for a in by_sev[sev_key]:
            lines.append(f"### [{a.get('id', '?')}] {a.get('title', '?')}")
            lines.append(f"- **Problem**: {a.get('problem', '')}")
            lines.append(f"- **Source**: {', '.join(a.get('sources', []))}")
            lines.append(f"- **Location**: {a.get('location', '')}")
            lines.append(f"- **Fix action**: {a.get('fix_action', '')}")
            lines.append(f"- **Expected impact**: {a.get('expected_impact', '')}")
            lines.append(f"- **Effort**: {a.get('effort', '')}")
            if a.get("depends_on"):
                lines.append(f"- **Depends on**: {', '.join(a['depends_on'])}")
            lines.append("")

    if plan.get("wont_fix"):
        lines.append("## Won't Fix This Round")
        for w in plan["wont_fix"]:
            lines.append(f"- **{w.get('title', '')}**: {w.get('reason', '')}")
        lines.append("")

    if plan.get("open_questions"):
        lines.append("## Open Questions for Author")
        for q in plan["open_questions"]:
            opts = " / ".join(q.get("options", []))
            lines.append(f"- **{q.get('question', '')}** (options: {opts})")
        lines.append("")

    if plan.get("execution_order"):
        lines.append("## Sequencing")
        lines.append("Recommended execution order for fix agent:")
        for i, aid in enumerate(plan["execution_order"], 1):
            lines.append(f"{i}. {aid}")
        lines.append("")

    # Append the raw JSON for downstream programmatic consumption
    lines.append("---")
    lines.append("```json")
    lines.append(json.dumps(plan, ensure_ascii=False, indent=2))
    lines.append("```")
    return "\n".join(lines)


@agentic_function(render_range={"depth": 0, "siblings": 0})
def build_revision_plan(paper_content: str, individual_reviews: str,
                        meta_review: str, venue: str, venue_criteria: str,
                        runtime: Runtime) -> str:
    """Build a structured revision plan from reviewer feedback (tool-use enforced).

    Returns markdown (human-readable plan + embedded JSON block). The JSON
    block matches the schema apply_revision_plan can consume programmatically.

    Goes between review (output: free-form criticism) and fix (input: precise
    actions). The schema ensures every action has id/severity/location/fix_action,
    so downstream apply_revision_plan can iterate over actions without regex
    parsing of free-text.
    """
    instructions = (
        f"You are a senior revision planner. {len(individual_reviews.split('### Reviewer '))-1 if '### Reviewer ' in individual_reviews else 'Multiple'} "
        f"reviewers and an AC have already submitted feedback on this paper. "
        f"Your job is NOT to re-review — it is to ORGANIZE the existing feedback "
        f"into a precise, executable plan for the fix agent.\n\n"
        f"## Required passes\n"
        f"  1. EXTRACT every weakness from individual_reviews + meta_review.\n"
        f"  2. DEDUPLICATE: merge duplicate concerns from multiple reviewers; "
        f"     track which reviewers raised each issue (for sources field).\n"
        f"  3. LOCATE: for each issue, find the specific paper section/paragraph/"
        f"     equation. If the reviewer was vague ('intro is weak'), look at "
        f"     paper_content yourself and pin it to a concrete location.\n"
        f"  4. PRIORITIZE: assign severity\n"
        f"     - critical = paper rejected without fix\n"
        f"     - major    = blocks acceptance but fixable\n"
        f"     - minor    = nice-to-have polish\n"
        f"     Mark heavy-effort items as wont_fix when out of scope (with concrete reason).\n"
        f"     Flag conflicting reviewers as open_questions.\n\n"
        f"## Constraints (the schema enforces structure; you enforce QUALITY)\n"
        f"  - Each fix_action must be EXECUTABLE: 'improve presentation' is NOT "
        f"    acceptable, 'split Section 3.2 paragraph 2 and add derivation steps "
        f"    from equation (3) to (7)' IS acceptable.\n"
        f"  - Each location must be SPECIFIC enough that the fix agent finds the "
        f"    spot without searching.\n"
        f"  - sources must list which reviewers raised the issue (R1/R2/R3/AC).\n"
        f"  - wont_fix reasons must be CONCRETE (no 'will address later').\n"
        f"  - Do NOT add weaknesses reviewers didn't raise. Use open_questions if you "
        f"    notice something they missed.\n\n"
        f"## Inputs\n\n"
        f"=== PAPER CONTENT ===\n{paper_content}\n\n"
        f"=== VENUE CRITERIA ({venue}) ===\n{venue_criteria}\n\n"
        f"=== INDIVIDUAL REVIEWS ===\n{individual_reviews}\n\n"
        f"=== AC META-REVIEW ===\n{meta_review}\n\n"
        f"Now call submit_revision_plan with the structured plan."
    )

    plan = call_with_schema(
        runtime=runtime,
        instructions=instructions,
        schema_name="submit_revision_plan",
        schema_description=(
            "Submit a structured, executable revision plan: action items "
            "(each with severity/location/fix_action/sources/effort), "
            "wont_fix items with concrete reasons, open questions for the "
            "author, and execution order."
        ),
        parameters=_REVISION_PLAN_SCHEMA,
    )

    # Render as markdown (with JSON block for apply_revision_plan).
    # round_num is hard to infer from inside this stage; default to 1, the
    # caller (review_loop) overrides via the file path.
    return _render_plan_markdown(plan, round_num=1)
