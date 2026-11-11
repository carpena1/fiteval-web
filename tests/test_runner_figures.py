import numpy as np
import pytest

from fiteval_core.config import FitevalConfig
from fiteval_core.engine import evaluate
from fiteval_core.figures import (fig_cdf, fig_combined, fig_match, fig_series,
                                  save_figure)
from fiteval_core.runner import delete_output_files, run_evaluation


def _data(n=60, seed=13):
    rng = np.random.default_rng(seed)
    yobs = 5 + 3 * np.sin(np.linspace(0, 4 * np.pi, n)) + rng.normal(0, 0.3, n)
    yprd = yobs + rng.normal(0, 0.4, n)
    return np.column_stack([yobs, yprd])


@pytest.fixture(scope="module")
def result():
    cfg = FitevalConfig(n_resamples=5000)
    return evaluate(_data(), cfg, rng=np.random.default_rng(1)), cfg


def test_summary_segments_bold_regions(result):
    from fiteval_core.report import summary_lines, summary_segments
    res, _ = result
    segs = summary_segments(res)
    # plain join must equal the plain lines (no text lost/added)
    assert ["".join(t for t, _ in ln) for ln in segs] == summary_lines(res)
    bold = {t for ln in segs for t, b in ln if b}
    # 1) rating on the "Evaluation of" line
    assert res.rating_text in bold
    # 2) the (p-value: ..) on the Unsatisfactory line
    assert any(t.startswith("(p-value:") and t.endswith(")") for t in bold)
    # 3) the secondary index + CI on the NRMSE line
    assert any(t.startswith(f"{res.sec_label}=") and "[" in t for t in bold)


def test_all_figures_build_and_save(result, tmp_path):
    res, cfg = result
    for name, fig in [("match", fig_match(res, cfg, "test run")),
                      ("cdf", fig_cdf(res, cfg)),
                      ("series", fig_series(res, cfg)),
                      ("comb", fig_combined(res, cfg))]:
        for ext in ("png", "pdf", "jpg", "eps", "tif"):
            save_figure(fig, tmp_path / f"{name}.{ext}", dpi=100)
            assert (tmp_path / f"{name}.{ext}").stat().st_size > 0


def test_run_evaluation_outputs(tmp_path):
    cfg = FitevalConfig(n_resamples=5000)
    art = run_evaluation(_data(), "sample.in", tmp_path, cfg, fig_ext="png",
                         fig_text="demo", rng=np.random.default_rng(2))
    expected = {"sample_out.txt", "sample_out.png", "sample.pdf",
                "sample.png", "sample_cdf.png", "sample_ds.png",
                "sample_cb.png"}
    assert {p.name for p in art.files} == expected
    for p in art.files:
        assert p.exists() and p.stat().st_size > 0
    txt = art.report_txt.read_text()
    assert "GOODNESS-OF-FIT EVALUATION" in txt


def test_run_evaluation_u_suffix(tmp_path):
    cfg = FitevalConfig(n_resamples=5000)
    art = run_evaluation(_data(), "sample.in", tmp_path, cfg, suffix="U",
                         rng=np.random.default_rng(2))
    assert art.combined_png.name == "sampleU_out.png"
    assert art.report_txt.name == "sampleU_out.txt"


def test_delete_output_files(tmp_path):
    cfg = FitevalConfig(n_resamples=5000)
    (tmp_path / "sample.in").write_text("1 2\n")
    (tmp_path / "sample.err").write_text("0.1\n")
    run_evaluation(_data(), "sample.in", tmp_path, cfg,
                   rng=np.random.default_rng(3))
    n = delete_output_files(tmp_path, "sample.in")
    assert n == 3
    remaining = {p.name for p in tmp_path.iterdir()}
    assert remaining == {"sample.in", "sample.err"}


def test_report_file_keeps_the_diagnostic_on_one_line():
    """The figure breaks the mismatch text; the report file joins it back,
    as the desktop does at L4017."""
    import numpy as np

    from fiteval_core.config import FitevalConfig
    from fiteval_core.engine import evaluate_case, prepare_case
    from fiteval_core.report import numerical_report

    x = np.linspace(0, 4 * np.pi, 100)
    yobs = np.sin(x)
    yprd = 0.80 * yobs + np.random.default_rng(0).normal(0, 0.40, x.size)
    res = evaluate_case(prepare_case(np.column_stack([yobs, yprd]), "t.in"),
                        FitevalConfig())
    assert "\n" in res.imbalance_txt                      # broken for the figure
    hits = [ln for ln in numerical_report(res).splitlines() if "mismatch:" in ln]
    assert len(hits) == 1                                 # but one line in the file
    assert hits[0].strip().endswith("and underestimated")
