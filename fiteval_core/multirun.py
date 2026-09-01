"""Multi-run batch mode (MR_RunButtonPushed, FITEVAL_GUI.m L846-1027).

Each row holds a file field ('name.in [norep] [figure text]') and an option
string ('0', a PER value, '1 <errfile>', '2 <errfile>', '3 <case> o... p...'
or '4 <case> p...').  Results are appended to a summary CSV with the same
columns and trailing-comma format as the desktop app.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .bootstrap import BootstrapError
from .config import FitevalConfig
from .dataio import DataError, read_in_file, safe_join
from .engine import EngineError
from .runner import RunArtifacts, run_evaluation, run_evaluation_unc
from .uncertainty import UncError, UncSpec, parse_unc_string


@dataclass
class MultiRunOutcome:
    logs: list[str] = field(default_factory=list)       # per-row 'OK'/error
    summary_path: Path | None = None
    files: list[Path] = field(default_factory=list)
    header: list[str] = field(default_factory=list)


def parse_list_file(text: str) -> list[tuple[str, str]]:
    """Parse a multi-run list file into (file_field, option) rows.

    Mirrors MR_LoadFileName (L1106-1133): each line is split at the first
    ';' or ',' -- everything before is the file field
    ('name.in [norep] [label]'), everything after is the option string.
    Lines without a separator are taken as a file field with option '0'.
    Blank lines are ignored.
    """
    rows: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.replace(",", ";").strip()
        if not line:
            continue
        sep = line.find(";")
        if sep == -1:
            rows.append((line, "0"))
        else:
            option = line[sep + 1:].strip()
            rows.append((line[:sep].strip(), option or "0"))
    return rows


def parse_file_field(field_str: str) -> tuple[str, bool, str]:
    """'name.in norep some text' -> (name.in, no_repeated, figure text)."""
    norep = "norep" in field_str.lower()
    cleaned = re.sub("norep", "", field_str, flags=re.IGNORECASE)
    tokens = cleaned.split()
    if not tokens:
        raise DataError("Empty file name in multi-run table")
    return tokens[0], norep, " ".join(tokens[1:])


def option_to_spec(option: str, workspace: Path
                   ) -> tuple[UncSpec | None, int | None]:
    """Interpret one option string (ValidOptionVal + Run_Callback L580-593).

    Returns (spec, parsed_case); spec None means no uncertainty.
    parsed_case is the CF case number from the string (None otherwise).
    """
    option = (option or "0").strip()
    if not option or option[0] not in "01234" and not option[0] == ".":
        raise UncError(f"Invalid option value: {option!r} "
                       "(first character must be 0, 1, 2, 3 or 4)")
    first = option.split()[0]
    val = float(first)
    if val == 0:
        return None, None
    if 0 < val < 1:
        # multi-run common PER goes through the uniform-CDF CF conversion
        return UncSpec(method="per_mixed", per=val), None
    if first in ("1", "2"):
        rest = option[1:].strip()
        if not rest:
            raise UncError(f"ERROR: provide error file name after the {first}")
        err_path = safe_join(workspace, rest)
        if not err_path.is_file():
            raise UncError(f"ERROR: file {rest} not found!")
        err = np.atleast_2d(read_in_file(err_path))
        if err.shape[1] not in (1, 2):
            raise UncError(
                f"Column Nr. in Error Data ({err.shape[1]}) is different "
                "to column Nr. required (1 or 2)")
        # option '1' = PER/bounds method; option '2' = CF method (MixedMethod)
        return UncSpec(method="errfile", err_data=err,
                       err_as_cf=(first == "2")), None
    # CF options '3 <case> ...' / '4 <case> ...'
    opt, case, od, pd_, cvo, cvp, plo, puo, plp, pup = parse_unc_string(option)
    if opt == 3 and case is not None and not (9 <= case <= 12):
        raise UncError("Option and Case values are not compatible")
    if opt == 4 and case is not None and not (13 <= case <= 14):
        raise UncError("Option and Case values are not compatible")
    spec = UncSpec(method="cf", obs_dist=od, prd_dist=pd_, cvo=cvo, cvp=cvp,
                   plubo=plo, puubo=puo, plubp=plp, puubp=pup)
    return spec, case


_LABELS = {1: "NSE", 2: "KGE*", 3: "KGE", 4: "E1"}
# blank fill for the "With Unc." block of a no-uncertainty row: value/scalar
# cells "--", CI cells empty
_WITH_UNC_BLANK = ["--", "", "--", "", "--", "--", "--", "--"]


def _summary_index_spec(cfg: FitevalConfig):
    """(idx1, idx2, idx2_pos, primary, uidx) column labels for the summary.

    idx1 is the coeff.-efficiency index (NSE, or E1 when E1 is selected),
    idx2 the KGE-family index (KGE* by default, KGE when KGE is selected);
    primary is the Configuration-selected index; uidx is the index the
    with-uncertainty run reports (NSE unless E1 is selected).
    """
    flag = cfg.gof_index_effective
    idx1 = "E1" if flag == 4 else "NSE"
    idx2, idx2_pos = ("KGE", 3) if flag == 3 else ("KGE*", 2)
    return idx1, idx2, idx2_pos, _LABELS[flag], ("E1" if flag == 4 else "NSE")


def _isnan(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _f3(v) -> str:
    return "NaN" if _isnan(v) else f"{float(v):.3f}"


def _ci(lo, hi) -> str:
    return "NaN" if (_isnan(lo) or _isnan(hi)) else f"[{float(lo):.3f} - {float(hi):.3f}]"


def _g(v) -> str:
    return "NaN" if _isnan(v) else f"{float(v):g}"


def _no_unc_cells(res, idx2_pos: int, primary: str) -> list[str]:
    ci = res.ci_all
    return [
        _f3(res.gof[1]), _ci(ci[0, 1], ci[1, 1]),
        _f3(res.gof[idx2_pos]), _ci(ci[0, idx2_pos], ci[1, idx2_pos]),
        _g(res.rmse), _ci(res.rmse_ci[0], res.rmse_ci[1]),
        f"{res.nrmse_pct:.0f}%",
        _f3(res.p_value), _g(res.class_lim[0]), primary,
    ]


def _with_unc_cells(res) -> list[str]:
    label = "E1" if res.index_label in ("E_1", "E1") else res.index_label
    return [
        _f3(res.main_idx), _ci(res.main_ci[0], res.main_ci[1]),
        _g(res.rmse), _ci(res.rmse_ci[0], res.rmse_ci[1]),
        f"{res.nrmse_pct:.0f}%",
        _f3(res.p_value), _g(res.class_lim[0]), label,
    ]


def _tail_cells(res) -> list[str]:
    if res.outliers.present:
        pt = res.outliers.points[0]
        outl = f"({pt[0]:g}; {pt[1]:g})"
    else:
        outl = "No"
    bias = f"{res.bias_rel:.2f}%".replace("-0.00%", "0.00%")
    return [bias, outl, f"{res.n}"]


def run_multi(rows: list[tuple[str, str]], workspace: str | Path,
              cfg: FitevalConfig, list_name: str = "multi_run.cf",
              rng: np.random.Generator | None = None) -> MultiRunOutcome:
    """Run every (file_field, option) row; write <list>_summary.csv.

    The summary has a "No Unc." section (always) and a "With Unc." section
    (only when at least one row carries an uncertainty option, since those
    rows are evaluated twice - with and without uncertainty).  Column labels
    follow the Configuration-selected index; the with-uncertainty runs are
    reported under NSE (their forced index) and its NSE-scale threshold.
    """
    workspace = Path(workspace)
    out = MultiRunOutcome()
    idx1, idx2, idx2_pos, primary, uidx = _summary_index_spec(cfg)
    collected: list[tuple] = []  # (field, option, no_unc, with_unc|None, tail)
    any_unc = False

    for field_str, option in rows:
        try:
            fname, norep, figtext = parse_file_field(field_str)
            fpath = safe_join(workspace, fname)
            if not fpath.is_file():
                raise DataError(f"File {fname} not found!")
            data = read_in_file(fpath)
            if data.shape[1] > 3:
                data = data[:, :3]
            spec, case = option_to_spec(option, workspace)

            if spec is not None and spec.method == "cf" and case is not None:
                # the case number in the string decides benchmark use
                # (computeCF L3029-3043)
                if case % 2 == 0 and data.shape[1] < 3:
                    raise DataError(f"Benchmark series required in {fname}")
                if case % 2 == 1 and data.shape[1] == 3:
                    data = data[:, :2]

            if spec is None:
                art = run_evaluation(data, fname, workspace, cfg,
                                     no_repeated=norep, fig_text=figtext,
                                     rng=rng)
                res_p, res_u = art.result, None
                out.files += list(art.files)
            else:
                art_u, art_p = run_evaluation_unc(
                    data, spec, fname, workspace, cfg, no_repeated=norep,
                    fig_text=figtext, rng=rng)
                res_p, res_u = art_p.result, art_u.result
                any_unc = True
                out.files += list(art_u.files) + list(art_p.files)

            collected.append((
                field_str, option.replace("%", ""),
                _no_unc_cells(res_p, idx2_pos, primary),
                _with_unc_cells(res_u) if res_u is not None else None,
                _tail_cells(res_p)))
            log = "OK"
            if res_p.repeated_cases:
                plural = "s were" if res_p.repeated_cases > 1 else " was"
                log += f", {res_p.repeated_cases} repeated case{plural} removed"
            out.logs.append(log)
        except (DataError, EngineError, BootstrapError, UncError,
                ValueError) as exc:
            out.logs.append(str(exc))

    if collected:
        band = ["", ""] + ["No Unc."] * 10
        header = ["Case", "Option", idx1, f"{idx1} 95%CI", idx2,
                  f"{idx2} 95%CI", "RMSE", "RMSE 95%CI", "NRMSE", "p-value",
                  "threshold", "Indicator"]
        if any_unc:
            band += ["With Unc."] * 8
            header += [uidx, f"{uidx} 95%CI", "RMSE", "RMSE 95%CI", "NRMSE",
                       "p-value", "threshold", "Indicator"]
        band += ["", "", ""]
        header += ["Bias", "Outlier", "N"]
        out.header = header

        base = Path(str(list_name)).name.split(".")[0] if list_name else "mr"
        out.summary_path = safe_join(workspace, f"{base or 'mr'}_summary.csv")
        with open(out.summary_path, "w", encoding="utf-8") as fid:
            fid.write(",".join(band) + "\n")
            fid.write(",".join(header) + "\n")
            for field_str, option, nou, wu, tail in collected:
                row = [field_str, option] + nou
                if any_unc:
                    row += wu if wu is not None else _WITH_UNC_BLANK
                fid.write(",".join(row + tail) + "\n")
        out.files.append(out.summary_path)
    return out
