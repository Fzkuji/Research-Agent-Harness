# Paper-review skills

Two stand-alone agent skills (Claude Code / opencode) shipped with this
sub-module:

- **`paper-review`** — write a venue-format peer review from scratch
  using sentence skeletons drawn live from a corpus of ~500
  GPTZero-verified human reviews (COLM / ICLR / NeurIPS / ICML,
  2018-2025). Empirically 0% AI on GPTZero (ACM MM smoke test).
- **`humanize-paper-review`** — humanize an existing LLM-generated
  review draft via 2-stage redaction (extract structured judgment from
  the draft, then re-generate prose from scratch). Preserves
  score / verdict / sub_scores verbatim from the draft, lands at 1% AI
  on GPTZero.

The skills themselves live at `<repo>/skills/{paper-review,humanize-paper-review}/SKILL.md`.
This directory holds the underlying `review_app` CLI, the corpus
(`review_corpus/`), and the cross-platform installer.

## One-line install

Mac / Linux:
```bash
curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3
```

Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python
```

The installer:
1. Clones this repo to `~/.research-agent-harness`
2. Symlinks the two skills into `~/.claude/skills/` (or copies on Windows
   when symlink isn't permitted)
3. Adds the repo to `PYTHONPATH` (shell rc on Unix, `setx` on Windows)

## Customization

Override paths via env vars or CLI flags:

```bash
# opencode — different skill directory
AGENT_SKILL_DIR=~/.opencode/skills python install.py

# Custom repo location and skill directory
RESEARCH_HARNESS_DIR=/opt/rah AGENT_SKILL_DIR=~/my-prompts python install.py

# Skip the PYTHONPATH step (set it yourself)
python install.py --no-pythonpath
```

## Use after install

In Claude Code / opencode:

```
> /paper-review my_paper.pdf venue="NeurIPS"
> /humanize-paper-review my_paper.pdf draft=existing_review.md venue="ACM Multimedia"
```

Or call the underlying CLI directly (no agent needed):

```bash
# From-scratch review
python -m research_harness.review_app my_paper.pdf \
    --venue "ACM Multimedia" \
    --output review.json

# Humanize existing draft (2-stage redaction)
python -m research_harness.review_app my_paper.pdf \
    --venue "ACM Multimedia" \
    --draft existing_llm_review.md \
    --output humanized.json
```

Each invocation: 3-7 minutes (codex CLI is the bottleneck).

## Upgrade

Re-run the installer (it does `git pull` and re-links):

```bash
python ~/.research-agent-harness/research_harness/stages/review/install.py
```

## Background

- Empirical record of what works / what doesn't:
  [`review_corpus/LESSONS.md`](review_corpus/LESSONS.md)
- Reviewer-JSON schema (v2):
  [`review_corpus/SCHEMA.md`](review_corpus/SCHEMA.md)
- Why verbatim sentence templates beat prompt-only humanization:
  see LESSONS.md sections on v1-v6 prompt iterations.
