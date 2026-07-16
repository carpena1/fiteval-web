"""CLI smoke runner: python -m fiteval_core data.in [--ext pdf] [--norep]

Evaluates the file with the default (or given) configuration and writes the
same outputs as the desktop app next to the input file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from .config import FitevalConfig, read_config
from .dataio import read_in_file
from .runner import run_evaluation


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fiteval_core")
    ap.add_argument("infile", help="input .in data file [Yobs Yprd (Yben)]")
    ap.add_argument("--config", help="fitevalconfig.txt path")
    ap.add_argument("--ext", default="", choices=["", "pdf", "png", "jpg", "eps", "tif"],
                    help="extra individual-figure format")
    ap.add_argument("--norep", action="store_true", help="remove repeated cases")
    ap.add_argument("--text", default="", help="annotation text on the figure")
    ap.add_argument("--seed", type=int, help="RNG seed for reproducible CIs")
    args = ap.parse_args(argv)

    infile = Path(args.infile)
    cfg = read_config(args.config) if args.config else FitevalConfig()
    rng = np.random.default_rng(args.seed) if args.seed is not None else None

    data = read_in_file(infile)
    art = run_evaluation(data, infile.name, infile.parent, cfg,
                         no_repeated=args.norep, fig_ext=args.ext,
                         fig_text=args.text, rng=rng)
    sys.stdout.write(art.report_txt.read_text())
    print("\nFiles written:")
    for f in art.files:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
