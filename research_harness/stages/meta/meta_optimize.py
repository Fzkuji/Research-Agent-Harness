"""
meta_optimize — outer-loop harness optimization.

Analyzes accumulated usage patterns and proposes improvements to
@agentic_function prompts, default parameters, and workflow ordering.

Inspired by Meta-Harness (Lee et al., 2026): harness design matters
as much as model weights, and harness engineering can be partially
automated by logging execution traces.
"""

from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def meta_optimize(target: str, runtime: Runtime) -> str:
    """Analyze usage logs and propose optimizations to the research harness.

    Observe how the research pipeline is used and propose improvements
    to the harness itself (NOT to the research artifacts it produces).

    ═══════════════════════════════════════════════════════════════
    WHAT YOU OPTIMIZE
    ═══════════════════════════════════════════════════════════════

    | Component               | Example                            | Optimizable? |
    |-------------------------|------------------------------------|:---:|
    | @agentic_function prompts | Reviewer instructions, quality gates | Yes |
    | Default parameters      | difficulty, max_rounds, threshold   | Yes |
    | Convergence rules       | When to stop review loop, retries   | Yes |
    | Workflow ordering        | Stage sequence within pipeline      | Yes |
    | Template schemas         | Fields in EXPERIMENT_LOG, etc.     | Cautious |

    NOT optimized: research artifacts (papers, code, experiments).

    ═══════════════════════════════════════════════════════════════
    ANALYSIS DIMENSIONS
    ═══════════════════════════════════════════════════════════════

    1. FREQUENCY — which functions called most, which parameters overridden
       (common overrides = bad defaults)
    2. FAILURE — which functions fail, what error patterns (OOM, import, etc.)
    3. CONVERGENCE — review loop rounds to threshold, score trajectories,
       plateau vs improvement
    4. HUMAN INTERVENTION — where users manually fix LLM output, common
       corrections (these are prompt improvement signals)
    5. QUALITY — output quality trends, which prompts produce best results

    ═══════════════════════════════════════════════════════════════
    WORKFLOW
    ═══════════════════════════════════════════════════════════════

    Step 1: Check data availability
      Look for usage logs, review logs (AUTO_REVIEW.md,
      PAPER_IMPROVEMENT_LOG.md), and any project history files.
      If insufficient data (<5 runs), report and suggest continuing
      normal use before re-running.

    Step 2: Analyze usage patterns
      Compute frequency, failure, convergence, and intervention metrics.

    Step 3: Generate improvement proposals
      For each finding, propose a minimal, targeted change:
      - Which file to modify
      - What specifically to change
      - Why (backed by data, not opinion)
      - Expected impact
      - Risk assessment

    Step 4: External review
      If a review_runtime is available, send proposals for adversarial
      review. Only proposals that survive review are presented.

    Step 5: Present to user
      Output proposals ranked by impact. NEVER auto-apply changes —
      the user must explicitly approve each one.

    ═══════════════════════════════════════════════════════════════
    SAFETY RULES
    ═══════════════════════════════════════════════════════════════

    - NEVER auto-apply changes. Always present diffs for user approval.
    - Each proposal must cite specific data (log entries, error counts,
      score distributions) — no "I think this would be better" proposals.
    - Prefer parameter tuning over prompt rewriting.
    - Prefer narrower changes over broad rewrites.
    - If data is ambiguous, say so and suggest what additional data
      would resolve the ambiguity.

    ═══════════════════════════════════════════════════════════════

    Based on the target, analyze the relevant data and propose
    optimizations. The target can be: a specific function name,
    a stage name, "review", "writing", "pipeline", or "all".
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": f"Optimize target: {target}"},
    ])
