# Paper-review skills

Two stand-alone agent skills shipped with this sub-module:

- **`paper-review`** — write a venue-format peer review from scratch
  using sentence skeletons drawn live from a corpus of ~500
  GPTZero-verified human reviews (COLM / ICLR / NeurIPS / ICML,
  2018-2025). Empirically 0% AI on GPTZero (ACM MM smoke test).
- **`humanize-paper-review`** — humanize an existing LLM-generated
  review draft via 2-stage redaction (extract structured judgment from
  the draft, then re-generate prose from scratch). Preserves
  score / verdict / sub_scores verbatim from the draft, lands at 1% AI
  on GPTZero.

## One-line install

Mac / Linux:
```bash
curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3
```

Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python
```

The installer auto-detects every supported agent on your machine
(Claude Code, opencode, Cursor, codex, Gemini Code, continue.dev) and
installs the skills into all of them. It clones the repo to
`~/.research-agent-harness`, links the skills, and adds the repo to
`PYTHONPATH`. It prints exactly where everything went.

Re-running upgrades the repo (`git pull`) and refreshes all skill
links — same one-line command.

## Use after install

In your agent:
```
> /paper-review my_paper.pdf venue="NeurIPS"
> /humanize-paper-review my_paper.pdf draft=existing_review.md venue="ACM Multimedia"
```

Or call the underlying CLI directly:
```bash
python -m research_harness.review_app my_paper.pdf \
    --venue "ACM Multimedia" --output review.json
python -m research_harness.review_app my_paper.pdf \
    --venue "ACM Multimedia" --draft existing.md --output humanized.json
```

## Override the defaults

If auto-detection picks the wrong place, override:

```bash
# Force a single skill destination
AGENT_SKILL_DIR=~/my-prompts/skills python install.py

# Custom repo location
RESEARCH_HARNESS_DIR=/opt/rah python install.py

# Don't touch PYTHONPATH
python install.py --no-pythonpath
```

## Uninstall

```bash
rm -rf ~/.research-agent-harness                  # the repo + corpus
# Then for each agent the installer linked into:
rm ~/.claude/skills/paper-review ~/.claude/skills/humanize-paper-review
# (the install summary printed the exact paths to remove)
# Finally remove the `export PYTHONPATH=...` line install.py added
# to ~/.zshrc / ~/.bashrc, or `setx PYTHONPATH ""` on Windows.
```

## Background

- Empirical record of what works / what doesn't:
  [`review_corpus/LESSONS.md`](review_corpus/LESSONS.md)
- Reviewer-JSON schema (v2):
  [`review_corpus/SCHEMA.md`](review_corpus/SCHEMA.md)
- Why verbatim sentence templates beat prompt-only humanization:
  see LESSONS.md sections on v1-v6 prompt iterations.
