"""Venue-specific scoring specifications.

Single source of truth for every venue-aware operation in the review pipeline:
  - lookup_venue_criteria: generates the venue criteria text from this spec
  - review_paper_grounded:  builds tool-use schemas with venue's exact scale
  - _meta_review:           same — schema's score field uses venue's scale
  - extract_review_from_markdown: venue-aware verdict-keyword mapping
  - calibrate_score:        venue's regression weights (or fallback mean)

When adding a new venue, prefer to verify the scale against the official
reviewer guidelines (linked in `source_url`). Mark `confidence` field "low"
if the scale was inferred rather than confirmed.

Last updated: 2026-04-26
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScoreDim:
    """A single scoring dimension within a venue's review form."""
    scale: tuple[float, float]
    """(min, max) of the dimension's score range."""

    meanings: dict[float, str]
    """{score_value: human-readable meaning}. Sparse — only the gridpoints."""

    optional: bool = False
    """True if this dimension is optional in the review form."""

    description: str = ""
    """One-sentence description of what this dimension measures."""


@dataclass
class VenueScoring:
    """Complete scoring spec for one venue."""

    name: str
    """Full venue name (e.g. 'ACL Rolling Review')."""

    aliases: tuple[str, ...]
    """Other names this venue is known by (case-insensitive). Used by _normalize_venue."""

    year_known: str
    """Most recent year the spec was verified against the official guidelines."""

    overall_dim: ScoreDim
    """The final/overall recommendation score."""

    sub_dimensions: dict[str, ScoreDim]
    """Other scored dimensions on the form (in display order)."""

    confidence_dim: Optional[ScoreDim] = None
    """Reviewer's self-confidence in their assessment, if the venue tracks it."""

    accept_threshold: float = 0
    """Overall score >= this is considered 'main conference accept'."""

    secondary_threshold: Optional[float] = None
    """Overall score >= this is considered 'Findings/Workshop track' (if applicable)."""

    secondary_track_name: str = ""
    """E.g. 'Findings of ACL'. Empty if no secondary track."""

    verdict_canonical: dict[str, list[str]] = field(default_factory=dict)
    """{canonical_decision: [keyword1, keyword2, ...]}.
    Used by extract_review_from_markdown to map free-text verdicts to scores.
    Keys should be sortable by 'specificity' (most-specific first); we list
    most-specific keywords first within each list."""

    verdict_to_score: dict[str, float] = field(default_factory=dict)
    """{canonical_decision: score on overall_dim's scale}.
    Used as fallback when LLM emits a verdict but no numeric score."""

    regression_weights: Optional[dict[str, float]] = None
    """Sub-dim weights for calibrate_score. Includes 'intercept' key.
    None = use mean of sub-scores."""

    source_url: str = ""
    """Link to the official reviewer guidelines for this venue/year."""

    confidence: str = "high"
    """'high' = verified from official source; 'medium' = inferred from
    similar venue; 'low' = best guess, please verify."""

    notes: str = ""
    """Caveats, e.g. 'overall scale changed in 2025'."""


# ---------------------------------------------------------------------------
# Venue specs
# ---------------------------------------------------------------------------

ARR = VenueScoring(
    name="ACL Rolling Review (ARR)",
    aliases=("acl", "arr", "emnlp", "naacl", "eacl", "aacl"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0:  "Consider for Award (top ~2.5%)",
            4.5:  "Borderline Award",
            4.0:  "Conference acceptance (main conference)",
            3.5:  "Borderline Conference",
            3.0:  "Findings acceptance",
            2.5:  "Borderline Findings",
            2.0:  "Resubmit next cycle",
            1.5:  "Resubmit after next cycle",
            1.0:  "Do not resubmit",
        },
        description="Overall publication recommendation on ARR's 1-5 scale (with .5 increments).",
    ),
    sub_dimensions={
        "soundness": ScoreDim(
            scale=(1.0, 5.0),
            meanings={
                5.0: "Excellent — one of the most thorough studies of its type",
                4.0: "Strong — sufficient support for all claims",
                3.0: "Acceptable — sufficient support for main claims",
                2.0: "Poor — main claims lack sufficient support; major problems",
                1.0: "Major Issues — not yet sufficient to warrant publication",
            },
            description="Soundness/rigor of the technical claims and methodology.",
        ),
        "excitement": ScoreDim(
            scale=(1.0, 5.0),
            meanings={
                5.0: "Highly Exciting — would recommend / attend presentation",
                4.0: "Exciting — would mention to others / attend if convenient",
                3.0: "Mildly Interesting — might mention some points",
                2.0: "Potentially Interesting — does not resonate with me, might with others",
                1.0: "Not Exciting — unlikely to resonate with the *ACL community",
            },
            description="Subjective excitement / impact / novelty.",
        ),
        "reproducibility": ScoreDim(
            scale=(1.0, 5.0),
            meanings={
                5.0: "Easily reproducible",
                4.0: "Mostly reproducible (minor variations possible)",
                3.0: "Reproducible with difficulty",
                2.0: "Hard to reproduce (data/details unavailable)",
                1.0: "Cannot reproduce",
            },
            optional=True,
            description="How easily another researcher could reproduce the results.",
        ),
    },
    confidence_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0: "Very confident — careful reading, familiar with related work",
            4.0: "Confident — unlikely to have missed important details",
            3.0: "Pretty confident — didn't carefully check all details",
            2.0: "Willing to defend but likely missed some details",
            1.0: "Not my area, or very hard to understand",
        },
    ),
    accept_threshold=4.0,                  # Main conference
    secondary_threshold=3.0,               # Findings
    secondary_track_name="Findings of ACL",
    verdict_canonical={
        "award":          ["consider for award", "award"],
        "main_accept":    ["conference acceptance", "accept main", "main conference"],
        "borderline_main":["borderline conference"],
        "findings":       ["findings acceptance", "findings", "borderline accept"],
        "borderline_findings": ["borderline findings"],
        "resubmit_soon":  ["resubmit next cycle"],
        "resubmit_later": ["resubmit after next cycle"],
        "no_resubmit":    ["do not resubmit", "strong reject"],
    },
    verdict_to_score={
        "award": 5.0, "main_accept": 4.0, "borderline_main": 3.5,
        "findings": 3.0, "borderline_findings": 2.5,
        "resubmit_soon": 2.0, "resubmit_later": 1.5, "no_resubmit": 1.0,
    },
    source_url="https://aclrollingreview.org/reviewform",
)

