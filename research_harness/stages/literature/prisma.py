# Adapted from academic-research-skills v3.12.0
# (https://github.com/Imbad0202/academic-research-skills),
# (c) Cheng-I Wu, CC BY-NC 4.0
# Changed: ARS deep-research's prisma_report_template.md (an LLM-filled
# PRISMA 2020 flow template) is recast as a pure-Python report whose
# numbers are computed from the literature loop's state.json ledger.
"""PRISMA-style flow report over the literature loop's real ledger.

`prisma_report(output_dir)` reads `<output_dir>/state.json` (the
canonical machine state written by `run_literature`) and renders
`<output_dir>/synthesis/PRISMA_FLOW.md`: an identification → screening
→ included flow whose counts are computed, not LLM-estimated.

Bucketing — each paper lands in exactly one bucket on a well-formed
state:

  - not yet screened     annotated == False
  - excluded: orphan     is_orphan == True (annotated, never absorbed)
  - excluded: dropped    annotated, no placement on a current framework
                         leaf (topic was pruned, or placements empty)
  - excluded: abstract   annotated + placed, but tier == "abstract_only"
  - included             annotated + placed on a current leaf, full text
                         (pdf / html excerpt) was available

The buckets use independent predicates on purpose: an odd state (e.g. a
paper flagged is_orphan before annotation, or a non-dict papers entry)
breaks the identified = included + excluded + unscreened + surveys
identity and surfaces as a "ledger mismatch" warning in the report
instead of being silently re-balanced.
"""
from __future__ import annotations

import json
import os

from research_harness.stages.literature._state import _iter_leaves


# ─── Flow computation ──────────────────────────────────────────────────

def _compute_flow(state: dict) -> dict:
    """Compute the PRISMA-ish flow counts from a state dict."""
    papers_raw = state.get("papers") or []
    surveys_raw = state.get("surveys") or []
    audit = [a for a in (state.get("audit") or []) if isinstance(a, dict)]
    framework = state.get("framework") or None

    leaf_order = [path for path, _node in _iter_leaves(framework)]
    leaf_paths = set(leaf_order)

    n_papers = len(papers_raw)
    n_surveys = len(surveys_raw)
    identified = n_papers + n_surveys

    seed_rounds = sum(
        1 for a in audit if a.get("action") == "seed_surveys"
    )
    search_rounds = sum(
        1 for a in audit if a.get("action") == "search_papers"
    )

    screened = 0
    unscreened = 0
    excl_orphan = 0
    excl_dropped = 0
    excl_abstract = 0
    included = 0
    topic_counts: dict[str, int] = {path: 0 for path in leaf_order}

    for p in papers_raw:
        if not isinstance(p, dict):
            # Counted in `identified` but in no bucket — shows up as a
            # ledger mismatch below, which is the honest outcome.
            continue
        annotated = bool(p.get("annotated"))
        if annotated:
            screened += 1
        else:
            unscreened += 1
        if p.get("is_orphan"):
            excl_orphan += 1
            continue
        if not annotated:
            continue
        valid = [
            pl for pl in (p.get("placements") or [])
            if isinstance(pl, dict)
            and pl.get("topic_path") in leaf_paths
        ]
        if not valid:
            excl_dropped += 1
            continue
        if p.get("tier") == "abstract_only":
            excl_abstract += 1
            continue
        included += 1
        for pl in valid:
            tp = pl["topic_path"]
            topic_counts[tp] = topic_counts.get(tp, 0) + 1

    excluded_total = excl_orphan + excl_dropped + excl_abstract
    # The ledger identity. Asserted here, but a violation is written
    # into the report as a warning rather than crashing the function —
    # an odd state should still produce a (flagged) report.
    accounted = included + excluded_total + unscreened + n_surveys
    consistent = accounted == identified

    return {
        "identified": identified,
        "n_papers": n_papers,
        "n_surveys": n_surveys,
        "seed_rounds": seed_rounds,
        "search_rounds": search_rounds,
        "screened": screened,
        "unscreened": unscreened,
        "excl_orphan": excl_orphan,
        "excl_dropped": excl_dropped,
        "excl_abstract": excl_abstract,
        "excluded_total": excluded_total,
        "included": included,
        "leaf_order": leaf_order,
        "topic_counts": topic_counts,
        "accounted": accounted,
        "consistent": consistent,
    }


# ─── Markdown rendering ────────────────────────────────────────────────

_HONESTY_FOOTER = """\
## Honesty footer — what does not map onto PRISMA

This is a transparency report over an LLM-driven literature loop,
**not** a systematic-review compliance claim. PRISMA 2020 concepts that
do NOT map cleanly:

- **No duplicate-detection stage.** The loop dedupes by paper id at
  merge time; there is no separate "duplicates removed" count.
- **Screening = LLM annotation, not human double-screening.** A single
  LLM pass places each paper in the framework; there are no independent
  reviewers, no conflict resolution, no inter-rater reliability.
- **Search is iterative and LLM-directed**, not a pre-registered query
  over named databases; the "search rounds" above count loop actions,
  not database queries.
- **"Full text not retrieved" papers may still leak into the prose**:
  abstract-only papers are excluded from the included count here, but
  their abstracts remain in state and can inform synthesis text.
- **No protocol registration, risk-of-bias assessment, effect measures,
  or certainty grading** — the loop produces a narrative review, not a
  meta-analysis.
"""


