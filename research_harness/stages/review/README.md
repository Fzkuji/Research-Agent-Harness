# Paper-review skills

Three stand-alone agent skills (Claude Code / opencode) shipped with this
sub-module, covering the two distinct review use cases (self-eval vs
submission to a venue):

- **`self-paper-review`** — critique your own paper before submitting.
  Pure-prompt skill; no corpus templates, no external CLI, no AI-detector
  constraint. Optimized for harsh, paper-grounded critique that the user
  can feed into a revision loop.
- **`official-paper-review`** — write a venue-form peer review of someone
  else's paper, from scratch, with prose drawn from a corpus of ~500
  GPTZero-verified human reviews (COLM / ICLR / NeurIPS / ICML,
  2018-2025). Targets the lab's AI-detector cap (e.g. ACM MM 2026
  <=20%). Empirically 0% AI on GPTZero (ACM MM smoke test).
- **`humanize-paper-review`** — you (or an LLM) already wrote a review
  draft, and now its prose has to pass an AI detector while keeping your
  score / verdict / observations verbatim. Uses 2-stage redaction:
  extracts structured judgment from the draft, then regenerates prose
  from scratch (so no draft-prose token reaches the prose generator's
  context). 1% AI on GPTZero in the smoke test.

The skills themselves live at `<repo>/skills/{self,official,humanize}-paper-review/SKILL.md`.
This directory holds the underlying `review_app` CLI (used by `official-`
and `humanize-`; `self-` is a pure-prompt skill), the corpus
(`review_corpus/`), and the cross-platform installer.

Use-case map:

| You are... | Use this skill |
|---|---|
| Pre-submission self-critique of *your* paper | `self-paper-review` |
| Reviewing someone else's paper, AI-rate matters | `official-paper-review` |
| Already have a review draft (yours, an LLM's, a colleague's), want it under the detector cap | `humanize-paper-review` |

## One-line install

```bash
# === Mac / Linux ===

# Claude Code, default paths
curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3

# opencode
AGENT_SKILL_DIR=~/.opencode/skills bash -c 'curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3'

# Cursor / Continue / any agent that just reads SKILL.md from a directory
AGENT_SKILL_DIR=~/my-prompts/skills bash -c 'curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3'

# Custom repo location
RESEARCH_HARNESS_DIR=/opt/research-harness bash -c 'curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3'

# Custom repo + custom skill dir at once
RESEARCH_HARNESS_DIR=/opt/rah AGENT_SKILL_DIR=~/my-prompts/skills bash -c 'curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3'

# Don't touch my PYTHONPATH (I'll set it myself)
curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3 - --no-pythonpath

# Install for Claude Code AND opencode side by side (one repo, two symlinks)
curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3
AGENT_SKILL_DIR=~/.opencode/skills bash -c 'curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3'
```

```powershell
# === Windows (PowerShell) ===

# Claude Code, default paths
irm https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python

# opencode
$env:AGENT_SKILL_DIR = "$env:USERPROFILE\.opencode\skills"
irm https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python

# Custom paths
$env:RESEARCH_HARNESS_DIR = "C:\research-harness"
$env:AGENT_SKILL_DIR      = "$env:USERPROFILE\my-prompts\skills"
irm https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python

# Don't touch my PYTHONPATH
irm https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python - --no-pythonpath
```

### What gets installed where

The installer touches **three places** on your machine:

| What | Default path | Override |
|---|---|---|
| 1. The repo (full clone, ~13 MB) — contains review_app, corpus (1265 reviewer JSONs + sentence index), and the skill source files | `~/.research-agent-harness/` | `RESEARCH_HARNESS_DIR=<path>` env var or `--repo-dir <path>` flag |
| 2. The three skills (symlink → repo on Mac/Linux; copy on Windows w/o dev mode) | `~/.claude/skills/self-paper-review/`<br>`~/.claude/skills/official-paper-review/`<br>`~/.claude/skills/humanize-paper-review/` | `AGENT_SKILL_DIR=<path>` env var or `--skill-dir <path>` flag |
| 3. `PYTHONPATH` (so `python -m research_harness.review_app` resolves) | Appended to `~/.zshrc` (Mac, default shell) or `~/.bashrc` (Linux) — Windows uses `setx` to write the user-scope env var | `--no-pythonpath` flag to skip |

After install your filesystem looks like:

```
~/.research-agent-harness/                # ← the repo
├── research_harness/
│   ├── review_app.py                     # the CLI official- and humanize- skills call
│   └── stages/review/
│       ├── install.py                    # this installer
│       ├── README.md                     # this file
│       └── review_corpus/
│           ├── source/                   # 1265 GPTZero-verified human reviewer JSONs
│           └── processed/                # sentence-template index for sample_for_venue
└── skills/
    ├── self-paper-review/SKILL.md
    ├── official-paper-review/SKILL.md
    └── humanize-paper-review/SKILL.md

~/.claude/skills/                         # ← where Claude Code looks for skills
├── self-paper-review       -> ~/.research-agent-harness/skills/self-paper-review
├── official-paper-review   -> ~/.research-agent-harness/skills/official-paper-review
└── humanize-paper-review   -> ~/.research-agent-harness/skills/humanize-paper-review

~/.zshrc                                  # ← appended:
                                          # export PYTHONPATH="$HOME/.research-agent-harness:$PYTHONPATH"
```

### Uninstall

There is no uninstaller, but cleanup is three deletes (whatever paths
you actually used):

```bash
rm -rf ~/.research-agent-harness                          # the repo + corpus
rm ~/.claude/skills/self-paper-review                              # the symlinks
rm ~/.claude/skills/official-paper-review
rm ~/.claude/skills/humanize-paper-review
# Then remove the `export PYTHONPATH=...` line install.py added
# to ~/.zshrc / ~/.bashrc (or `setx PYTHONPATH ""` on Windows).
```

## Use after install

In Claude Code / opencode:

```
> /self-paper-review my_own_paper.pdf venue=NeurIPS
> /official-paper-review someone_elses_paper.pdf venue="NeurIPS"
> /humanize-paper-review someone_elses_paper.pdf draft=existing_review.md venue="ACM Multimedia"
```

`self-paper-review` runs entirely inside the agent (no external CLI).
`official-` and `humanize-` delegate prose generation to the
`review_app` CLI; you can also call that CLI directly (no agent needed):

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
