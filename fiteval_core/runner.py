"""Run one evaluation and write the desktop-compatible output files.

File naming mirrors fiteval_2 (L3316-3355): for project name <nproy>
(input filename without extension), suffix 'U' for the with-uncertainty run:
  <nproy>[U]_out.png   combined 4-panel figure (always)
  <nproy>[U].pdf       combined figure as PDF (always)
  <nproy>[U]_out.txt   numerical report (always)
  <nproy>[U].<ext>, <nproy>[U]_cdf.<ext>, <nproy>[U]_ds.<ext>,
  <nproy>[U]_cb.<ext>  individual figures when an extra format is chosen
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import FitevalConfig
from .engine import evaluate_case, prepare_case
from .figures import fig_cdf, fig_combined, fig_match, fig_series, save_figure
from .report import build_numout_row, numerical_report
from .results import EvalResult

FIG_FORMATS = ("pdf", "png", "jpg", "eps", "tif")


@dataclass
class RunArtifacts:
    result: EvalResult
    files: list[Path] = field(default_factory=list)
    combined_png: Path | None = None
    report_txt: Path | None = None
    numout: list[str] = field(default_factory=list)


def _run_case(case, name: str, outdir: Path, cfg: FitevalConfig,
              fig_ext: str, fig_text: str, suffix: str,
              rng: np.random.Generator | None) -> RunArtifacts:
    """Evaluate one prepared case and write its output-file set."""
    nproy = name.rsplit(".", 1)[0] + suffix
    res = evaluate_case(case, cfg, rng=rng)
    art = RunArtifacts(result=res, numout=build_numout_row(res))

    report = numerical_report(res)
    art.report_txt = outdir / f"{nproy}_out.txt"
    art.report_txt.write_text(report, encoding="utf-8")
    art.files.append(art.report_txt)

    combined = fig_combined(res, cfg, fig_text)
    art.combined_png = outdir / f"{nproy}_out.png"
    save_figure(combined, art.combined_png, dpi=cfg.dpi)  # honour configured dpi
    save_figure(combined, outdir / f"{nproy}.pdf")
    art.files += [art.combined_png, outdir / f"{nproy}.pdf"]

    if fig_ext:
        if fig_ext not in FIG_FORMATS:
            raise ValueError(f"Unsupported figure format: {fig_ext}")
        pairs = [
            (fig_match(res, cfg, fig_text), f"{nproy}.{fig_ext}"),
            (fig_cdf(res, cfg), f"{nproy}_cdf.{fig_ext}"),
            (fig_series(res, cfg), f"{nproy}_ds.{fig_ext}"),
            (combined, f"{nproy}_cb.{fig_ext}"),
        ]
        for fig, fname in pairs:
            p = outdir / fname
            save_figure(fig, p, dpi=cfg.dpi, tight=True)
            art.files.append(p)
    return art


def run_evaluation(data: np.ndarray, name: str, outdir: str | Path,
                   cfg: FitevalConfig, no_repeated: bool = False,
                   fig_ext: str = "", fig_text: str = "",
                   suffix: str = "",
                   rng: np.random.Generator | None = None) -> RunArtifacts:
    """No-uncertainty evaluation of [Yobs Yprd (Yben)] + all output files."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    case = prepare_case(data, no_repeated)
    return _run_case(case, name, outdir, cfg, fig_ext, fig_text, suffix, rng)


def run_evaluation_unc(data: np.ndarray, spec, name: str, outdir: str | Path,
                       cfg: FitevalConfig, no_repeated: bool = False,
                       fig_ext: str = "", fig_text: str = "",
                       rng: np.random.Generator | None = None
                       ) -> tuple[RunArtifacts, RunArtifacts]:
    """Uncertainty evaluation: runs twice like fiteval_2 (L3307 + L3335).

    Returns (with-uncertainty artifacts '<name>U_*',
             without-uncertainty artifacts '<name>_*').
    """
    from .uncertainty import prepare_unc_cases

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    unc_case, plain_case = prepare_unc_cases(data, spec, no_repeated)
    art_u = _run_case(unc_case, name, outdir, cfg, fig_ext, fig_text, "U", rng)
    art_p = _run_case(plain_case, name, outdir, cfg, fig_ext, fig_text, "", rng)
    return art_u, art_p


def delete_output_files(outdir: str | Path, name: str) -> int:
    """DeleteOutputFiles (L1428): remove <nproy>* except the .in and .err."""
    outdir = Path(outdir)
    nproy = name.rsplit(".", 1)[0]
    n = 0
    for p in outdir.glob(f"{nproy}*.*"):
        if p.suffix in (".in", ".err"):
            continue
        p.unlink()
        n += 1
    return n