def _render_md(state: dict, flow: dict) -> str:
    direction = (state.get("direction") or "").strip()
    title = "# PRISMA-style Flow Report"
    if direction:
        title += f" — {direction}"

    lines = [
        title,
        "",
        "*Counts computed directly from `state.json` — "
        "no LLM estimation.*",
        "",
    ]

    if not flow["consistent"]:
        lines.extend([
            f"**WARNING: ledger mismatch** — identified "
            f"({flow['identified']}) != included ({flow['included']}) "
            f"+ excluded ({flow['excluded_total']}) "
            f"+ not yet screened ({flow['unscreened']}) "
            f"+ surveys ({flow['n_surveys']}) = {flow['accounted']}. "
            "State may be mid-update or malformed; counts are reported "
            "as computed.",
            "",
        ])

    total_rounds = flow["seed_rounds"] + flow["search_rounds"]
    lines.extend([
        "## Identification",
        "",
        f"- Records identified: **{flow['identified']}** "
        f"(papers: {flow['n_papers']}, surveys: {flow['n_surveys']})",
        f"- Search rounds (from the audit log): {total_rounds} "
        f"(seed_surveys: {flow['seed_rounds']}, "
        f"search_papers: {flow['search_rounds']})",
        "",
        "## Screening",
        "",
        f"- Records screened (LLM-annotated): **{flow['screened']}**",
        f"- Records not yet screened (unannotated): "
        f"{flow['unscreened']}",
        f"- Records excluded: **{flow['excluded_total']}**",
        f"  - Orphan — annotated but never absorbed into the framework "
        f"(n = {flow['excl_orphan']})",
        f"  - Placements dropped — topic pruned from the framework "
        f"(n = {flow['excl_dropped']})",
        f"  - Full text not retrieved — abstract-only tier "
        f"(n = {flow['excl_abstract']})",
        "",
        "## Included",
        "",
        f"- Papers included in synthesis (placed on current framework "
        f"leaves): **{flow['included']}**",
        f"- Surveys seeding the framework: **{flow['n_surveys']}**",
        "",
        "## Included papers per topic",
        "",
    ])

    if flow["leaf_order"]:
        lines.append("| Topic path | Included papers |")
        lines.append("|---|---|")
        for path in flow["leaf_order"]:
            lines.append(
                f"| {path} | {flow['topic_counts'].get(path, 0)} |"
            )
        lines.extend([
            "",
            "*A paper placed on multiple topics is counted once per "
            "topic; the column total can exceed the included count.*",
        ])
    else:
        lines.append(
            "(no framework leaves — per-topic table unavailable)"
        )

    lines.extend([
        "",
        f"*Ledger check: identified ({flow['identified']}) "
        f"{'=' if flow['consistent'] else '!='} "
        f"included ({flow['included']}) "
        f"+ excluded ({flow['excluded_total']}) "
        f"+ not yet screened ({flow['unscreened']}) "
        f"+ surveys ({flow['n_surveys']}).*",
        "",
        _HONESTY_FOOTER,
    ])
    return "\n".join(lines)


# ─── Entry point ───────────────────────────────────────────────────────

def prisma_report(output_dir: str) -> str:
    """Write a PRISMA-style flow report (synthesis/PRISMA_FLOW.md) with real counts from the literature loop's state.json — pure Python, no LLM.

    Reads `<output_dir>/state.json` (the run_literature ledger) and
    computes an identification → screening → included flow: records
    identified (papers + surveys, with search rounds derived from the
    audit log), records screened (LLM-annotated), excluded with reasons
    (orphans not absorbed, pruned-topic placements dropped,
    abstract-only tier), papers included in synthesis, plus a per-topic
    included-count table from the framework and an honesty footer about
    where PRISMA does not map onto an LLM-driven loop. Counts are
    checked for internal consistency; an odd state yields a "ledger
    mismatch" warning in the report instead of an exception.

    Args:
        output_dir: Literature-loop output directory (must contain
            state.json).

    Returns:
        Summary string naming the report path and headline counts, or
        an "error: ..." string if state.json is missing or unreadable.
    """
    state_path = os.path.join(output_dir, "state.json")
    if not os.path.exists(state_path):
        return (
            f"error: state.json not found at {state_path} — "
            "run the literature loop first"
        )
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return f"error: could not read {state_path}: {e}"
    if not isinstance(state, dict):
        return f"error: {state_path} is not a JSON object"

    flow = _compute_flow(state)
    md = _render_md(state, flow)

    synth_dir = os.path.join(output_dir, "synthesis")
    os.makedirs(synth_dir, exist_ok=True)
    report_path = os.path.join(synth_dir, "PRISMA_FLOW.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)

    summary = (
        f"PRISMA flow report written to {report_path} — "
        f"identified {flow['identified']} "
        f"(papers {flow['n_papers']} + surveys {flow['n_surveys']}), "
        f"screened {flow['screened']}, "
        f"excluded {flow['excluded_total']} "
        f"(orphans {flow['excl_orphan']}, "
        f"pruned {flow['excl_dropped']}, "
        f"abstract-only {flow['excl_abstract']}), "
        f"included {flow['included']}"
    )
    if not flow["consistent"]:
        summary += " — WARNING: ledger mismatch (see report)"
    return summary
