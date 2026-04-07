"""
theory — mathematical derivation and proof writing.

Helps with formula derivation, proof construction, and
ablation study planning.
"""

from __future__ import annotations

from agentic.function import agentic_function
from agentic.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def derive_formula(notes: str, runtime: Runtime) -> str:
    """Structure and derive research formulas from scattered notes.

    Build an honest derivation package, not a fake polished story.

    For each derivation:
    1. State assumptions explicitly
    2. Define notation precisely
    3. Show every step (no "it is easy to see that...")
    4. Mark approximations clearly (≈ vs =)
    5. Note where assumptions are used

    Status must be one of:
    - COHERENT AS STATED
    - COHERENT AFTER REFRAMING / EXTRA ASSUMPTION
    - NOT YET COHERENT (with blocker explanation)

    Output: LaTeX derivation with assumptions, steps, and status.
    """
    return runtime.exec(content=[
        {"type": "text", "text": notes},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def write_proof(theorem: str, runtime: Runtime) -> str:
    """Write a rigorous mathematical proof for a theorem/lemma.

    Write a mathematically honest proof, not a polished fake.

    Produce exactly one of:
    1. Complete proof of the original claim
    2. Corrected claim + proof (if original is too strong)
    3. Blockage report (if claim is not currently justified)

    Rules:
    - State the exact interpretation of notation/assumptions used.
    - Every step must follow logically. No hand-waving.
    - If a step requires a lemma, state and prove it.
    - Mark where each assumption is used.
    - If the proof requires extra assumptions, state them clearly.

    Status must be one of:
    - PROVABLE AS STATED
    - PROVABLE AFTER WEAKENING / EXTRA ASSUMPTION
    - NOT CURRENTLY JUSTIFIED

    Output: LaTeX proof with status, assumptions, and complete steps.
    """
    return runtime.exec(content=[
        {"type": "text", "text": theorem},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def plan_ablations(method_description: str, results: str,
                   claims: str, runtime: Runtime) -> str:
    """Design ablation studies from a reviewer's perspective.

    For each ablation:
    1. Name: what to change (remove module X, replace Y with Z)
    2. What it tests: the specific question this answers
    3. Expected outcome if component matters
    4. Priority: 1 (must-run) to 5 (nice-to-have)

    Also provide:
    - Coverage: what reviewer questions these ablations answer
    - Unnecessary ablations: experiments that seem useful but won't add insight
    - Suggested run order: maximize early information
    - Compute estimate: total GPU-hours

    Output: Structured ablation plan.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Method:\n{method_description}\n\n"
            f"Results:\n{results}\n\n"
            f"Claims:\n{claims}"
        )},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def refine_research(direction: str, runtime: Runtime) -> str:
    """Refine a vague research direction into a concrete, focused plan.

    Four principles:
    1. Do not lose the original problem. Freeze a Problem Anchor.
    2. The smallest adequate mechanism wins. Minimal intervention.
    3. One paper, one dominant contribution.
    4. Modern leverage (LLM/VLM/RL) is a prior, not a decoration.

    Output a focused proposal:
    - Problem Anchor (immutable)
    - Technical gap identified
    - Proposed method (minimal, elegant)
    - Why this is the sharpest route
    - Minimal validation plan
    - One-sentence thesis

    Output: Structured research plan document.
    """
    return runtime.exec(content=[
        {"type": "text", "text": direction},
    ])


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def write_grant_proposal(direction: str, grant_type: str,
                         runtime: Runtime) -> str:
    """Draft a structured grant proposal from research ideas.

    Supports: NSFC (面上/青年/优青/杰青/海外优青/重点), NSF (US),
    KAKENHI (Japan), ERC (EU), DFG (Germany), ARC (Australia), generic.

    Structure:
    1. Research significance and background
    2. Research objectives and key questions
    3. Research plan and methodology
    4. Expected outcomes and impact
    5. Feasibility: team, resources, timeline
    6. Budget justification (if applicable)

    Rules:
    - Ground every claim in literature or preliminary results.
    - Be specific about methodology — reviewers hate vague plans.
    - One clear thesis, not a laundry list of ideas.
    - Match tone/structure to the specific grant agency's expectations.
    - Include preliminary results if available to demonstrate feasibility.

    Output: Structured grant proposal document.
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Research direction:\n{direction}\n\n"
            f"Grant type: {grant_type}"
        )},
    ])