NEURIPS = VenueScoring(
    name="NeurIPS",
    aliases=("neurips", "nips"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 6.0),
        meanings={
            6.0: "Strong Accept — technically flawless, groundbreaking impact",
            5.0: "Accept — technically solid, high impact",
            4.0: "Borderline accept — reasons to accept outweigh reasons to reject",
            3.0: "Borderline reject — reasons to reject outweigh reasons to accept",
            2.0: "Reject — technical flaws, weak evaluation, inadequate reproducibility",
            1.0: "Strong Reject — well-known results or unaddressed ethical issues",
        },
        description=(
            "NeurIPS 2025 changed from 1-10 to 1-6 scale. Keep this in mind "
            "when comparing to historical scores."
        ),
    ),
    sub_dimensions={
        "quality": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
            description="Quality of the work (Strengths and Weaknesses).",
        ),
        "clarity": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
            description="Clarity of presentation, writing, contextualization.",
        ),
        "significance": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
            description="Significance of the contribution to the field.",
        ),
        "originality": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
            description="Originality of ideas / approach.",
        ),
    },
    confidence_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0: "Absolutely certain — checked math/details carefully",
            4.0: "Confident, not absolutely certain",
            3.0: "Fairly confident — possible some parts were missed",
            2.0: "Willing to defend, but central parts may be missed",
            1.0: "Educated guess",
        },
    ),
    accept_threshold=4.0,                  # Borderline accept and above
    secondary_threshold=None,
    verdict_canonical={
        "strong_accept":    ["strong accept"],
        "accept":           ["accept"],
        "borderline_accept":["borderline accept"],
        "borderline_reject":["borderline reject"],
        "reject":           ["reject"],
        "strong_reject":    ["strong reject"],
    },
    verdict_to_score={
        "strong_accept": 6.0, "accept": 5.0,
        "borderline_accept": 4.0, "borderline_reject": 3.0,
        "reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://neurips.cc/Conferences/2025/ReviewerGuidelines",
    notes="NeurIPS 2025 changed Overall scale from 1-10 to 1-6.",
)

ICLR = VenueScoring(
    name="ICLR",
    aliases=("iclr",),
    year_known="2026",
    overall_dim=ScoreDim(
        scale=(0.0, 10.0),
        meanings={
            10.0: "Strong Accept — top 5% of accepted papers",
            8.0:  "Accept — solid, top 50% of accepted",
            6.0:  "Marginally above acceptance threshold",
            4.0:  "Marginally below acceptance threshold",
            2.0:  "Reject — significant issues",
            0.0:  "Strong Reject — fundamental problems",
        },
        description=(
            "ICLR 2026 uses {0, 2, 4, 6, 8, 10} (no odd values). Removes the "
            "middle-ground 5 to force decisive opinions."
        ),
    ),
    sub_dimensions={
        "soundness": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
            description="Technical soundness of claims, methodology, and evidence.",
        ),
        "presentation": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
            description="Quality of presentation, writing, contextualization.",
        ),
        "contribution": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
            description="Quality and importance of the contribution.",
        ),
    },
    confidence_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0: "Absolutely certain",
            4.0: "Confident, not absolutely certain",
            3.0: "Fairly confident",
            2.0: "Willing to defend, possibly missed details",
            1.0: "Educated guess",
        },
    ),
    accept_threshold=6.0,
    secondary_threshold=None,
    verdict_canonical={
        "strong_accept":  ["strong accept", "10"],
        "accept":         ["accept", "8"],
        "marginal_accept":["marginally above", "6"],
        "marginal_reject":["marginally below", "4"],
        "reject":         ["reject", "2"],
        "strong_reject":  ["strong reject", "0"],
    },
    verdict_to_score={
        "strong_accept": 10.0, "accept": 8.0, "marginal_accept": 6.0,
        "marginal_reject": 4.0, "reject": 2.0, "strong_reject": 0.0,
    },
    # debashis1983/agentic-paper-review weights (fitted on 46K ICLR 2025 reviews,
    # ρ ≈ 0.74 with human reviewers); inputs on 1-4, output on 1-10.
    regression_weights={
        "intercept": -0.3057,
        "soundness": 0.7134,
        "presentation": 0.4242,
        "contribution": 1.0588,
    },
    source_url="https://iclr.cc/Conferences/2026/ReviewerGuide",
    notes="ICLR 2026 uses even-only {0,2,4,6,8,10} to remove borderline 5.",
)

ICML = VenueScoring(
    name="ICML",
    aliases=("icml",),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 6.0),
        meanings={
            6.0: "Strong Accept",
            5.0: "Accept",
            4.0: "Weak Accept",
            3.0: "Weak Reject",
            2.0: "Reject",
            1.0: "Strong Reject",
        },
        description="ICML 2025 overall recommendation on a 1-6 scale.",
    ),
    sub_dimensions={
        "soundness": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
        ),
        "presentation": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
        ),
        "significance": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
        ),
        "originality": ScoreDim(
            scale=(1.0, 4.0),
            meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"},
        ),
    },
    confidence_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={5.0: "Absolutely certain", 3.0: "Fairly confident", 1.0: "Educated guess"},
    ),
    accept_threshold=4.0,
    secondary_threshold=None,
    verdict_canonical={
        "strong_accept": ["strong accept"],
        "accept":        ["accept"],
        "weak_accept":   ["weak accept", "borderline accept"],
        "weak_reject":   ["weak reject", "borderline reject"],
        "reject":        ["reject"],
        "strong_reject": ["strong reject"],
    },
    verdict_to_score={
        "strong_accept": 6.0, "accept": 5.0, "weak_accept": 4.0,
        "weak_reject": 3.0, "reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://icml.cc/Conferences/2025/ReviewerInstructions",
    confidence="medium",
    notes="ICML scale inferred from 2025 reviewer instructions; verify exact dim names.",
)

