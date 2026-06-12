"""Tests for research_harness.writing_lint — deterministic LaTeX lints.

No LLM, no network: both checks are pure-stdlib text analysis.
"""

from research_harness.writing_lint import (
    check_citations,
    check_tex,
    citation_context_check,
    uncited_assertion_check,
)


# ---------------------------------------------------------------------------
# uncited assertions (check_tex)
# ---------------------------------------------------------------------------

def test_quantified_claim_without_cite_fires():
    findings = check_tex(
        r"Our method improves accuracy by 4.2\% over the strongest baseline."
    )
    assert len(findings) == 1
    assert findings[0]["line"] == 1
    assert "4.2%" in findings[0]["reason"]


def test_same_claim_with_citep_passes():
    assert check_tex(
        r"Prior work improves accuracy by 4.2\% over the baseline"
        r" \citep{smith2020}."
    ) == []
    assert check_tex(
        r"Prior work improves accuracy by 4.2\% \cite{smith2020}."
    ) == []
    assert check_tex(
        r"\citet{smith2020} showed a 4.2\% gain over the baseline."
    ) == []


def test_claim_with_own_table_reference_passes():
    # Textual "Table N" reference — the number has a source.
    assert check_tex(
        r"As shown in Table~2, our method improves accuracy by 4.2\%."
    ) == []
    # \ref{tab:...} form.
    assert check_tex(
        r"Our method outperforms all baselines (Table~\ref{tab:main})."
    ) == []
    # \ref{fig:...} form.
    assert check_tex(
        r"Accuracy improves by 12\% as depicted in Figure~\ref{fig:curve}."
    ) == []


def test_math_and_comments_do_not_false_positive():
    tex = "\n".join([
        r"% 90% of comments lie about numbers like 42",
        r"The loss balances both terms.",
        r"\begin{equation}",
        r"\alpha = 0.5 + 42",
        r"\end{equation}",
        r"The weight $\lambda = 17$ controls the tradeoff.",
    ])
    assert check_tex(tex) == []


def test_definitional_sentence_passes():
    assert check_tex(
        "Perplexity is defined as the exponentiated average negative"
        " log-likelihood over 100 tokens."
    ) == []


def test_empirical_verb_without_cite_fires():
    findings = check_tex(
        "Earlier studies showed that augmentation hurts calibration."
    )
    assert len(findings) == 1
    assert "showed" in findings[0]["reason"]


def test_year_version_and_identifier_numbers_do_not_fire():
    assert check_tex("The dataset was released in 2019 under an"
                     " open license.") == []
    assert check_tex("We follow the protocol from Section 3.2 of the"
                     " appendix.") == []
    assert check_tex("All models are evaluated on the CIFAR-10 benchmark"
                     " in this work.") == []


def test_check_tex_accepts_path_and_reports_line(tmp_path):
    tex = tmp_path / "sec.tex"
    tex.write_text(
        "\\section{Results}\n"
        "All baselines are reproduced from public code.\n"
        "Our approach outperforms the previous state of the art.\n",
        encoding="utf-8",
    )
    findings = check_tex(str(tex))
    assert len(findings) == 1
    assert findings[0]["line"] == 3
    assert "outperforms" in findings[0]["reason"]


def test_uncited_assertion_check_writes_report(tmp_path):
    (tmp_path / "main.tex").write_text(
        "Our model outperforms the baseline by 12\\% on every benchmark.\n"
        "The encoder follows standard practice.\n",
        encoding="utf-8",
    )
    summary = uncited_assertion_check(str(tmp_path))
    report = tmp_path / "uncited_assertions_report.md"
    assert report.exists()
    assert str(report) in summary
    assert "1 uncited" in summary
    body = report.read_text(encoding="utf-8")
    assert "main.tex" in body
    assert "12%" in body


def test_uncited_assertion_check_bad_path():
    assert uncited_assertion_check("/nonexistent/nowhere").startswith("ERROR")


# ---------------------------------------------------------------------------
# citation context (check_citations)
# ---------------------------------------------------------------------------

def test_citet_misuse_flagged():
    findings = check_citations(
        r"\citep{vaswani2017} proposed the transformer architecture for"
        r" sequence transduction."
    )
    assert len(findings) == 1
    assert "citet" in findings[0]["reason"]


def test_citet_used_correctly_passes():
    assert check_citations(
        r"\citet{vaswani2017} proposed the transformer architecture for"
        r" sequence transduction."
    ) == []


def test_bare_citation_dump_flagged():
    findings = check_citations(
        r"Many prior works have studied this problem"
        r" \citep{a,b,c,d,e}."
    )
    assert len(findings) == 1
    assert "dump" in findings[0]["reason"]


def test_small_citation_group_passes():
    assert check_citations(
        r"Many prior works have studied this problem \citep{a,b,c}."
    ) == []


def test_dump_with_enumeration_cue_passes():
    assert check_citations(
        r"Many approaches, e.g., \citep{a,b,c,d,e}, have studied this"
        r" problem in depth."
    ) == []


def test_cargo_cult_citation_flagged():
    findings = check_citations(r"This was proved \citep{tao2019}.")
    assert len(findings) == 1
    assert "cargo-cult" in findings[0]["reason"]


def test_substantive_strong_claim_passes():
    assert check_citations(
        r"\citet{tao2019} proved that the iterates converge linearly"
        r" under strong convexity assumptions."
    ) == []


def test_citation_context_check_writes_report(tmp_path):
    (tmp_path / "related.tex").write_text(
        "\\citep{kim2021} proposed a contrastive objective.\n",
        encoding="utf-8",
    )
    (tmp_path / "clean.tex").write_text(
        "\\citet{lee2022} proposed a simpler decoding scheme.\n",
        encoding="utf-8",
    )
    summary = citation_context_check(str(tmp_path))
    report = tmp_path / "citation_context_report.md"
    assert report.exists()
    assert str(report) in summary
    assert "Scanned 2 .tex file(s)" in summary
    assert "related.tex (1)" in summary
    body = report.read_text(encoding="utf-8")
    assert "related.tex" in body
    assert "citet" in body
