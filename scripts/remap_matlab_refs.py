#!/usr/bin/env python3
"""Move the MATLAB line references in this port to a new FITEVAL_GUI.m.

The Python sources cite line numbers in the desktop program, written as
L1234 or L1234-1256. Editing FITEVAL_GUI.m moves the code those numbers
point at, and the citations go stale. This tool re-derives them.

It aligns the two copies of FITEVAL_GUI.m with difflib and moves each
reference by the same amount as the line it points at. A reference is
"exact" when that line survived the edit unchanged. When the line was
rewritten, difflib cannot follow it, so the tool estimates from the
nearest surviving neighbour and reports the reference for review: the
estimate is often right, but not always, and a rewritten block usually
needs a human to pick the new target.

Usage, from the repository root:

    # see what would change
    python scripts/remap_matlab_refs.py OLD.m NEW.m

    # write the changes
    python scripts/remap_matlab_refs.py OLD.m NEW.m --apply

OLD.m is the copy the current references match, i.e. the desktop source as
it was before the edit. Keep one whenever you change FITEVAL_GUI.m; the
FITEVAL_GUI_src/_backup_* folder holds these.

Always read the review list before trusting --apply, and check that the
code each flagged reference lands on is still the code the comment
describes.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

REF = re.compile(r"L(\d{2,4})(?:-(\d{2,4}))?")
DEFAULT_GLOBS = ("fiteval_core/*.py", "fiteval_app/**/*.py", "tests/*.py")
SEARCH = 400          # how far to look for a surviving neighbour


def read_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    return [line.rstrip() for line in text.splitlines()]


def build_map(old: list[str], new: list[str]) -> dict[int, int]:
    """1-based old line -> 1-based new line, for lines that did not change."""
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    out: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                out[i1 + k + 1] = j1 + k + 1
    return out


def move(line: int, amap: dict[int, int]) -> tuple[int | None, int]:
    """Return (new line, 0) when exact, (estimate, offset) when not."""
    if line in amap:
        return amap[line], 0
    for d in range(1, SEARCH):
        if line - d in amap:
            return amap[line - d] + d, -d
        if line + d in amap:
            return amap[line + d] - d, d
    return None, 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Re-derive MATLAB line references after editing "
                    "FITEVAL_GUI.m.")
    ap.add_argument("old", type=Path, help="FITEVAL_GUI.m the references match")
    ap.add_argument("new", type=Path, help="FITEVAL_GUI.m to move them to")
    ap.add_argument("--apply", action="store_true",
                    help="write the files (default: report only)")
    ap.add_argument("--root", type=Path, default=Path("."),
                    help="repository root (default: the current directory)")
    ap.add_argument("--glob", action="append", dest="globs",
                    help="file pattern to scan; repeatable "
                         f"(default: {', '.join(DEFAULT_GLOBS)})")
    args = ap.parse_args(argv)

    for p in (args.old, args.new):
        if not p.is_file():
            sys.stderr.write(f"No such file: {p}\n")
            return 2

    old, new = read_lines(args.old), read_lines(args.new)
    amap = build_map(old, new)
    print(f"{args.old.name}: {len(old)} lines   {args.new.name}: {len(new)} "
          f"lines   aligned: {len(amap)} ({100 * len(amap) // max(1, len(old))}%)")

    files: list[Path] = []
    for pattern in (args.globs or DEFAULT_GLOBS):
        files += [f for f in args.root.glob(pattern) if f.is_file()]
    files = sorted(set(files))

    review: list[str] = []
    counts = {"exact": 0, "review": 0, "unmapped": 0}

    for f in files:
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(args.root)

        def replace(m: re.Match) -> str:
            start = int(m.group(1))
            if start > len(old):
                counts["unmapped"] += 1
                review.append(f"  {rel}  {m.group(0)}  past the end of "
                              f"{args.old.name} - check it by hand")
                return m.group(0)
            a, off_a = move(start, amap)
            if a is None:
                counts["unmapped"] += 1
                review.append(f"  {rel}  {m.group(0)}  no nearby anchor - "
                              f"check it by hand")
                return m.group(0)
            out, off_b = f"L{a}", 0
            if m.group(2):
                b, off_b = move(min(int(m.group(2)), len(old)), amap)
                if b is None:
                    counts["unmapped"] += 1
                    review.append(f"  {rel}  {m.group(0)}  range end has no "
                                  f"anchor - check it by hand")
                    return m.group(0)
                out += f"-{b}"
            if off_a or off_b:
                counts["review"] += 1
                review.append(
                    f"  {rel}  {m.group(0)} -> {out}  (estimated)\n"
                    f"      was: {old[start - 1].strip()[:64]}\n"
                    f"      now: {new[a - 1].strip()[:64]}")
            else:
                counts["exact"] += 1
            return out

        updated = REF.sub(replace, text)
        if args.apply and updated != text:
            f.write_text(updated, encoding="utf-8")

    total = sum(counts.values())
    print(f"{total} references in {len(files)} files: "
          f"{counts['exact']} exact, {counts['review']} estimated, "
          f"{counts['unmapped']} unmapped")
    if review:
        print("\nCheck these by hand - the code they point at was rewritten:")
        print("\n".join(review))
    print("\nFiles written." if args.apply
          else "\nNothing written. Re-run with --apply.")
    return 1 if counts["unmapped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
