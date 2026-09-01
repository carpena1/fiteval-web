"""CLI runner: python -m fiteval_core data.in [--ext pdf] [--norep]

Single-run mode evaluates one .in file with the default (or given)
configuration and writes the same outputs as the desktop app next to it.

Multi-run mode (--multi) treats INFILE as a batch list file (one
'datafile [norep] [label] ; option' per line) and writes <list>_summary.csv
plus every per-run output into the list file's directory, exactly like the
desktop / web batch mode.  All referenced .in / .err files must already sit
next to the list file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from .config import FitevalConfig, read_config
from .dataio import read_in_file
from .multirun import parse_list_file, run_multi
from .runner import run_evaluation


def _run_multi(infile: Path, cfg: FitevalConfig,
               rng: np.random.Generator | None) -> int:
    rows = parse_list_file(infile.read_text(encoding="utf-8", errors="replace"))
    if not rows:
        sys.stderr.write(f"No runs found in {infile}\n")
        return 1
    out = run_multi(rows, infile.parent, cfg, list_name=infile.name, rng=rng)
    for (field, _opt), log in zip(rows, out.logs):
        name = field.split()[0] if field.split() else field
        print(f"  {name}: {log}")
    if out.summary_path is None:
        sys.stderr.write("No summary written (all runs failed)\n")
        return 1
    print(f"\nSummary: {out.summary_path}")
    print("Files written:")
    for f in out.files:
        print(f"  {f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows consoles/redirects default to a legacy code page (cp1252, cp850)
    # that cannot encode the Greek rho/alpha of the timing/amplitude line.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(prog="fiteval_core")
    ap.add_argument("infile", help="input .in data file [Yobs Yprd (Yben)], "
                                    "or a batch list file with --multi")
    ap.add_argument("--multi", action="store_true",
                    help="treat INFILE as a multi-run list file "
                         "('datafile [norep] [label] ; option' per line)")
    ap.add_argument("--config", help="fitevalconfig.txt path")
    ap.add_argument("--ext", default="", choices=["", "pdf", "png", "jpg", "eps", "tif"],
                    help="extra individual-figure format (single-run only)")
    ap.add_argument("--norep", action="store_true",
                    help="remove repeated cases (single-run only; in --multi "
                         "use 'norep' in each list line)")
    ap.add_argument("--text", default="",
                    help="annotation text on the figure (single-run only)")
    ap.add_argument("--seed", type=int, help="RNG seed for reproducible CIs")
    args = ap.parse_args(argv)

    infile = Path(args.infile)
    cfg = read_config(args.config) if args.config else FitevalConfig()
    rng = np.random.default_rng(args.seed) if args.seed is not None else None

    if args.multi:
        return _run_multi(infile, cfg, rng)

    data = read_in_file(infile)
    art = run_evaluation(data, infile.name, infile.parent, cfg,
                         no_repeated=args.norep, fig_ext=args.ext,
                         fig_text=args.text, rng=rng)
    sys.stdout.write(art.report_txt.read_text(encoding="utf-8"))
    print("\nFiles written:")
    for f in art.files:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