CVPR = VenueScoring(
    name="CVPR / ICCV / ECCV (CVF)",
    aliases=("cvpr", "iccv", "eccv", "wacv"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0: "Strong Accept",
            4.0: "Weak Accept",
            3.0: "Borderline",
            2.0: "Weak Reject",
            1.0: "Strong Reject",
        },
        description="CVF venues use a 1-5 overall scale.",
    ),
    sub_dimensions={},  # CVPR primarily emphasizes overall + free-text strengths/weaknesses
    confidence_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"},
    ),
    accept_threshold=4.0,
    secondary_threshold=None,
    verdict_canonical={
        "strong_accept": ["strong accept"],
        "weak_accept":   ["weak accept"],
        "borderline":    ["borderline"],
        "weak_reject":   ["weak reject"],
        "strong_reject": ["strong reject", "reject"],
    },
    verdict_to_score={
        "strong_accept": 5.0, "weak_accept": 4.0, "borderline": 3.0,
        "weak_reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://cvpr.thecvf.com/Conferences/2025/ReviewerGuidelines",
    confidence="medium",
    notes="CVF scale not exhaustively documented in public guidelines; verify if exact.",
)

ACM_MM = VenueScoring(
    name="ACM Multimedia (ACM MM)",
    aliases=("acmmm", "acm mm", "acm_mm", "mm", "acm-mm"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 6.0),
        meanings={
            6.0: "Strong Accept — outstanding contribution to multimedia",
            5.0: "Accept — solid contribution, recommend acceptance",
            4.0: "Weak Accept — marginal accept, reasons to accept outweigh reject",
            3.0: "Weak Reject — marginal reject, reasons to reject outweigh accept",
            2.0: "Reject — significant issues, not ready for publication",
            1.0: "Strong Reject — fundamental problems",
        },
        description=(
            "ACM MM uses a 1-6 overall scale. Inferred from PaperCopilot stats "
            "(2024 reviewer averages spanned 2.5-5.5)."
        ),
    ),
    sub_dimensions={
        "soundness": ScoreDim(
            scale=(1.0, 5.0),
            meanings={5.0: "excellent", 4.0: "good", 3.0: "fair",
                      2.0: "marginal", 1.0: "poor"},
            description="Technical soundness of methodology and claims.",
        ),
        "originality": ScoreDim(
            scale=(1.0, 5.0),
            meanings={5.0: "excellent", 4.0: "good", 3.0: "fair",
                      2.0: "marginal", 1.0: "poor"},
            description="Novelty of ideas / approach.",
        ),
        "significance": ScoreDim(
            scale=(1.0, 5.0),
            meanings={5.0: "excellent", 4.0: "good", 3.0: "fair",
                      2.0: "marginal", 1.0: "poor"},
            description="Significance of contribution to multimedia research.",
        ),
        "clarity": ScoreDim(
            scale=(1.0, 5.0),
            meanings={5.0: "excellent", 4.0: "good", 3.0: "fair",
                      2.0: "marginal", 1.0: "poor"},
            description="Clarity of presentation, writing, figures.",
        ),
        "reproducibility": ScoreDim(
            scale=(1.0, 5.0),
            meanings={5.0: "easily reproducible", 3.0: "with difficulty",
                      1.0: "not reproducible"},
            optional=True,
            description="How easily the work could be reproduced.",
        ),
    },
    confidence_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"},
    ),
    accept_threshold=4.0,                  # Weak Accept and above
    secondary_threshold=None,
    verdict_canonical={
        "strong_accept": ["strong accept"],
        "accept":        ["accept"],
        "weak_accept":   ["weak accept", "borderline accept"],
        "weak_reject":   ["weak reject", "borderline reject"],
        "reject":        ["reject"],
        "strong_reject": ["strong reject"],
    },
    verdict_to_score={
        "strong_accept": 6.0, "accept": 5.0, "weak_accept": 4.0,
        "weak_reject": 3.0, "reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://acmmm2025.org/reviewer-and-area-chair-guidelines/",
    confidence="medium",
    notes=(
        "ACM MM does not publicly publish exact review form. Overall scale "
        "(1-6) inferred from PaperCopilot statistics; sub-dimensions are "
        "ACM standard (Soundness/Originality/Significance/Clarity/"
        "Reproducibility). Verify against actual review form in OpenReview."
    ),
)

