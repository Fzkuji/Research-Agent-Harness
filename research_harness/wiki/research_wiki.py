#!/usr/bin/env python3
"""
Research Wiki — persistent per-project knowledge base.

Accumulates papers, ideas, experiments, claims, and their typed
relationships across the entire research lifecycle.  Inspired by
Karpathy's LLM Wiki pattern: compile knowledge once, keep it current.

Four entity types:
    paper:<slug>   — a published or preprint paper
    idea:<id>      — a research idea (proposed / tested / failed)
    exp:<id>       — a concrete experiment run with results
    claim:<id>     — a testable scientific claim with evidence status

Eight relationship types stored in graph/edges.jsonl:
    extends, contradicts, addresses_gap, inspired_by,
    tested_by, supports, invalidates, supersedes

Usage (CLI):
    python -m research_harness.wiki.research_wiki init <wiki_root>
    python -m research_harness.wiki.research_wiki slug "<title>" --author "<last>" --year 2025
    python -m research_harness.wiki.research_wiki add_edge <root> --from <id> --to <id> --type <type>
    python -m research_harness.wiki.research_wiki rebuild_query_pack <root> [--max-chars 8000]
    python -m research_harness.wiki.research_wiki stats <root>
    python -m research_harness.wiki.research_wiki log <root> "<message>"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------

def slugify(title: str, author_last: str = "", year: int = 0) -> str:
    """Generate a canonical slug: author_last + year + keywords."""
    stop_words = {
        "a", "an", "the", "of", "for", "in", "on",
        "with", "via", "and", "to", "by",
    }
    words = re.sub(r"[^a-z0-9\s]", "", title.lower()).split()
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    keyword = "_".join(keywords[:3]) if keywords else "untitled"

    author = re.sub(r"[^a-z]", "", author_last.lower()) if author_last else "unknown"
    yr = str(year) if year else "0000"
    return f"{author}{yr}_{keyword}"


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_wiki(wiki_root: str) -> str:
    """Create the wiki directory structure and empty index files."""
    root = Path(wiki_root)
    for d in ("papers", "ideas", "experiments", "claims", "graph"):
        (root / d).mkdir(parents=True, exist_ok=True)

    defaults = {
        "index.md": "# Research Wiki Index\n\n_Auto-generated. Do not edit._\n",
        "log.md": "# Research Wiki Log\n\n_Append-only timeline._\n",
        "gap_map.md": "# Gap Map\n\n_Field gaps with stable IDs (G1, G2, ...)._\n",
        "query_pack.md": "# Query Pack\n\n_Auto-generated for idea generation. Max 8000 chars._\n",
    }
    for fname, content in defaults.items():
        path = root / fname
        if not path.exists():
            path.write_text(content)

    edges_path = root / "graph" / "edges.jsonl"
    if not edges_path.exists():
        edges_path.write_text("")

    append_log(wiki_root, "Wiki initialized")
    return str(root)


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------

VALID_EDGE_TYPES = frozenset({
    "extends", "contradicts", "addresses_gap", "inspired_by",
    "tested_by", "supports", "invalidates", "supersedes",
})


def _load_edges(edges_path: Path) -> list[dict]:
    if not edges_path.exists():
        return []
    edges = []
    for line in edges_path.read_text().strip().split("\n"):
        if line.strip():
            try:
                edges.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return edges


def add_edge(
    wiki_root: str,
    from_id: str,
    to_id: str,
    edge_type: str,
    evidence: str = "",
) -> bool:
    """Append a typed edge to graph/edges.jsonl. Returns False if duplicate."""
    if edge_type not in VALID_EDGE_TYPES:
        print(
            f"Warning: unknown edge type '{edge_type}'. "
            f"Valid: {sorted(VALID_EDGE_TYPES)}",
            file=sys.stderr,
        )

    edges_path = Path(wiki_root) / "graph" / "edges.jsonl"
    existing = _load_edges(edges_path)

    for e in existing:
        if (e.get("from") == from_id
                and e.get("to") == to_id
                and e.get("type") == edge_type):
            return False  # duplicate

    edge = {
        "from": from_id,
        "to": to_id,
        "type": edge_type,
        "evidence": evidence,
        "added": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(edges_path, "a") as f:
        f.write(json.dumps(edge, ensure_ascii=False) + "\n")
    return True


# ---------------------------------------------------------------------------
# Query pack
# ---------------------------------------------------------------------------

def rebuild_query_pack(wiki_root: str, max_chars: int = 8000) -> int:
    """Regenerate query_pack.md. Returns the character count."""
    root = Path(wiki_root)
    sections: list[str] = []

    # 1. Project direction (300 chars)
    for name in ("RESEARCH_BRIEF.md", "README.md"):
        brief_path = root.parent / name
        if brief_path.exists():
            brief = brief_path.read_text()[:300]
            sections.append(f"## Project Direction\n{brief}\n")
            break

    # 2. Gap map (1200 chars)
    gap_path = root / "gap_map.md"
    if gap_path.exists():
        raw = gap_path.read_text()
        # Skip if it's only the default header
        if raw.strip() not in (
            "# Gap Map",
            "# Gap Map\n\n_Field gaps with stable IDs (G1, G2, ...)._",
        ):
            sections.append(f"## Open Gaps\n{raw[:1200]}\n")

    # 3. Failed ideas (1400 chars) — highest anti-repetition value
    ideas_dir = root / "ideas"
    if ideas_dir.exists():
        failed: list[str] = []
        for f in sorted(ideas_dir.glob("*.md")):
            content = f.read_text()
            if "outcome: negative" in content or "outcome: mixed" in content:
                lines = content.split("\n")
                title = ""
                failure = ""
                for line in lines:
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')
                    if "failure" in line.lower() or "lesson" in line.lower():
                        idx = lines.index(line)
                        failure = "\n".join(lines[idx : idx + 3])
                if title:
                    failed.append(f"- **{title}**: {failure[:200]}")
        if failed:
            sections.append(
                f"## Failed Ideas (avoid repeating)\n"
                + "\n".join(failed)[:1400]
                + "\n"
            )

    # 4. Paper summaries (1800 chars)
    papers_dir = root / "papers"
    if papers_dir.exists():
        summaries: list[str] = []
        for f in sorted(papers_dir.glob("*.md")):
            content = f.read_text()
            node_id = title = thesis = ""
            content_lines = content.split("\n")
            for i, line in enumerate(content_lines):
                if line.startswith("node_id:"):
                    node_id = line.split(":", 1)[1].strip()
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                if line.startswith("# One-line thesis"):
                    next_lines = content_lines[i + 1 : i + 3]
                    thesis = " ".join(
                        l for l in next_lines if l.strip() and not l.startswith("#")
                    )
            if title:
                summaries.append(f"- [{node_id}] {title}: {thesis[:150]}")
        if summaries:
            sections.append(
                f"## Key Papers ({len(summaries)} total)\n"
                + "\n".join(summaries[:12])[:1800]
                + "\n"
            )

    # 5. Recent relationships (900 chars)
    edges_path = root / "graph" / "edges.jsonl"
    edges = _load_edges(edges_path)
    if edges:
        chains = [
            f"  {e['from']} --{e['type']}--> {e['to']}"
            for e in edges[-20:]
        ]
        sections.append(
            f"## Recent Relationships ({len(edges)} total)\n"
            + "\n".join(chains)[:900]
            + "\n"
        )

    # Assemble within budget
    pack = "# Research Wiki Query Pack\n\n_Auto-generated. Do not edit._\n\n"
    for s in sections:
        if len(pack) + len(s) <= max_chars:
            pack += s
        else:
            remaining = max_chars - len(pack) - 20
            if remaining > 100:
                pack += s[:remaining] + "\n...(truncated)\n"
            break

    (root / "query_pack.md").write_text(pack)
    return len(pack)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats(wiki_root: str) -> dict:
    """Return wiki statistics as a dict."""
    root = Path(wiki_root)

    def count_files(subdir: str) -> int:
        d = root / subdir
        return len(list(d.glob("*.md"))) if d.exists() else 0

    def count_by_field(subdir: str, field: str, value: str) -> int:
        d = root / subdir
        if not d.exists():
            return 0
        return sum(
            1 for f in d.glob("*.md")
            if f"{field}: {value}" in f.read_text()
        )

    edges_path = root / "graph" / "edges.jsonl"
    edge_count = len(_load_edges(edges_path))

    stats = {
        "papers": count_files("papers"),
        "ideas": count_files("ideas"),
        "ideas_failed": count_by_field("ideas", "outcome", "negative"),
        "ideas_succeeded": count_by_field("ideas", "outcome", "positive"),
        "experiments": count_files("experiments"),
        "claims": count_files("claims"),
        "claims_supported": count_by_field("claims", "status", "supported"),
        "claims_invalidated": count_by_field("claims", "status", "invalidated"),
        "edges": edge_count,
        "wiki_root": str(root),
    }
    return stats


def print_stats(wiki_root: str):
    """Print wiki statistics to stdout."""
    s = get_stats(wiki_root)
    print(f"Research Wiki Stats")
    print(f"Papers:      {s['papers']}")
    print(f"Ideas:       {s['ideas']} "
          f"({s['ideas_failed']} failed, {s['ideas_succeeded']} succeeded)")
    print(f"Experiments: {s['experiments']}")
    print(f"Claims:      {s['claims']} "
          f"({s['claims_supported']} supported, "
          f"{s['claims_invalidated']} invalidated)")
    print(f"Edges:       {s['edges']}")
    print(f"Wiki root:   {s['wiki_root']}")


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

def append_log(wiki_root: str, message: str):
    """Append a timestamped entry to log.md."""
    log_path = Path(wiki_root) / "log.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"- `{ts}` {message}\n"

    if log_path.exists():
        with open(log_path, "a") as f:
            f.write(entry)
    else:
        log_path.write_text(f"# Research Wiki Log\n\n{entry}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Research Wiki — persistent research knowledge base"
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init", help="Initialize wiki directory")
    p.add_argument("wiki_root")

    p = sub.add_parser("slug", help="Generate canonical paper slug")
    p.add_argument("title")
    p.add_argument("--author", default="")
    p.add_argument("--year", type=int, default=0)

    p = sub.add_parser("add_edge", help="Add a typed relationship edge")
    p.add_argument("wiki_root")
    p.add_argument("--from", dest="from_id", required=True)
    p.add_argument("--to", dest="to_id", required=True)
    p.add_argument("--type", dest="edge_type", required=True)
    p.add_argument("--evidence", default="")

    p = sub.add_parser("rebuild_query_pack", help="Regenerate query_pack.md")
    p.add_argument("wiki_root")
    p.add_argument("--max-chars", type=int, default=8000)

    p = sub.add_parser("stats", help="Print wiki statistics")
    p.add_argument("wiki_root")

    p = sub.add_parser("log", help="Append to wiki log")
    p.add_argument("wiki_root")
    p.add_argument("message")

    args = parser.parse_args()

    if args.command == "init":
        init_wiki(args.wiki_root)
        print(f"Wiki initialized at {args.wiki_root}")
    elif args.command == "slug":
        print(slugify(args.title, args.author, args.year))
    elif args.command == "add_edge":
        ok = add_edge(
            args.wiki_root, args.from_id, args.to_id,
            args.edge_type, args.evidence,
        )
        if ok:
            print(f"Edge added: {args.from_id} --{args.edge_type}--> {args.to_id}")
        else:
            print(f"Edge already exists (skipped)")
    elif args.command == "rebuild_query_pack":
        n = rebuild_query_pack(args.wiki_root, args.max_chars)
        print(f"query_pack.md rebuilt: {n} chars")
    elif args.command == "stats":
        print_stats(args.wiki_root)
    elif args.command == "log":
        append_log(args.wiki_root, args.message)
        print("Logged.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
