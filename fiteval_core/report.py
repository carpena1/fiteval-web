"""Text outputs: the numerical report file and the figure summary panel.

numerical_report() is a verbatim port of numerical_output
(FITEVAL_GUI.m L3968-4035); summary_lines() reproduces the txstr text panel
(L3891-3911) without TeX markup.  build_numout_row() ports the NUMOUT record
(L3766-3782) used by the multi-run summary CSV.
"""

from __future__ import annotations

import re

import numpy as np

from .engine import BENCHMARK_NOTE, BSTYPE_NOTE
from .indices import rounddec
from .results import EvalResult


def _one_line(text: str) -> str:
    """Join a broken diagnostic back onto one line (regexprep, L4017)."""
    return re.sub(r"\s*\n\s*", " ", text)


def _fmt(spec: str, v: float) -> str:
    """C-style formatting with MATLAB's 'NaN' spelling."""
    if isinstance(v, float) and np.isnan(v):
        return "NaN"
    return spec % v


def _num2str(v: float) -> str:
    """MATLAB num2str for scalars: %g-like."""
    if np.isnan(v):
        return "NaN"
    return f"{v:g}"


def nrmse_sd_text(res: EvalResult, for_file: bool) -> str:
    """The 'NRMSE= 100*RMSE/SD= ..%; <sec>= .. [..]; N= ..' line (L3423+3458).

    for_file=True applies the char(183)->'*' and char(8211)->' - '
    substitutions done when writing numerical_output.txt.
    """
    dot = "*" if for_file else "\N{MIDDLE DOT}"
    txt = f"NRMSE= 100{dot}RMSE/SD= " + _fmt("%1.0f", res.nrmse_pct) + "%"
    txt += (f"; {res.sec_label}= " + _fmt("%1.3f", res.sec_idx)
            + " [" + _fmt("%1.3f", res.sec_ci[0]) + " - "
            + _fmt("%1.3f", res.sec_ci[1]) + "]")
    txt += f"; N= {res.n}"
    # negative-CI dash treatment: ' - -' -> ' <endash> -' (L3517), which the
    # file writer later expands back to '  -  -' (L4009-4010)
    txt = txt.replace(" - -", "  -  -" if for_file else " \N{EN DASH} -")
    # compression when the TeX-markup version exceeds 90 chars (L3520);
    # the MATLAB string carries 39 chars of \it/\bf/\rm markup
    if len(txt) + 39 > 90:
        txt = txt.replace("= ", "=")
    return txt


def numerical_report(res: EvalResult) -> str:
    """Content of <name>[U]_out.txt."""
    L: list[str] = []
    L.append("   =============== GOODNESS-OF-FIT EVALUATION ================")

    if rounddec(res.rmse, 2) == 0:
        f = "%1.3e"
    else:
        f = "%1.3f"
    index_str = ("       RMSE= " + _fmt(f, res.rmse)
                 + " [" + _fmt(f, res.rmse_ci[0]) + " - "
                 + _fmt(f, res.rmse_ci[1]) + "]*\n"
                 + f"       {res.index_label} = " + _fmt("%1.3f", res.main_idx)
                 + " [" + _fmt("%1.3f", res.main_ci[0]) + " - "
                 + _fmt("%1.3f", res.main_ci[1]) + "]*")
    index_str = index_str.replace(" - -", "  -  -")
    L.append(index_str)

    p = res.class_probs
    pvalue = (100 - p["acceptable"] - p["good"] - p["verygood"]) / 100.0
    L.append("")
    L.append(f"       Evaluation of {res.index_label}: {res.rating_text}")
    L.append("       Probability of fit being:")
    L.append(f"        - Very good ({res.index_label} = {res.reglim['R1']}): "
             + _fmt("%1.1f", p["verygood"]) + "%")
    L.append(f"        - Good ({res.index_label} = {res.reglim['R2']}): "
             + _fmt("%1.1f", p["good"]) + "%")
    L.append(f"        - Acceptable ({res.index_label} = {res.reglim['R3']}): "
             + _fmt("%1.1f", p["acceptable"]) + "%")
    L.append(f"        - Unsatisfactory ({res.index_label} {res.reglim['R4']}): "
             + _fmt("%1.1f", 100 * pvalue) + "% (p-value: "
             + _fmt("%1.3f", pvalue) + ")")

    if np.isnan(p["verygood"]) and np.isnan(p["good"]):
        L.append("")
        L.append("        WARNING: A KGE probability distribution could not be generated ")
        L.append("        because the KGE is ill-defined when the mean of observations")
        L.append("        is close to zero. To resolve this, select KGE* instead of KGE.")

    L.append("")
    L.append("       " + nrmse_sd_text(res, for_file=True))
    L.append("       " + res.outliers.text)
    if res.outliers.present:
        pt = res.outliers.points
        L.append(f"       Potential outlier at: ({_num2str(pt[0, 0])},"
                 f"{_num2str(pt[0, 1])})")
    L.append("       " + res.bias_txt1)
    if res.bias_txt2:
        L.append("                 " + res.bias_txt2)
    if res.imbalance_txt:
        # MATLAB collapses the line break for the file (L4017)
        L.append("       " + _one_line(res.imbalance_txt))
    if res.repeated_cases == 1:
        L.append("")
        L.append(f"       {res.repeated_cases} repeated case was removed")
    elif res.repeated_cases > 1:
        L.append("")
        L.append(f"       {res.repeated_cases} repeated cases were removed")
    L.append("   ____________________________________________________________")
    L.append("   *: 95% Confidence interval obtained from Bca bootstrapping")
    note = BSTYPE_NOTE[res.bstype_used]
    L.append("      " + note[0])
    L.append("      " + note[1])
    if res.benchmark_used:
        L.append("")
        L.append("      " + BENCHMARK_NOTE[0])
        L.append("      " + BENCHMARK_NOTE[1])
    if res.meas_unc != 0 and res.unc_type_lines:
        L.append("")
        L.append("      " + res.unc_type_lines[0])
        L.append("      " + res.unc_type_lines[1])
    return "\n".join(L) + "\n"