AAAI = VenueScoring(
    name="AAAI",
    aliases=("aaai",),
    year_known="2026",
    overall_dim=ScoreDim(
        scale=(1.0, 6.0),
        meanings={
            6.0: "Strong Accept",
            5.0: "Accept",
            4.0: "Weak Accept",
            3.0: "Weak Reject",
            2.0: "Reject",
            1.0: "Strong Reject",
        },
        description="AAAI two-phase review; rough mapping to 1-6.",
    ),
    sub_dimensions={
        "soundness": ScoreDim(
            scale=(1.0, 5.0),
            meanings={5.0: "excellent", 4.0: "good", 3.0: "fair", 2.0: "marginal", 1.0: "poor"},
        ),
        "originality": ScoreDim(
            scale=(1.0, 5.0),
            meanings={5.0: "excellent", 4.0: "good", 3.0: "fair", 2.0: "marginal", 1.0: "poor"},
        ),
        "significance": ScoreDim(
            scale=(1.0, 5.0),
            meanings={5.0: "excellent", 4.0: "good", 3.0: "fair", 2.0: "marginal", 1.0: "poor"},
        ),
    },
    confidence_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"},
    ),
    accept_threshold=4.0,
    secondary_threshold=None,
    verdict_canonical={
        "strong_accept": ["strong accept"],
        "accept":        ["accept"],
        "weak_accept":   ["weak accept"],
        "weak_reject":   ["weak reject"],
        "reject":        ["reject"],
        "strong_reject": ["strong reject"],
    },
    verdict_to_score={
        "strong_accept": 6.0, "accept": 5.0, "weak_accept": 4.0,
        "weak_reject": 3.0, "reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://aaai.org/conference/aaai/aaai-26/instructions-for-aaai-26-reviewers/",
    confidence="medium",
    notes="AAAI exact form not in public guidelines; spec inferred. Verify before relying.",
)

# ---------------------------------------------------------------------------
# Additional venues (batch-added 2026-04-26)
# ---------------------------------------------------------------------------

# COLM uses OpenReview with ICLR-style review form (1-10 scale + Soundness/
# Presentation/Contribution sub-dims).
COLM = VenueScoring(
    name="COLM (Conference on Language Modeling)",
    aliases=("colm",),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 10.0),
        meanings={
            10.0: "Strong Accept", 8.0: "Accept", 6.0: "Marginally above threshold",
            5.0:  "Borderline", 4.0:  "Marginally below threshold",
            2.0:  "Reject", 1.0:  "Strong Reject",
        },
    ),
    sub_dimensions={
        "soundness":    ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "presentation": ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "contribution": ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Absolutely certain", 3.0: "Fairly confident", 1.0: "Educated guess"}),
    accept_threshold=6.0,
    verdict_canonical={
        "strong_accept": ["strong accept"], "accept": ["accept"],
        "marginal_accept": ["marginally above"], "marginal_reject": ["marginally below"],
        "reject": ["reject"], "strong_reject": ["strong reject"],
    },
    verdict_to_score={
        "strong_accept": 10.0, "accept": 8.0, "marginal_accept": 6.0,
        "marginal_reject": 4.0, "reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://colmweb.org/",
    confidence="medium",
    notes="Uses OpenReview ICLR-style form. Verify against actual reviewer guide.",
)

# COLING uses ARR review form (same as ACL/EMNLP).
COLING = VenueScoring(
    name="COLING",
    aliases=("coling",),
    year_known="2025",
    overall_dim=ARR.overall_dim,
    sub_dimensions=ARR.sub_dimensions,
    confidence_dim=ARR.confidence_dim,
    accept_threshold=ARR.accept_threshold,
    secondary_threshold=ARR.secondary_threshold,
    secondary_track_name="COLING Findings (if applicable)",
    verdict_canonical=ARR.verdict_canonical,
    verdict_to_score=ARR.verdict_to_score,
    source_url="https://aclrollingreview.org/reviewform",
    confidence="medium",
    notes="Inherits ARR review form (COLING typically uses ARR pipeline).",
)

# IJCAI: 1-6 scale, similar to AAAI.
IJCAI = VenueScoring(
    name="IJCAI",
    aliases=("ijcai",),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 10.0),
        meanings={
            10.0: "Top 5%", 8.0: "Top 25%, accept", 6.0: "Top 50%, marginal accept",
            5.0:  "Borderline", 4.0:  "Bottom 50%, marginal reject",
            2.0:  "Bottom 25%, reject", 1.0:  "Bottom 5%, strong reject",
        },
    ),
    sub_dimensions={
        "originality":  ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "soundness":    ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "significance": ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "clarity":      ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"}),
    accept_threshold=6.0,
    verdict_canonical={
        "strong_accept": ["strong accept", "top 5"], "accept": ["accept", "top 25"],
        "marginal_accept": ["marginal accept"], "marginal_reject": ["marginal reject"],
        "reject": ["reject"], "strong_reject": ["strong reject"],
    },
    verdict_to_score={
        "strong_accept": 10.0, "accept": 8.0, "marginal_accept": 6.0,
        "marginal_reject": 4.0, "reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://www.ijcai.org/",
    confidence="medium",
)

# AISTATS: 1-6 scale similar to ICML, with categorical soundness option.
AISTATS = VenueScoring(
    name="AISTATS",
    aliases=("aistats",),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 6.0),
        meanings={
            6.0: "Strong Accept", 5.0: "Accept", 4.0: "Weak Accept",
            3.0: "Weak Reject", 2.0: "Reject", 1.0: "Strong Reject",
        },
    ),
    sub_dimensions={
        "soundness":    ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "minor errors", 2.0: "major errors", 1.0: "fundamentally flawed"}),
        "presentation": ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "significance": ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "originality":  ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Absolutely certain", 3.0: "Fairly confident", 1.0: "Educated guess"}),
    accept_threshold=4.0,
    verdict_canonical={
        "strong_accept": ["strong accept"], "accept": ["accept"],
        "weak_accept": ["weak accept"], "weak_reject": ["weak reject"],
        "reject": ["reject"], "strong_reject": ["strong reject"],
    },
    verdict_to_score={
        "strong_accept": 6.0, "accept": 5.0, "weak_accept": 4.0,
        "weak_reject": 3.0, "reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://aistats.org/aistats2025/reviewer_guidelines.html",
    confidence="medium",
)

