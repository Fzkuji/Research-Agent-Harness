"""Tests for the review-loop upgrades (ARS-derived mechanisms):

1. Concession-threshold debate rulings (withdraw only at 5, downgrade at 4,
   5-only bar after any concession) — parsed and APPLIED to the review.
2. Score trajectory: per-dimension deltas + REGRESSION flags.
3. Commitment ledger: plan items parsed deterministically, audited next
   round, unaddressed items carried forward verbatim.

All LLM interactions use MockRuntime with scripted replies — no network.
"""

import json

from tests.conftest import MockRuntime

from research_harness.stages.review import (
    _apply_debate_rulings,
    _audit_commitments,
    _carry_from_audit,
    _carry_section,
    _commitment_audit_table,
    _enforce_concession_policy,
    _parse_debate_rulings,
    _parse_plan_commitments,
    _regression_warning,
    _run_debate,
    _score_trajectory,
    _trajectory_table,
)


# ── 1. Concession threshold ──────────────────────────────────────────

class TestConcessionParsing:

    def test_parse_rulings_from_prose_plus_json(self):
        reply = (
            "Rebuttal 1 brings new ablation data, decisive.\n"
            "Rebuttal 2 is just persistence.\n\n"
            '{"rulings": [\n'
            ' {"weakness_index": 1, "rebuttal_score": 5, "action": "WITHDRAWN", "reason": "new ablation"},\n'
            ' {"weakness_index": "2", "rebuttal_score": 9, "action": "sustained", "reason": "no evidence"}\n'
            "]}"
        )
        rulings = _parse_debate_rulings(reply)
        assert len(rulings) == 2
        assert rulings[0]["weakness_index"] == 1
        assert rulings[0]["action"] == "WITHDRAWN"
        # string index coerced, out-of-range score clamped to 5, action upper
        assert rulings[1]["weakness_index"] == 2
        assert rulings[1]["rebuttal_score"] == 5
        assert rulings[1]["action"] == "SUSTAINED"

    def test_parse_rulings_garbage_returns_empty(self):
        assert _parse_debate_rulings("no json here at all") == []
        assert _parse_debate_rulings('{"rulings": "oops"}') == []

    def test_withdraw_requires_score_5(self):
        rulings = _enforce_concession_policy([
            {"weakness_index": 1, "rebuttal_score": 4,
             "action": "WITHDRAWN", "reason": ""},
            {"weakness_index": 2, "rebuttal_score": 3,
             "action": "WITHDRAWN", "reason": ""},
        ])
        # score-4 withdrawal demoted to downgrade; score-3 → sustained
        assert rulings[0]["action"] == "DOWNGRADED"
        assert rulings[0]["enforced"] is True
        assert rulings[1]["action"] == "SUSTAINED"

    def test_no_consecutive_concessions_bar_rises_to_5(self):
        rulings = _enforce_concession_policy([
            {"weakness_index": 1, "rebuttal_score": 5,
             "action": "WITHDRAWN", "reason": ""},
            # after a concession, a score-4 downgrade is no longer allowed
            {"weakness_index": 2, "rebuttal_score": 4,
             "action": "DOWNGRADED", "reason": ""},
            # but a score-5 withdrawal still meets the raised bar
            {"weakness_index": 3, "rebuttal_score": 5,
             "action": "WITHDRAWN", "reason": ""},
        ])
        assert rulings[0]["action"] == "WITHDRAWN"
        assert rulings[1]["action"] == "SUSTAINED"
        assert rulings[1]["enforced"] is True
        assert rulings[2]["action"] == "WITHDRAWN"

    def test_policy_never_escalates_sustained(self):
        rulings = _enforce_concession_policy([
            {"weakness_index": 1, "rebuttal_score": 5,
             "action": "SUSTAINED", "reason": "reviewer held firm"},
        ])
        assert rulings[0]["action"] == "SUSTAINED"

    def test_apply_rulings_drops_withdrawn_and_adjusts_score(self):
        review = {
            "score": 4.0,
            "weaknesses": ["w1 missing baseline", "w2 unclear proof",
                           "w3 overclaim", "w4 typo storm"],
        }
        rulings = [
            {"weakness_index": 1, "rebuttal_score": 5,
             "action": "WITHDRAWN", "reason": ""},
            {"weakness_index": 3, "rebuttal_score": 4,
             "action": "DOWNGRADED", "reason": ""},
        ]
        adj = _apply_debate_rulings(review, rulings, scale_max=10.0)
        assert review["weaknesses"][0] == "w2 unclear proof"
        assert any(w.startswith("[severity downgraded after rebuttal]")
                   for w in review["weaknesses"])
        assert len(review["weaknesses"]) == 3
        # proportional: 4 + (10 - 4) * (1/4) = 5.5
        assert review["score"] == 5.5
        assert review["pre_debate_score"] == 4.0
        assert adj["withdrawn"] == 1
        assert adj["downgraded"] == 1

    def test_apply_rulings_no_withdrawals_keeps_score(self):
        review = {"score": 3.0, "weaknesses": ["w1", "w2"]}
        rulings = [{"weakness_index": 1, "rebuttal_score": 4,
                    "action": "DOWNGRADED", "reason": ""}]
        _apply_debate_rulings(review, rulings, scale_max=10.0)
        assert review["score"] == 3.0
        assert "pre_debate_score" not in review

    def test_run_debate_end_to_end_with_mock_runtimes(self):
        exec_rt = MockRuntime("### Rebuttal to Weakness #1\nWe added Table 5.")
        review_rt = MockRuntime(
            "Ruling prose.\n"
            '{"rulings": [{"weakness_index": 1, "rebuttal_score": 5, '
            '"action": "WITHDRAWN", "reason": "table added"}]}'
        )
        result = _run_debate(
            ["missing baseline", "weak novelty"], "paper text",
            exec_rt, review_rt, return_rulings=True,
        )
        assert "Rebuttal to Weakness #1" in result["transcript"]
        assert result["rulings"][0]["action"] == "WITHDRAWN"
        # numbered weakness list reached both models
        assert "1. missing baseline" in exec_rt.calls[0]["content"][0]["text"]
        assert "1. missing baseline" in review_rt.calls[0]["content"][0]["text"]

    def test_run_debate_default_returns_transcript_string(self):
        exec_rt = MockRuntime("rebuttal")
        review_rt = MockRuntime("ruling, no json")
        out = _run_debate(["w1"], "paper", exec_rt, review_rt)
        assert isinstance(out, str)
        assert "Reviewer's Ruling" in out


