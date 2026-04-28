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

### What gets installed where

The installer touches **three places** on your machine:

| What | Default path | Override |
|---|---|---|
| 1. The repo (full clone, ~13 MB) — contains review_app, corpus (1265 reviewer JSONs + sentence index), and the skill source files | `~/.research-agent-harness/` | `RESEARCH_HARNESS_DIR=<path>` env var or `--repo-dir <path>` flag |
| 2. The two skills (symlink → repo on Mac/Linux; copy on Windows w/o dev mode) | `~/.claude/skills/paper-review/`<br>`~/.claude/skills/humanize-paper-review/` | `AGENT_SKILL_DIR=<path>` env var or `--skill-dir <path>` flag |
| 3. `PYTHONPATH` (so `python -m research_harness.review_app` resolves) | Appended to `~/.zshrc` (Mac, default shell) or `~/.bashrc` (Linux) — Windows uses `setx` to write the user-scope env var | `--no-pythonpath` flag to skip |

After install your filesystem looks like:

```
~/.research-agent-harness/                # ← the repo
├── research_harness/
│   ├── review_app.py                     # the CLI both skills call
│   └── stages/review/
│       ├── install.py                    # this installer
│       ├── README.md                     # this file
│       └── review_corpus/
│           ├── source/                   # 1265 GPTZero-verified human reviewer JSONs
│           └── processed/                # sentence-template index for sample_for_venue
└── skills/
    ├── paper-review/SKILL.md
    └── humanize-paper-review/SKILL.md

~/.claude/skills/                         # ← where Claude Code looks for skills
├── paper-review            -> ~/.research-agent-harness/skills/paper-review
└── humanize-paper-review   -> ~/.research-agent-harness/skills/humanize-paper-review

~/.zshrc                                  # ← appended:
                                          # export PYTHONPATH="$HOME/.research-agent-harness:$PYTHONPATH"
```

### Customization (when default paths don't fit)

Defaults assume Claude Code on a single-user machine. Other agents and
layouts:

```bash
# opencode — write skills to its own directory instead of ~/.claude/skills
AGENT_SKILL_DIR=~/.opencode/skills python install.py

# Custom repo location and a non-Claude/non-opencode skill directory
RESEARCH_HARNESS_DIR=/opt/rah AGENT_SKILL_DIR=~/my-prompts python install.py

# Install side-by-side for two agents (re-run with a different SKILL dir)
python install.py                                      # → ~/.claude/skills/
AGENT_SKILL_DIR=~/.opencode/skills python install.py   # → ~/.opencode/skills/
# Both symlink to the same repo, so `git pull` updates both.

# Skip touching PYTHONPATH (you'll set it yourself)
python install.py --no-pythonpath
```

### Uninstall

There is no uninstaller, but cleanup is three deletes (whatever paths
you actually used):

```bash
rm -rf ~/.research-agent-harness                          # the repo + corpus
rm ~/.claude/skills/paper-review                          # the symlinks
rm ~/.claude/skills/humanize-paper-review
# Then remove the `export PYTHONPATH=...` line install.py added
# to ~/.zshrc / ~/.bashrc (or `setx PYTHONPATH ""` on Windows).
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