# UAI: 1-10 scale, similar to ICLR.
UAI = VenueScoring(
    name="UAI",
    aliases=("uai",),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 10.0),
        meanings={
            10.0: "Top 5% accept", 8.0: "Accept", 6.0: "Marginal accept",
            5.0:  "Borderline", 4.0:  "Marginal reject",
            2.0:  "Reject", 1.0:  "Strong reject",
        },
    ),
    sub_dimensions={
        "soundness":    ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "significance": ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "novelty":      ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "clarity":      ScoreDim(scale=(1.0, 4.0),
                                 meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"}),
    accept_threshold=6.0,
    verdict_canonical={
        "strong_accept": ["strong accept"], "accept": ["accept"],
        "marginal_accept": ["marginal accept"], "marginal_reject": ["marginal reject"],
        "reject": ["reject"], "strong_reject": ["strong reject"],
    },
    verdict_to_score={
        "strong_accept": 10.0, "accept": 8.0, "marginal_accept": 6.0,
        "marginal_reject": 4.0, "reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://www.auai.org/",
    confidence="low",
)

# KDD 2025: 4-point scale (reduced from 5-point), 6 dimensions.
KDD = VenueScoring(
    name="KDD",
    aliases=("kdd", "sigkdd"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 4.0),
        meanings={
            4.0: "Accept — clear contribution",
            3.0: "Lean accept — reasons to accept outweigh reject",
            2.0: "Lean reject — reasons to reject outweigh accept",
            1.0: "Reject",
        },
        description="KDD 2025 changed from 5-point to 4-point scale (no neutral midpoint).",
    ),
    sub_dimensions={
        "relevance":         ScoreDim(scale=(1.0, 4.0),
                                       meanings={4.0: "highly relevant", 3.0: "relevant", 2.0: "marginally", 1.0: "off-topic"}),
        "novelty":           ScoreDim(scale=(1.0, 4.0),
                                       meanings={4.0: "highly novel", 3.0: "novel", 2.0: "incremental", 1.0: "not novel"}),
        "technical_quality": ScoreDim(scale=(1.0, 4.0),
                                       meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "presentation":      ScoreDim(scale=(1.0, 4.0),
                                       meanings={4.0: "excellent", 3.0: "good", 2.0: "fair", 1.0: "poor"}),
        "reproducibility":   ScoreDim(scale=(1.0, 4.0),
                                       meanings={4.0: "fully reproducible", 3.0: "mostly", 2.0: "partial", 1.0: "not reproducible"}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"}),
    accept_threshold=3.0,
    verdict_canonical={
        "accept": ["accept"], "lean_accept": ["lean accept"],
        "lean_reject": ["lean reject"], "reject": ["reject"],
    },
    verdict_to_score={"accept": 4.0, "lean_accept": 3.0, "lean_reject": 2.0, "reject": 1.0},
    source_url="https://kdd2025.kdd.org/call-for-reviewers/",
    confidence="medium",
)

# WWW (TheWebConf): 1-5 scale with similar dims to KDD.
WWW = VenueScoring(
    name="WWW (The Web Conference)",
    aliases=("www", "thewebconf", "webconf"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0: "Strong Accept", 4.0: "Weak Accept",
            3.0: "Borderline", 2.0: "Weak Reject", 1.0: "Strong Reject",
        },
    ),
    sub_dimensions={
        "novelty":    ScoreDim(scale=(1.0, 5.0), meanings={}),
        "soundness":  ScoreDim(scale=(1.0, 5.0), meanings={}),
        "significance": ScoreDim(scale=(1.0, 5.0), meanings={}),
        "clarity":    ScoreDim(scale=(1.0, 5.0), meanings={}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"}),
    accept_threshold=4.0,
    verdict_canonical={
        "strong_accept": ["strong accept"], "weak_accept": ["weak accept"],
        "borderline": ["borderline"], "weak_reject": ["weak reject"], "strong_reject": ["strong reject", "reject"],
    },
    verdict_to_score={
        "strong_accept": 5.0, "weak_accept": 4.0, "borderline": 3.0,
        "weak_reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://www2025.thewebconf.org/",
    confidence="low",
)

# MLSys: 1-6 scale similar to NeurIPS.
MLSYS = VenueScoring(
    name="MLSys",
    aliases=("mlsys",),
    year_known="2025",
    overall_dim=NEURIPS.overall_dim,
    sub_dimensions=NEURIPS.sub_dimensions,
    confidence_dim=NEURIPS.confidence_dim,
    accept_threshold=4.0,
    verdict_canonical=NEURIPS.verdict_canonical,
    verdict_to_score=NEURIPS.verdict_to_score,
    source_url="https://mlsys.org/",
    confidence="low",
    notes="Inherits NeurIPS-style form. Verify before relying.",
)

# BMVC / ACCV: CVPR-style 1-5 (sibling CV venues).
BMVC = VenueScoring(
    name="BMVC",
    aliases=("bmvc",),
    year_known="2025",
    overall_dim=CVPR.overall_dim,
    sub_dimensions=CVPR.sub_dimensions,
    confidence_dim=CVPR.confidence_dim,
    accept_threshold=CVPR.accept_threshold,
    verdict_canonical=CVPR.verdict_canonical,
    verdict_to_score=CVPR.verdict_to_score,
    source_url="https://bmvc.org/",
    confidence="low",
    notes="Inherits CVF-style form.",
)

ACCV = VenueScoring(
    name="ACCV",
    aliases=("accv",),
    year_known="2024",
    overall_dim=CVPR.overall_dim,
    sub_dimensions=CVPR.sub_dimensions,
    confidence_dim=CVPR.confidence_dim,
    accept_threshold=CVPR.accept_threshold,
    verdict_canonical=CVPR.verdict_canonical,
    verdict_to_score=CVPR.verdict_to_score,
    source_url="https://accv2024.org/",
    confidence="low",
    notes="Inherits CVF-style form.",
)

MM_ASIA = VenueScoring(
    name="ACM MM Asia",
    aliases=("mm asia", "mmasia", "mm-asia", "acmmm asia"),
    year_known="2025",
    overall_dim=ACM_MM.overall_dim,
    sub_dimensions=ACM_MM.sub_dimensions,
    confidence_dim=ACM_MM.confidence_dim,
    accept_threshold=ACM_MM.accept_threshold,
    verdict_canonical=ACM_MM.verdict_canonical,
    verdict_to_score=ACM_MM.verdict_to_score,
    source_url="https://mmasia2025.org/",
    confidence="low",
    notes="Inherits ACM MM form.",
)

# Robotics: CoRL uses OpenReview (ICLR-style); ICRA/IROS use IEEE 1-5.
CORL = VenueScoring(
    name="CoRL (Conference on Robot Learning)",
    aliases=("corl",),
    year_known="2025",
    overall_dim=COLM.overall_dim,
    sub_dimensions=COLM.sub_dimensions,
    confidence_dim=COLM.confidence_dim,
    accept_threshold=COLM.accept_threshold,
    verdict_canonical=COLM.verdict_canonical,
    verdict_to_score=COLM.verdict_to_score,
    source_url="https://www.corl.org/",
    confidence="low",
    notes="Uses OpenReview ICLR-style form (inferred).",
)

ICRA = VenueScoring(
    name="ICRA / IROS / RSS",
    aliases=("icra", "iros", "rss"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0: "Definite Accept", 4.0: "Probable Accept",
            3.0: "Borderline", 2.0: "Probable Reject", 1.0: "Definite Reject",
        },
    ),
    sub_dimensions={
        "originality":  ScoreDim(scale=(1.0, 5.0), meanings={}),
        "technical_quality": ScoreDim(scale=(1.0, 5.0), meanings={}),
        "significance": ScoreDim(scale=(1.0, 5.0), meanings={}),
        "presentation": ScoreDim(scale=(1.0, 5.0), meanings={}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"}),
    accept_threshold=4.0,
    verdict_canonical={
        "definite_accept": ["definite accept"], "probable_accept": ["probable accept"],
        "borderline": ["borderline"], "probable_reject": ["probable reject"],
        "definite_reject": ["definite reject", "reject"],
    },
    verdict_to_score={
        "definite_accept": 5.0, "probable_accept": 4.0, "borderline": 3.0,
        "probable_reject": 2.0, "definite_reject": 1.0,
    },
    source_url="https://www.ieee-ras.org/conferences-workshops",
    confidence="low",
    notes="IEEE robotics venues use 1-5 categorical recommendation.",
)

# Speech: INTERSPEECH 1-5, COLM-style.
INTERSPEECH = VenueScoring(
    name="INTERSPEECH",
    aliases=("interspeech",),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0: "Definite Accept", 4.0: "Probable Accept",
            3.0: "Borderline", 2.0: "Probable Reject", 1.0: "Definite Reject",
        },
    ),
    sub_dimensions={
        "scientific_quality": ScoreDim(scale=(1.0, 5.0), meanings={}),
        "novelty":            ScoreDim(scale=(1.0, 5.0), meanings={}),
        "presentation":       ScoreDim(scale=(1.0, 5.0), meanings={}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"}),
    accept_threshold=3.5,
    verdict_canonical={
        "definite_accept": ["definite accept"], "probable_accept": ["probable accept"],
        "borderline": ["borderline"], "probable_reject": ["probable reject"],
        "definite_reject": ["definite reject", "reject"],
    },
    verdict_to_score={
        "definite_accept": 5.0, "probable_accept": 4.0, "borderline": 3.0,
        "probable_reject": 2.0, "definite_reject": 1.0,
    },
    source_url="https://www.isca-archive.org/interspeech_2025/",
    confidence="low",
)

# USENIX/SIGOPS: categorical (no numeric scale; 4 categories).
# Modeled as 1-4 for compatibility with the rest of the pipeline.
OSDI_SOSP = VenueScoring(
    name="OSDI / SOSP / NSDI / EuroSys / ATC",
    aliases=("osdi", "sosp", "nsdi", "eurosys", "atc", "usenix"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 4.0),
        meanings={
            4.0: "Strong Accept",
            3.0: "Weak Accept (revisions needed but viable)",
            2.0: "Weak Reject (significant issues, fixable)",
            1.0: "Strong Reject",
        },
        description="USENIX/SIGOPS reviewers typically vote in categorical 4-tier scheme.",
    ),
    sub_dimensions={
        # USENIX reviews are mostly free-text; we keep one bucket per axis for
        # downstream compatibility but expect models to often leave them empty.
        "novelty":      ScoreDim(scale=(1.0, 4.0), meanings={}),
        "soundness":    ScoreDim(scale=(1.0, 4.0), meanings={}),
        "significance": ScoreDim(scale=(1.0, 4.0), meanings={}),
        "writing":      ScoreDim(scale=(1.0, 4.0), meanings={}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 4.0),
                            meanings={4.0: "Expert", 1.0: "Outsider"}),
    accept_threshold=3.0,
    verdict_canonical={
        "strong_accept": ["strong accept"], "weak_accept": ["weak accept", "accept"],
        "weak_reject":   ["weak reject"], "strong_reject": ["strong reject", "reject"],
    },
    verdict_to_score={
        "strong_accept": 4.0, "weak_accept": 3.0,
        "weak_reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://www.usenix.org/conferences",
    confidence="medium",
    notes="USENIX-family conferences emphasize categorical voting + free-text discussion.",
)

# Theory: COLT / ALT use a small numeric scale.
COLT = VenueScoring(
    name="COLT / ALT (Learning Theory)",
    aliases=("colt", "alt"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 5.0),
        meanings={
            5.0: "Strong Accept", 4.0: "Weak Accept",
            3.0: "Borderline", 2.0: "Weak Reject", 1.0: "Strong Reject",
        },
    ),
    sub_dimensions={
        "technical_quality": ScoreDim(scale=(1.0, 5.0), meanings={}),
        "novelty":           ScoreDim(scale=(1.0, 5.0), meanings={}),
        "significance":      ScoreDim(scale=(1.0, 5.0), meanings={}),
        "clarity":           ScoreDim(scale=(1.0, 5.0), meanings={}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0),
                            meanings={5.0: "Expert", 3.0: "Confident", 1.0: "Outsider"}),
    accept_threshold=4.0,
    verdict_canonical={
        "strong_accept": ["strong accept"], "weak_accept": ["weak accept"],
        "borderline": ["borderline"], "weak_reject": ["weak reject"], "strong_reject": ["strong reject", "reject"],
    },
    verdict_to_score={
        "strong_accept": 5.0, "weak_accept": 4.0, "borderline": 3.0,
        "weak_reject": 2.0, "strong_reject": 1.0,
    },
    source_url="https://learningtheory.org/colt2025/",
    confidence="low",
)

# Journals: TPAMI / JMLR / TMLR — categorical decisions, not numeric.
# Modeled as 1-4 for compatibility.
JOURNAL = VenueScoring(
    name="TPAMI / JMLR / TMLR (Journals)",
    aliases=("tpami", "jmlr", "tmlr", "tacl", "journal"),
    year_known="2025",
    overall_dim=ScoreDim(
        scale=(1.0, 4.0),
        meanings={
            4.0: "Accept (no revisions / minor revisions)",
            3.0: "Accept with Minor Revisions",
            2.0: "Major Revisions",
            1.0: "Reject",
        },
        description="Journals use categorical decisions, not numeric scoring.",
    ),
    sub_dimensions={
        "soundness":    ScoreDim(scale=(1.0, 4.0), meanings={}),
        "novelty":      ScoreDim(scale=(1.0, 4.0), meanings={}),
        "significance": ScoreDim(scale=(1.0, 4.0), meanings={}),
        "clarity":      ScoreDim(scale=(1.0, 4.0), meanings={}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 4.0),
                            meanings={4.0: "Expert", 1.0: "Outsider"}),
    accept_threshold=3.0,
    verdict_canonical={
        "accept":          ["accept", "minor revisions"],
        "minor_revisions": ["minor revision"],
        "major_revisions": ["major revision"],
        "reject":          ["reject"],
    },
    verdict_to_score={"accept": 4.0, "minor_revisions": 3.0,
                      "major_revisions": 2.0, "reject": 1.0},
    source_url="",
    confidence="medium",
    notes="Journals (TPAMI, JMLR, TMLR, TACL) use categorical Accept/Minor/Major/Reject.",
)


# Generic fallback for unknown venues — neutral 1-10 scale, no verdict mapping.
GENERIC = VenueScoring(
    name="Generic Conference",
    aliases=("_default", "generic", "unknown"),
    year_known="2026",
    overall_dim=ScoreDim(
        scale=(1.0, 10.0),
        meanings={
            10.0: "Outstanding", 8.0: "Strong accept", 6.0: "Accept",
            5.0:  "Borderline", 4.0:  "Weak reject", 2.0: "Reject", 1.0: "Strong reject",
        },
        description="Generic 1-10 scale used when venue is unknown.",
    ),
    sub_dimensions={
        "soundness":     ScoreDim(scale=(1.0, 5.0), meanings={}),
        "novelty":       ScoreDim(scale=(1.0, 5.0), meanings={}),
        "clarity":       ScoreDim(scale=(1.0, 5.0), meanings={}),
        "significance":  ScoreDim(scale=(1.0, 5.0), meanings={}),
    },
    confidence_dim=ScoreDim(scale=(1.0, 5.0), meanings={}),
    accept_threshold=6.0,
    confidence="low",
    notes="Fallback when venue is unknown. Check if your venue should be added to the spec.",
)


# ---------------------------------------------------------------------------
# Registry + lookup
# ---------------------------------------------------------------------------

_VENUE_REGISTRY: dict[str, VenueScoring] = {}

def _register(spec: VenueScoring) -> None:
    for alias in spec.aliases:
        _VENUE_REGISTRY[alias.lower()] = spec

for spec in [
    # NLP
    ARR, COLM, COLING,
    # ML general
    NEURIPS, ICLR, ICML, AISTATS, UAI, AAAI, IJCAI,
    # CV / Multimedia
    CVPR, BMVC, ACCV, ACM_MM, MM_ASIA,
    # Speech
    INTERSPEECH,
    # Data mining / web
    KDD, WWW,
    # Robotics
    CORL, ICRA,
    # Systems
    OSDI_SOSP, MLSYS,
    # Theory
    COLT,
    # Journals
    JOURNAL,
    # Fallback
    GENERIC,
]:
    _register(spec)


def get_venue_spec(venue: str) -> VenueScoring:
    """Look up a venue spec, accepting aliases case-insensitively.

    Falls back to GENERIC if the venue is unknown.
    """
    if not venue:
        return GENERIC
    key = venue.strip().lower()
    if key in _VENUE_REGISTRY:
        return _VENUE_REGISTRY[key]
    # Try stripping years / suffixes: "ICLR 2026" → "iclr"
    parts = key.split()
    if parts and parts[0] in _VENUE_REGISTRY:
        return _VENUE_REGISTRY[parts[0]]
    return GENERIC


def list_known_venues() -> list[str]:
    """Return the list of canonical venue names registered."""
    seen = set()
    out = []
    for spec in _VENUE_REGISTRY.values():
        if spec.name not in seen:
            seen.add(spec.name)
            out.append(spec.name)
    return out


# ---------------------------------------------------------------------------
# Helpers used by downstream stages
# ---------------------------------------------------------------------------

def render_criteria_text(spec: VenueScoring) -> str:
    """Render a venue spec into the text used as `venue_criteria` in prompts.

    Replaces lookup_venue_criteria (which used to call the LLM)."""
    lines = [
        f"VENUE: {spec.name}",
        f"YEAR: {spec.year_known}",
        f"",
        f"OVERALL ASSESSMENT:",
        f"  Scale: {spec.overall_dim.scale[0]}-{spec.overall_dim.scale[1]}",
    ]
    for val in sorted(spec.overall_dim.meanings.keys(), reverse=True):
        lines.append(f"  {val}: {spec.overall_dim.meanings[val]}")
    lines.append("")

    if spec.sub_dimensions:
        lines.append("SUB-DIMENSIONS:")
        for dname, dim in spec.sub_dimensions.items():
            opt = " (optional)" if dim.optional else ""
            lines.append(f"  {dname}{opt}:")
            lines.append(f"    Scale: {dim.scale[0]}-{dim.scale[1]}")
            for val in sorted(dim.meanings.keys(), reverse=True):
                lines.append(f"    {val}: {dim.meanings[val]}")
        lines.append("")

    if spec.confidence_dim:
        lines.append("CONFIDENCE:")
        lines.append(f"  Scale: {spec.confidence_dim.scale[0]}-{spec.confidence_dim.scale[1]}")
        for val in sorted(spec.confidence_dim.meanings.keys(), reverse=True):
            lines.append(f"  {val}: {spec.confidence_dim.meanings[val]}")
        lines.append("")

    lines.append("ACCEPTANCE THRESHOLD:")
    lines.append(f"  Main: overall >= {spec.accept_threshold}")
    if spec.secondary_threshold is not None:
        lines.append(
            f"  {spec.secondary_track_name or 'Secondary'}: "
            f"overall >= {spec.secondary_threshold}"
        )
    lines.append("")

    if spec.notes:
        lines.append(f"NOTES: {spec.notes}")
    if spec.confidence != "high":
        lines.append(f"SPEC CONFIDENCE: {spec.confidence}")
        if spec.source_url:
            lines.append(f"  (Verify against {spec.source_url})")

    return "\n".join(lines)


def build_review_schema(spec: VenueScoring,
                        require_strengths_weaknesses: bool = True) -> dict:
    """Build a JSON schema for a single reviewer's submission to this venue.

    Used by review_paper / review_paper_grounded with call_with_schema.
    Score field is constrained to the venue's exact scale.
    """
    s_min, s_max = spec.overall_dim.scale
    sub_props = {}
    for dname, dim in spec.sub_dimensions.items():
        d_min, d_max = dim.scale
        meaning_str = "; ".join(
            f"{v}={spec.sub_dimensions[dname].meanings.get(v, '')}"
            for v in sorted(dim.meanings.keys(), reverse=True)
        )
        sub_props[dname] = {
            "type": "number",
            "minimum": d_min,
            "maximum": d_max,
            "description": (
                f"{dim.description} Scale {d_min}-{d_max}. "
                + (f"({meaning_str})" if meaning_str else "")
            ),
        }

    overall_meaning_str = "; ".join(
        f"{v}={spec.overall_dim.meanings.get(v, '')}"
        for v in sorted(spec.overall_dim.meanings.keys(), reverse=True)
    )
    schema_props = {
        "score": {
            "type": "number",
            "minimum": s_min,
            "maximum": s_max,
            "description": (
                f"Overall recommendation on {spec.name}'s {s_min}-{s_max} scale. "
                f"({overall_meaning_str})"
            ),
        },
        "verdict": {
            "type": "string",
            "description": (
                f"One-line decision label using {spec.name}'s vocabulary "
                f"(e.g. for ARR: 'Conference acceptance' / 'Findings' / 'Resubmit')."
            ),
        },
        "weaknesses": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific weaknesses, ranked by severity (critical first).",
        },
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific strengths.",
        },
    }
    if sub_props:
        schema_props["sub_scores"] = {
            "type": "object",
            "properties": sub_props,
            "required": list(sub_props.keys()),
            "description": f"Per-dimension scores on {spec.name}'s sub-scales.",
        }
    if spec.confidence_dim:
        c_min, c_max = spec.confidence_dim.scale
        schema_props["confidence"] = {
            "type": "number",
            "minimum": c_min,
            "maximum": c_max,
            "description": f"Reviewer self-confidence on {c_min}-{c_max} scale.",
        }

    required = ["score", "verdict", "weaknesses", "strengths"]
    if require_strengths_weaknesses and "sub_scores" in schema_props:
        required.append("sub_scores")

    return {
        "type": "object",
        "properties": schema_props,
        "required": required,
    }


def build_meta_review_schema(spec: VenueScoring) -> dict:
    """Same as build_review_schema but for AC meta-review.

    Adds fields specific to meta-review: passed (bool), individual_scores (list).
    """
    schema = build_review_schema(spec, require_strengths_weaknesses=False)
    schema["properties"]["passed"] = {
        "type": "boolean",
        "description": (
            f"True if the score meets {spec.name}'s acceptance threshold "
            f"(>= {spec.accept_threshold})."
        ),
    }
    schema["properties"]["individual_scores"] = {
        "type": "array",
        "items": {"type": "number"},
        "description": "Per-reviewer scores in the order they were provided.",
    }
    schema["required"] = ["score", "verdict", "weaknesses", "strengths", "passed"]
    return schema


def map_verdict_to_score(spec: VenueScoring, verdict_text: str) -> Optional[float]:
    """Map a free-text verdict to a numeric score using the venue's vocabulary.

    Returns None if no keyword matches.
    """
    if not verdict_text:
        return None
    v = verdict_text.lower()

    # Iterate verdict_canonical in insertion order (Python 3.7+ dicts are ordered);
    # spec authors should list most-specific decisions first.
    for canonical, keywords in spec.verdict_canonical.items():
        for kw in keywords:
            if kw.lower() in v:
                return spec.verdict_to_score.get(canonical)
    return None