# ── 2. Score trajectory ──────────────────────────────────────────────

class TestScoreTrajectory:

    def test_needs_two_rounds(self):
        assert _score_trajectory([{"score": 5, "round": 1}]) is None
        assert _score_trajectory([]) is None

    def test_deltas_and_regression_default_threshold(self):
        reviews = [
            {"round": 1, "score": 6,
             "sub_scores": {"soundness": 4, "clarity": 3}},
            {"round": 2, "score": 5,
             "sub_scores": {"soundness": 2, "clarity": 4}},
        ]
        traj = _score_trajectory(reviews)
        rows = {r["dimension"]: r for r in traj["rows"]}
        assert rows["soundness"]["delta"] == -2
        assert rows["soundness"]["flag"] == "REGRESSION"
        assert rows["clarity"]["delta"] == 1
        assert rows["clarity"]["flag"] == "improved"
        assert rows["overall"]["delta"] == -1
        assert rows["overall"]["flag"] == "warn"
        assert traj["regressions"] == ["soundness"]

    def test_venue_scale_threshold_25_percent(self):
        reviews = [
            {"round": 1, "score": 5.0, "sub_scores": {"soundness": 3.5}},
            {"round": 2, "score": 5.0, "sub_scores": {"soundness": 2.0}},
        ]
        # NeurIPS-style 1-6 scale → threshold = 0.25 * 5 = 1.25; -1.5 trips it
        traj = _score_trajectory(reviews, scale_range=(1.0, 6.0))
        assert traj["threshold"] == 1.25
        assert traj["regressions"] == ["soundness"]
        # same drop on the default absolute-2 threshold is only a warning
        traj2 = _score_trajectory(reviews)
        assert traj2["regressions"] == []
        rows2 = {r["dimension"]: r for r in traj2["rows"]}
        assert rows2["soundness"]["flag"] == "warn"

    def test_missing_dimension_flagged_na(self):
        reviews = [
            {"round": 1, "score": 5, "sub_scores": {"soundness": 3}},
            {"round": 2, "score": 5, "sub_scores": {"novelty": 2}},
        ]
        traj = _score_trajectory(reviews)
        rows = {r["dimension"]: r for r in traj["rows"]}
        assert rows["soundness"]["flag"] == "n/a"
        assert rows["novelty"]["flag"] == "n/a"

    def test_table_and_warning_render(self):
        reviews = [
            {"round": 1, "score": 6, "sub_scores": {"soundness": 4}},
            {"round": 2, "score": 6, "sub_scores": {"soundness": 1}},
        ]
        traj = _score_trajectory(reviews)
        table = _trajectory_table(traj)
        assert table.startswith("## Score trajectory")
        assert "| soundness | 4 | 1 | -3 | REGRESSION |" in table
        warning = _regression_warning(traj)
        assert "REGRESSION WARNING" in warning
        assert "soundness" in warning
        # no regression → no warning text
        assert _regression_warning(
            {"regressions": [], "rows": []}) == ""


# ── 3. Commitment ledger ─────────────────────────────────────────────

SAMPLE_PLAN = """# Revision Plan — Round 1

## Summary
- **Current score**: 4/1-10
- **Action items in scope**: 1 CRITICAL + 1 MAJOR + 0 MINOR

## Action Items

### [CRITICAL-1] Missing baseline comparison
- **Problem**: No comparison against the standard baseline X.
- **Source**: R1, AC
- **Location**: Section 4, Table 2
- **Fix action**: Add baseline X results to Table 2 with the same metrics.
- **Expected impact**: Soundness +1
- **Effort**: medium

### [MAJOR-2] Overclaimed generality
- **Problem**: Claims exceed the evidence.
- **Source**: R2
- **Location**: Abstract, Section 1
- **Fix action**: Soften the generality claims in the abstract and Section 1.
- **Effort**: trivial

## Sequencing
Recommended execution order for fix agent:
1. CRITICAL-1
2. MAJOR-2
"""


