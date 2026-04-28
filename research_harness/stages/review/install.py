#!/usr/bin/env python3
"""Cross-platform installer for the self-paper-review +
official-paper-review + humanize-paper-review skills, plus the
underlying review_app + corpus.

Default behavior:
  1. Clone (or update) https://github.com/Fzkuji/Research-Agent-Harness
     into ~/.research-agent-harness
  2. Symlink (or copy on Windows w/o dev mode) the three skills into
     ~/.claude/skills/{self,official,humanize}-paper-review
  3. Add the repo path to PYTHONPATH (in shell rc on Unix, or via setx
     on Windows) so `python -m research_harness.review_app` resolves.

Customize via environment variables or CLI flags:
  AGENT_SKILL_DIR / --skill-dir <path>     where to install the skills
                                           (default: ~/.claude/skills)
  RESEARCH_HARNESS_DIR / --repo-dir <path> where to clone the repo
                                           (default: ~/.research-agent-harness)
  --no-pythonpath                          skip the shell-rc / setx step

Examples:
  # Default — Claude Code on Mac/Linux/Windows
  python install.py

  # opencode user
  AGENT_SKILL_DIR=~/.opencode/skills python install.py

  # Both Claude Code and opencode (re-run with different dest)
  python install.py
  AGENT_SKILL_DIR=~/.opencode/skills python install.py

  # Install into a custom location
  python install.py --skill-dir ~/my-prompts/skills --repo-dir /opt/research-harness
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
SKILLS = ("self-paper-review", "official-paper-review",
          "humanize-paper-review")


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    repo = Path(
        args.repo_dir
        or os.environ.get("RESEARCH_HARNESS_DIR")
        or (Path.home() / ".research-agent-harness")
    ).expanduser()
    skills = Path(
        args.skill_dir
        or os.environ.get("AGENT_SKILL_DIR")
        or os.environ.get("CLAUDE_SKILL_DIR")
        or (Path.home() / ".claude" / "skills")
    ).expanduser()
    return repo, skills


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


def _link_skill(src: Path, dst: Path) -> None:
    """Best-effort symlink with copytree fallback (Windows w/o dev mode).

    Removes any existing entry first to keep the link / copy in sync.
    """
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst, ignore_errors=True)
    try:
        dst.symlink_to(src, target_is_directory=True)
        print(f"  symlink: {dst} -> {src}")
    except (OSError, NotImplementedError) as e:
        # Windows without dev mode / admin: fall back to copy.
        shutil.copytree(src, dst)
        print(f"  copy:    {src} -> {dst}  "
              f"(re-run install.py to update; reason: {e})")


def _set_pythonpath(repo: Path) -> None:
    if platform.system() == "Windows":
        # Persist via setx (user scope). Note: setx writes to the user
        # registry; effective in *new* terminals only.
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
            print(f"  ! could not run setx ({e}); set PYTHONPATH manually:",
                  file=sys.stderr)
            print(f"    PYTHONPATH={new}", file=sys.stderr)
        return

    # Unix — append to shell rc if not already there.
    home = Path.home()
    candidates = [home / ".zshrc", home / ".bashrc", home / ".profile"]
    rc = next((c for c in candidates if c.exists()), candidates[0])
    line = f'export PYTHONPATH="{repo}:$PYTHONPATH"'
    existing = rc.read_text() if rc.exists() else ""
    if line in existing:
        print(f"  PYTHONPATH already in {rc}")
        return
    with rc.open("a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"# Added by Research-Agent-Harness install.py\n{line}\n")
    print(f"  appended PYTHONPATH to {rc}. "
          f"Open a new shell or `source {rc}`.")


def main() -> int:
    p = argparse.ArgumentParser(
        prog="install.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--skill-dir", default=None,
                   help="Where to install the skills "
                        "(default: ~/.claude/skills, override via "
                        "AGENT_SKILL_DIR env var).")
    p.add_argument("--repo-dir", default=None,
                   help="Where to clone the repo "
                        "(default: ~/.research-agent-harness, override "
                        "via RESEARCH_HARNESS_DIR env var).")
    p.add_argument("--no-pythonpath", action="store_true",
                   help="Skip adding the repo to PYTHONPATH.")
    args = p.parse_args()

    repo, skills = _resolve_paths(args)
    print(f"== Research Agent Harness installer ==")
    print(f"  repo dir:  {repo}")
    print(f"  skill dir: {skills}")
    print()

    print("[1/3] Repo")
    _clone_or_pull(repo)
    print()

    print("[2/3] Skills")
    skills.mkdir(parents=True, exist_ok=True)
    for name in SKILLS:
        src = repo / "skills" / name
        if not src.is_dir():
            print(f"  ! source skill not found: {src}", file=sys.stderr)
            return 1
        _link_skill(src, skills / name)
    print()

    print("[3/3] PYTHONPATH")
    if args.no_pythonpath:
        print(f"  (skipped — set PYTHONPATH manually to: {repo})")
    else:
        _set_pythonpath(repo)
    print()

    print("✓ install done")
    print()
    print("Next:")
    print(f"  1. Restart your terminal (or run "
          f"`export PYTHONPATH={repo}:$PYTHONPATH`).")
    print(f"  2. Verify: python -c "
          f"'from research_harness.review_app import generate_review' && "
          f"echo OK")
    print(f"  3. In your agent (Claude Code, opencode, ...):")
    print(f"       /self-paper-review <paper.pdf>           "
          f"# critique your own paper")
    print(f"       /official-paper-review <paper.pdf> venue=<v>     "
          f"# review someone else's paper, prose <=AI cap")
    print(f"       /humanize-paper-review <paper.pdf> draft=<d.md> venue=<v>"
          f"  # humanize an existing draft")
    return 0


if __name__ == "__main__":
    sys.exit(main())
