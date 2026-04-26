"""Score calibration: venue-aware regression from sub-scores to a final score.

LLM reviewers are unreliable when asked to emit a single scalar score directly.
The Stanford Agentic Reviewer paper showed that scoring sub-dimensions
separately and then fitting a linear regression to map them to the final
score produces calibration close to human reviewers.

This module is pure Python (no LLM call). Reads regression weights from
`references.venue_scoring`. When no fitted weights exist for a venue, falls
back to uniform mean of the available sub-scores, clamped to the venue's
overall_dim scale.
"""

from __future__ import annotations

from typing import Optional

from research_harness.references.venue_scoring import get_venue_spec


# ---------------------------------------------------------------------------
# Per-venue regression weights
#
# Format: {venue_name_normalized: {
#     "intercept": float,
#     "weights":   {sub_dimension_name: float},
#     "scale":     (min, max),     # output clamping range
#     "source":    str,             # provenance / citation
#     "notes":     str,             # any caveats
# }}
#
# Defaults below are baselines from public sources; replace with locally fitted
# weights when we accumulate enough graded reviews for a venue.
# ---------------------------------------------------------------------------

# Venue weights and aliases now live in references/venue_scoring.py.
# Add new venues there; calibrate_score auto-picks them up.


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calibrate_score(sub_scores: dict, venue: str,
                    runtime: Optional[object] = None) -> dict:
    """Map a dict of sub-scores to a calibrated final score for the given venue.

    Reads regression_weights and overall_dim.scale from the venue spec.
    When weights are None (most venues), falls back to mean of inputs.

    Args:
        sub_scores: e.g. {"soundness": 3, "presentation": 2, "contribution": 3}
                    Keys are case-insensitive.
        venue:      Venue name. Aliases handled by venue_scoring.get_venue_spec.
        runtime:    Unused (kept for orchestrator compatibility).
    """
    if not isinstance(sub_scores, dict):
        raise TypeError(f"sub_scores must be dict, got {type(sub_scores).__name__}")

    spec = get_venue_spec(venue)
    inputs = {k.lower(): float(v) for k, v in sub_scores.items()
              if isinstance(v, (int, float))}

    weights = spec.regression_weights or {}
    intercept = weights.pop("intercept", 0.0) if weights else 0.0
    weights_only = {k: v for k, v in weights.items() if k != "intercept"} if weights else {}

    if not weights_only:
        # Uniform mean fallback
        if not inputs:
            score = 0.0
            used = {}
        else:
            score = sum(inputs.values()) / len(inputs)
            used = {k: 1.0 / len(inputs) for k in inputs}
        missing = []
        ignored = []
        source_label = "uniform mean (no fitted weights)"
    else:
        used = {}
        score = intercept
        for dim, w in weights_only.items():
            if dim in inputs:
                score += w * inputs[dim]
                used[dim] = w
        missing = [dim for dim in weights_only if dim not in inputs]
        ignored = [dim for dim in inputs if dim not in weights_only]
        source_label = f"fitted regression for {spec.name}"

    # Restore intercept on weights for the return (we popped it earlier)
    if intercept:
        weights["intercept"] = intercept

    lo, hi = spec.overall_dim.scale
    calibrated = max(lo, min(hi, score))

    return {
        "venue": spec.name,
        "calibrated_score": round(calibrated, 2),
        "raw_score": round(score, 4),
        "scale": (lo, hi),
        "used_weights": used,
        "missing_dimensions": missing,
        "ignored_dimensions": ignored,
        "source": source_label,
        "notes": spec.notes,
    }
