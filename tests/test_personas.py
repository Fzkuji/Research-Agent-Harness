"""Tests for the ARS-enriched reviewer persona pool.

Covers:
1. Pool integrity — every persona is a non-empty string, DEFAULT_PERSONAS
   all resolve, the "balanced" fallback key exists.
2. New ARS-derived personas present (methodologist / statistician /
   reproducibility_auditor / devils_advocate).
3. Signature checks per persona — each persona text mentions the concrete
   checks distilled from the ARS reviewer agents.
4. Harness-flow compatibility — every non-balanced persona keeps the
   "80% of your weaknesses" focus-bias pattern (personas bias WHERE
   weaknesses focus; they do not change the output schema).
5. Prompt-builder path — _build_structured_instructions is a pure string
   builder; a new persona's block renders into the stage-2 prompt.

No LLM / network / MockRuntime needed.
"""

from research_harness.stages.review import DEFAULT_PERSONAS
from research_harness.stages.review.review_paper_grounded import (
    _PERSONA_INSTRUCTIONS,
    _build_structured_instructions,
)


# ── 1. Pool integrity ────────────────────────────────────────────────

class TestPoolIntegrity:

    def test_every_persona_is_nonempty_string(self):
        assert _PERSONA_INSTRUCTIONS, "persona pool must not be empty"
        for name, text in _PERSONA_INSTRUCTIONS.items():
            assert isinstance(name, str) and name
            assert isinstance(text, str)
            assert text.strip(), f"persona {name!r} has empty instructions"

    def test_all_default_personas_exist_in_pool(self):
        assert len(DEFAULT_PERSONAS) == 4  # cost: 4 reviewers per round
        for p in DEFAULT_PERSONAS:
            assert p in _PERSONA_INSTRUCTIONS, (
                f"DEFAULT_PERSONAS entry {p!r} missing from pool")

    def test_balanced_fallback_key_exists(self):
        # review_paper_grounded falls back to "balanced" for unknown names
        assert "balanced" in _PERSONA_INSTRUCTIONS

    def test_original_five_personas_still_present(self):
        for p in ("balanced", "empiricist", "theorist", "novelty_hawk",
                  "clarity_critic"):
            assert p in _PERSONA_INSTRUCTIONS


# ── 2. New ARS-derived personas ──────────────────────────────────────

class TestNewPersonas:

    def test_new_personas_present(self):
        for p in ("methodologist", "statistician",
                  "reproducibility_auditor", "devils_advocate"):
            assert p in _PERSONA_INSTRUCTIONS, f"missing new persona {p!r}"

    def test_default_pool_includes_devils_advocate(self):
        assert "devils_advocate" in DEFAULT_PERSONAS


# ── 3. Signature checks per persona ──────────────────────────────────