class TestCommitmentParsing:

    def test_parse_action_blocks(self):
        commitments = _parse_plan_commitments(SAMPLE_PLAN)
        assert [c["id"] for c in commitments] == ["CRITICAL-1", "MAJOR-2"]
        assert commitments[0]["title"] == "Missing baseline comparison"
        assert commitments[0]["fix_action"].startswith("Add baseline X")
        assert commitments[0]["severity"] == "critical"
        assert commitments[1]["severity"] == "major"
        # the Sequencing list's bare ids must not become extra commitments
        assert len(commitments) == 2

    def test_numbered_fallback_for_freeform_plans(self):
        plan = (
            "Fix list:\n"
            "1. Add the ablation table for the encoder depth sweep.\n"
            "2. CRITICAL-9\n"
            "3. Fix the notation clash in Section 3.\n"
        )
        commitments = _parse_plan_commitments(plan)
        assert len(commitments) == 2
        assert commitments[0]["id"] == "ITEM-1"
        assert "ablation table" in commitments[0]["title"]
        assert all("CRITICAL-9" != c["title"] for c in commitments)

    def test_empty_plan(self):
        assert _parse_plan_commitments("no items here") == []


class TestCommitmentAudit:

    def _commitments(self, n=3):
        return [
            {"id": f"CRITICAL-{i}", "round": 1,
             "title": f"issue {i}", "fix_action": f"do thing {i}",
             "severity": "critical"}
            for i in range(1, n + 1)
        ]

    def test_audit_statuses_parsed_and_aligned(self):
        rt = MockRuntime(json.dumps({"audit": [
            {"id": "CRITICAL-1", "status": "FULLY_ADDRESSED",
             "evidence": "Table 2 now has baseline X"},
            {"id": "CRITICAL-2", "status": "not addressed",
             "evidence": "no change found"},
            {"id": "CRITICAL-3", "status": "MADE_WORSE",
             "evidence": "new claim contradicts Section 3"},
        ]}))
        audit = _audit_commitments(self._commitments(3), "paper text", rt)
        assert [a["status"] for a in audit] == [
            "FULLY_ADDRESSED", "NOT_ADDRESSED", "MADE_WORSE"]
        assert audit[0]["title"] == "issue 1"
        # one exec on the review runtime, fed both commitments and paper
        assert len(rt.calls) == 1
        prompt = rt.calls[0]["content"][0]["text"]
        assert "CRITICAL-2" in prompt and "Current paper" in prompt

    def test_unparseable_reply_marks_unverified(self):
        rt = MockRuntime("I refuse to emit JSON today.")
        audit = _audit_commitments(self._commitments(2), "paper", rt)
        assert [a["status"] for a in audit] == ["UNVERIFIED", "UNVERIFIED"]

    def test_feed_capped_at_15_most_recent(self):
        commitments = [
            {"id": f"ITEM-{i}", "round": 1, "title": f"t{i}",
             "fix_action": f"f{i}", "severity": "unknown"}
            for i in range(1, 21)
        ]
        rt = MockRuntime(json.dumps({"audit": []}))
        audit = _audit_commitments(commitments, "paper", rt)
        assert len(audit) == 15
        assert audit[0]["id"] == "ITEM-6"
        prompt = rt.calls[0]["content"][0]["text"]
        assert '"ITEM-6"' in prompt
        assert '"ITEM-5"' not in prompt

    def test_carry_feeds_unaddressed_items_forward(self):
        commitments = self._commitments(4)
        audit = [
            {"id": "CRITICAL-1", "status": "FULLY_ADDRESSED", "evidence": ""},
            {"id": "CRITICAL-2", "status": "NOT_ADDRESSED", "evidence": ""},
            {"id": "CRITICAL-3", "status": "MADE_WORSE", "evidence": ""},
            {"id": "CRITICAL-4", "status": "UNVERIFIED", "evidence": ""},
        ]
        carry = _carry_from_audit(audit, commitments)
        assert [c["id"] for c in carry] == [
            "CRITICAL-2", "CRITICAL-3", "CRITICAL-4"]
        section = _carry_section(carry)
        # carried items appear verbatim (title + fix action), addressed don't
        assert "Unresolved commitments" in section
        assert "issue 2" in section and "do thing 2" in section
        assert "MADE_WORSE" in section
        assert "issue 1" not in section
        # table renders every audited commitment with its status
        table = _commitment_audit_table(audit, round_num=2)
        assert "## Commitment audit (round 2)" in table
        assert "| CRITICAL-2 |" in table and "NOT_ADDRESSED" in table

    def test_carry_section_empty_when_nothing_to_carry(self):
        assert _carry_section([]) == ""
