#!/usr/bin/env python3
"""One-line cross-platform installer for paper-review +
humanize-paper-review skills.

Run:
    curl -sSL https://raw.githubusercontent.com/Fzkuji/Research-Agent-Harness/main/research_harness/stages/review/install.py | python3

That's it. No flags, no env vars, no choices required.

What it does (auto-detected):
  1. Clone the repo to a sensible location (~/.research-agent-harness
     by default; reuses an existing clone if you already have one).
  2. Detect every supported agent that's installed on this machine
     (Claude Code, opencode, Cursor, codex, Gemini, ...) by looking
     for its config directory under $HOME, and install the skills
     into each one. If none are detected, fall back to creating
     ~/.claude/skills/ (Claude Code's default).
  3. Make `python -m research_harness.review_app` resolve from any
     shell — appended to ~/.zshrc / ~/.bashrc on Unix, written via
     `setx` on Windows. Skipped silently if already set.

Override anything via env vars or flags:
    RESEARCH_HARNESS_DIR=<path>   override repo clone location
    AGENT_SKILL_DIR=<path>        force a single skill destination
    --skill-dir <path>            same, via flag
    --repo-dir <path>             same as RESEARCH_HARNESS_DIR
    --no-pythonpath               skip the shell-rc / setx step

Idempotent: re-running upgrades the repo (`git pull`) and refreshes
all skill links / copies.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/Fzkuji/Research-Agent-Harness"
SKILLS = ("paper-review", "humanize-paper-review")

# Known agent skill directories — relative to $HOME. Order = display
# order in install summary; not significance.
AGENT_DIRS: tuple[tuple[str, str], ...] = (
    ("Claude Code",      ".claude/skills"),
    ("opencode",         ".opencode/skills"),
    ("Cursor",           ".cursor/skills"),
    ("codex",            ".codex/skills"),
    ("Gemini Code",      ".gemini/skills"),
    ("continue.dev",     ".continue/skills"),
)


def _detect_agent_skill_dirs() -> list[tuple[str, Path]]:
    """Scan $HOME for known agent config dirs. Returns the list of
    (display_name, skill_dir_path) pairs whose *parent* directory
    exists (i.e. the user has that agent installed).
    """
    home = Path.home()
    detected: list[tuple[str, Path]] = []
    for name, rel in AGENT_DIRS:
        skill_dir = home / rel
        # Parent (~/.claude, ~/.opencode, ...) existing means the agent
        # is installed; the skills/ subdir we'll create.
        if skill_dir.parent.is_dir():
            detected.append((name, skill_dir))
    return detected


def _resolve(args: argparse.Namespace) -> tuple[Path, list[tuple[str, Path]]]:
    repo = Path(
        args.repo_dir
        or os.environ.get("RESEARCH_HARNESS_DIR")
        or (Path.home() / ".research-agent-harness")
    ).expanduser()

    forced = (args.skill_dir
              or os.environ.get("AGENT_SKILL_DIR")
              or os.environ.get("CLAUDE_SKILL_DIR"))
    if forced:
        targets = [("(explicit)", Path(forced).expanduser())]
    else:
        targets = _detect_agent_skill_dirs()
        if not targets:
            # Nothing detected — fall back to Claude Code's default
            # location and create it. Keeps the "one line, no
            # questions" promise.
            targets = [("Claude Code (created)",
                        Path.home() / ".claude" / "skills")]
    return repo, targets


def _clone_or_pull(repo: Path) -> None:
    if repo.exists():
        if not (repo / ".git").is_dir():
            print(f"  ! {repo} exists but is not a git repo; aborting.",
                  file=sys.stderr)
            sys.exit(1)
        print(f"  pull: {repo}")
        subprocess.check_call(["git", "-C", str(repo), "pull",
                               "--ff-only"])
    else:
        repo.parent.mkdir(parents=True, exist_ok=True)
        print(f"  clone: {REPO_URL} -> {repo}")
        subprocess.check_call(["git", "clone", REPO_URL, str(repo)])


def _link_skill(src: Path, dst: Path) -> str:
    """Best-effort symlink with copytree fallback. Returns 'symlink'
    or 'copy' to describe what happened.
    """
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst, ignore_errors=True)
    try:
        dst.symlink_to(src, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        shutil.copytree(src, dst)
        return "copy"


def _set_pythonpath(repo: Path) -> None:
    if platform.system() == "Windows":
        cur = os.environ.get("PYTHONPATH", "")
        if str(repo) in cur.split(";"):
            print(f"  PYTHONPATH already includes {repo}")
            return
        new = f"{repo};{cur}" if cur else str(repo)
        try:
            subprocess.check_call(["setx", "PYTHONPATH", new])
            print(f"  setx PYTHONPATH (user env). "
                  f"Open a new terminal for it to take effect.")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"  ! could not run setx ({e}); set PYTHONPATH "
                  f"manually:", file=sys.stderr)
            print(f"    PYTHONPATH={new}", file=sys.stderr)
        return

    # Unix
    home = Path.home()
    candidates = [home / ".zshrc", home / ".bashrc", home / ".profile"]
    rc = next((c for c in candidates if c.exists()), candidates[0])
    line = f'export PYTHONPATH="{repo}:$PYTHONPATH"'
    existing = rc.read_text() if rc.exists() else ""
    if line in existing:
        print(f"  PYTHONPATH already set in {rc}")
        return
    with rc.open("a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"# Added by Research-Agent-Harness install.py\n{line}\n")
    print(f"  appended PYTHONPATH to {rc} "
          f"(open a new shell or `source {rc}`)")


def main() -> int:
    p = argparse.ArgumentParser(
        prog="install.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--skill-dir", default=None,
                   help="Force a single skill install destination "
                        "(default: auto-detect every installed agent).")
    p.add_argument("--repo-dir", default=None,
                   help="Where to clone the repo "
                        "(default: ~/.research-agent-harness).")
    p.add_argument("--no-pythonpath", action="store_true",
                   help="Skip adding the repo to PYTHONPATH.")
    args = p.parse_args()

    repo, targets = _resolve(args)
    print("== Research Agent Harness installer ==")
    print(f"  repo dir:   {repo}")
    print(f"  agents detected:")
    for name, dst in targets:
        print(f"    - {name}: {dst}")
    print()

    print("[1/3] Repo")
    _clone_or_pull(repo)
    print()

    print("[2/3] Skills")
    for name, skill_dir in targets:
        skill_dir.mkdir(parents=True, exist_ok=True)
        for skill in SKILLS:
            src = repo / "skills" / skill
            if not src.is_dir():
                print(f"  ! source skill not found: {src}",
                      file=sys.stderr)
                return 1
            dst = skill_dir / skill
            kind = _link_skill(src, dst)
            print(f"  [{name}] {kind}: {dst}")
    print()

    print("[3/3] PYTHONPATH")
    if args.no_pythonpath:
        print(f"  (skipped — set PYTHONPATH manually to: {repo})")
    else:
        _set_pythonpath(repo)
    print()

    print("✓ install done — installed into:")
    for name, dst in targets:
        print(f"    {name}: {dst}")
    print()
    print(f"Verify: python -c 'from research_harness.review_app "
          f"import generate_review' && echo OK")
    print(f"Use:    /paper-review <paper.pdf> [venue=...]")
    print(f"        /humanize-paper-review <paper.pdf> draft=<draft.md> [venue=...]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
