"""Cheap, AI-free check: has the sibling MIDAS-API repo's docs/manual/ changed
since this repo last vendored it, and if so, which midas_nx modules does that
touch (via docs/coverage.json's chapter_file -> module mapping)?

Exit code 0 -> no relevant diff, nothing to do.
Exit code 1 -> diff found; JSON report is printed to stdout (and optionally
                written to --out).

This script never calls an LLM and never writes to coverage.json. It only
reports; a human (or a human pasting the issue's prompt into Claude Code)
reviews the affected modules against the changed manual chapters and then
bumps "vendored_at_commit" in coverage.json once addressed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Real chapter docs are named e.g. "01_DOC.md", "24_DB_Design.md". This
# excludes sibling non-chapter files under docs/manual/ (INDEX.md,
# .sync_manifest.json, README.md, ...) that aren't mapped in coverage.json.
CHAPTER_FILE_RE = re.compile(r"^\d{2}_.*\.md$")


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manual-api-repo",
        required=True,
        help="path to a checkout of the Dennis5882/MIDAS-API repo (needs full history)",
    )
    parser.add_argument("--coverage", default=str(ROOT / "docs" / "coverage.json"))
    parser.add_argument("--out", help="path to write the report JSON (optional)")
    args = parser.parse_args()

    manual_repo = Path(args.manual_api_repo)
    coverage_path = Path(args.coverage)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))

    old_commit = coverage.get("vendored_at_commit")
    if not old_commit:
        print(
            f"'vendored_at_commit' missing from {coverage_path}; "
            "cannot determine drift baseline.",
            file=sys.stderr,
        )
        sys.exit(2)

    new_commit = git("rev-parse", "HEAD", cwd=manual_repo)

    if new_commit == old_commit:
        print(json.dumps({"has_diff": False, "commit": old_commit}, ensure_ascii=False))
        sys.exit(0)

    changed = git(
        "diff", "--name-only", old_commit, new_commit, "--", "docs/manual/",
        cwd=manual_repo,
    )
    changed_files = sorted(
        name for p in changed.splitlines()
        if p.strip() and CHAPTER_FILE_RE.match(name := Path(p).name)
    )

    if not changed_files:
        print(json.dumps(
            {"has_diff": False, "old_commit": old_commit, "new_commit": new_commit},
            ensure_ascii=False,
        ))
        sys.exit(0)

    # chapter_file -> set of modules, split by whether anything in that
    # chapter is actually implemented yet (only implemented modules can be
    # "stale"; planned-only chapters are just noted for awareness).
    modules_by_chapter: dict[str, set[str]] = {}
    implemented_chapters: set[str] = set()
    for e in coverage["endpoints"]:
        # A ledger entry can span multiple chapters (e.g. one module
        # implementing endpoints from both ch19 and ch20 records
        # "19_....md / 20_....md") - split so each chapter file matches
        # individually against changed_files, instead of only the compound
        # string ever matching.
        for chapter in e["chapter_file"].split(" / "):
            if e["status"] == "implemented":
                modules_by_chapter.setdefault(chapter, set()).add(e["module"])
                implemented_chapters.add(chapter)

    stale = {
        chapter: sorted(modules_by_chapter[chapter])
        for chapter in changed_files
        if chapter in implemented_chapters
    }
    not_yet_implemented = [
        chapter for chapter in changed_files if chapter not in implemented_chapters
    ]

    result = {
        "has_diff": True,
        "old_commit": old_commit,
        "new_commit": new_commit,
        "changed_manual_files": changed_files,
        "stale_modules": stale,
        "changed_chapters_not_yet_implemented": not_yet_implemented,
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    sys.exit(1)


if __name__ == "__main__":
    main()