class TestPersonaSignatures:
    """Each persona must carry its ARS-distilled concrete checks."""

    def _text(self, persona):
        return _PERSONA_INSTRUCTIONS[persona].lower()

    def test_empiricist_checks(self):
        text = self._text("empiricist")
        for kw in ("baseline", "ablation", "seed", "leakage",
                   "significance"):
            assert kw in text, f"empiricist missing {kw!r}"

    def test_theorist_checks(self):
        text = self._text("theorist")
        for kw in ("notation", "assumption", "circular reasoning",
                   "complexity"):
            assert kw in text, f"theorist missing {kw!r}"

    def test_novelty_hawk_checks(self):
        text = self._text("novelty_hawk")
        for kw in ("prior_work_context", "missing citation", "seminal",
                   "3-5 years", "overclaiming"):
            assert kw in text, f"novelty_hawk missing {kw!r}"

    def test_clarity_critic_checks(self):
        text = self._text("clarity_critic")
        for kw in ("abstract", "notation", "figures", "pseudocode"):
            assert kw in text, f"clarity_critic missing {kw!r}"

    def test_methodologist_checks(self):
        # ARS methodology_reviewer_agent.md: power/sample size, leakage,
        # baseline fairness, seed/variance reporting, fallacy checklist.
        text = self._text("methodologist")
        for kw in ("power", "sample", "leakage", "baseline fairness",
                   "seeds and variance", "p-hacking", "survivorship"):
            assert kw in text, f"methodologist missing {kw!r}"

    def test_statistician_checks(self):
        # ARS Step 4a + statistical_reporting_standards.md: test choice,
        # multiple comparisons, CI vs p-value, effect size.
        text = self._text("statistician")
        for kw in ("effect size", "confidence interval", "p-value",
                   "multiple comparisons", "bonferroni", "power analysis"):
            assert kw in text, f"statistician missing {kw!r}"

    def test_reproducibility_auditor_checks(self):
        # ARS Step 6: could it be re-run from the paper alone.
        text = self._text("reproducibility_auditor")
        for kw in ("re-run", "hyperparameter", "seed", "splits",
                   "code and data"):
            assert kw in text, f"reproducibility_auditor missing {kw!r}"

    def test_devils_advocate_checks(self):
        # ARS devils_advocate_reviewer_agent.md: steelman-then-attack,
        # attack-surface list, 'author persistence is not evidence'
        # (consistent with the concession-threshold debate protocol).
        text = self._text("devils_advocate")
        for kw in ("steelman", "counter-argument", "foundation collapse",
                   "logic chain break", "data-conclusion mismatch",
                   "persistence is not evidence"):
            assert kw in text, f"devils_advocate missing {kw!r}"


# ── 4. Harness-flow compatibility ────────────────────────────────────

class TestFlowCompatibility:

    def test_focus_bias_pattern_in_all_non_balanced_personas(self):
        # Personas bias WHERE weaknesses focus; the harness relies on the
        # "80% of your weaknesses" pattern rather than schema changes.
        for name, text in _PERSONA_INSTRUCTIONS.items():
            if name == "balanced":
                assert "80%" not in text
                continue
            assert "80% of your weaknesses" in text, (
                f"persona {name!r} lost the focus-bias pattern")

    def test_personas_reasonably_sized(self):
        # Distilled, not pasted walls of ARS text (~25 lines max each).
        for name, text in _PERSONA_INSTRUCTIONS.items():
            assert len(text) < 2200, f"persona {name!r} too long"


# ── 5. Prompt-builder path for a new persona ─────────────────────────

class TestPromptBuilder:

    def test_build_instructions_renders_new_persona_block(self):
        persona_instr = _PERSONA_INSTRUCTIONS["devils_advocate"]
        persona_block = f"## Persona\n{persona_instr}\n\n"
        prompt = _build_structured_instructions(
            venue_name="NeurIPS",
            venue_criteria="Soundness, novelty, clarity.",
            paper_content="PAPER BODY HERE",
            review_text={"review": "long prose review",
                         "weaknesses": ["w1", "w2"]},
            persona_block=persona_block,
            grounding_section="## Prior work context\n[1] Foo et al.\n\n",
        )
        assert isinstance(prompt, str)
        # persona text injected verbatim
        assert "## Persona" in prompt
        assert "steelman first, then attack" in prompt
        # stage-1 free-text fields rendered for context
        assert "Already-written `review`" in prompt
        assert "- w1" in prompt
        # core scaffolding intact (schema unchanged by persona)
        assert "submit_review" in prompt
        assert "NeurIPS" in prompt
        assert "PAPER BODY HERE" in prompt
        assert "[1] Foo et al." in prompt

    def test_build_instructions_works_for_every_pool_persona(self):
        for name, instr in _PERSONA_INSTRUCTIONS.items():
            prompt = _build_structured_instructions(
                venue_name="ICML",
                venue_criteria="criteria",
                paper_content="paper",
                review_text={"review": "text"},
                persona_block=f"## Persona\n{instr}\n\n",
                grounding_section="",
            )
            # First sentence fragment of the persona must reach the prompt.
            assert instr[:40] in prompt, f"persona {name!r} not injected"