def nrmse_sd_segments(res: EvalResult) -> list[tuple[str, bool]]:
    """The NRMSE/SD figure line split into (text, bold) segments.

    The secondary indicator with its 95% CI (between 'NRMSE..%' and '; N=')
    is bold, matching the \\bf markup at L3514.
    """
    dot = "\N{MIDDLE DOT}"
    p1 = f"NRMSE= 100{dot}RMSE/SD= " + _fmt("%1.0f", res.nrmse_pct) + "%; "
    p2 = (f"{res.sec_label}= " + _fmt("%1.3f", res.sec_idx) + " ["
          + _fmt("%1.3f", res.sec_ci[0]) + " - "
          + _fmt("%1.3f", res.sec_ci[1]) + "]")
    p3 = f"; N= {res.n}"
    p2 = p2.replace(" - -", " \N{EN DASH} -")
    if len(p1 + p2 + p3) + 39 > 90:      # same TeX-length rule as nrmse_sd_text
        p1, p2, p3 = (s.replace("= ", "=") for s in (p1, p2, p3))
    return [(p1, False), (p2, True), (p3, False)]


def summary_segments(res: EvalResult) -> list[list[tuple[str, bool]]]:
    """Figure text panel as styled lines: each line is a list of
    (text, bold) segments (txstr, L3891-3911).  Three lines carry the
    MATLAB \\bf emphasis: the rating on the 'Evaluation of' line, the
    '(p-value: ..)' on the Unsatisfactory line, and the secondary index
    with its CI on the NRMSE line.
    """
    p = res.class_probs
    lbl, R = res.index_label, res.reglim
    lines: list[list[tuple[str, bool]]] = [
        [("=========== GOODNESS-OF-FIT EVALUATION ===========", False)],
        [(f"  Evaluation of {lbl}:   ", False), (res.rating_text, True),
         (" ", False)],
        [("  Probability of fit being:", False)],
        [(f"     - Very good ({lbl} = {R['R1']}): "
          f"{_num2str(p['verygood'])}%", False)],
        [(f"     - Good ({lbl} = {R['R2']}): {_num2str(p['good'])}%", False)],
        [(f"     - Acceptable ({lbl} = {R['R3']}): "
          f"{_num2str(p['acceptable'])}%", False)],
        [(f"     - Unsatisfactory ({lbl} {R['R4']}): "
          f"{_num2str(p['unsatisfactory'])}%  ", False),
         (f"(p-value: {_num2str(p['unsatisfactory'] / 100.0)})", True)],
        [(" ", False)],
        [("  ", False)] + nrmse_sd_segments(res),
        [("  " + res.outliers.text, False)],
    ]
    if res.outliers.present:
        pt = res.outliers.points
        lines.append([(f"  Potential outlier at: ({_num2str(pt[0, 0])},"
                       f"{_num2str(pt[0, 1])})", False)])
    lines.append([("  " + res.bias_txt1, False)])
    if res.bias_txt2:
        lines.append([("                   " + res.bias_txt2, False)])
    if res.imbalance_txt:
        # kept as separate rows here: the figure panel does not wrap
        lines += [[("  " + part, False)]
                  for part in res.imbalance_txt.split("\n")]
    return lines


def summary_lines(res: EvalResult) -> list[str]:
    """Figure text panel lines (txstr, L3891-3911), plain text."""
    return ["".join(t for t, _ in segs) for segs in summary_segments(res)]


def build_numout_row(res: EvalResult) -> list[str]:
    """NUMOUT record for the multi-run summary CSV (L3766-3782)."""
    if rounddec(res.rmse, 2) == 0:
        rf = "%1.3e"
    else:
        rf = "%1.3f"
    if res.outliers.present:
        pt = res.outliers.points
        outl = f"({_num2str(pt[0, 0])}; {_num2str(pt[0, 1])})"
    else:
        outl = "No"
    return [
        _fmt("%1.3f", res.main_idx),
        " [" + _fmt(res.main_fmt, res.main_ci[0]) + " - "
        + _fmt(res.main_fmt, res.main_ci[1]) + "]",
        _fmt("%1.3f", res.sec_idx),
        " [" + _fmt("%1.3f", res.sec_ci[0]) + " - "
        + _fmt("%1.3f", res.sec_ci[1]) + "]",
        _fmt(rf, res.rmse),
        " [" + _fmt(rf, res.rmse_ci[0]) + " - " + _fmt(rf, res.rmse_ci[1]) + "]",
        _fmt("%1.3f", res.class_probs["unsatisfactory"] / 100.0),
        _fmt("%1.3f", res.class_lim[0]),
        _fmt("%1.0f", res.nrmse_pct) + "%",
        (_fmt("%1.1f", res.bias_rel) + "%").replace("-0.0%", "0.0%"),
        outl,
        f"{res.n}",
    ]
