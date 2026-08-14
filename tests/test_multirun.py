import numpy as np
import pytest

from fiteval_core.config import FitevalConfig
from fiteval_core.dataio import write_in_file
from fiteval_core.multirun import (option_to_spec, parse_file_field,
                                   parse_list_file, run_multi)
from fiteval_core.uncertainty import UncError


def _write_data(path, n=30, seed=5, bench=False):
    rng = np.random.default_rng(seed)
    yobs = 10 + 3 * np.sin(np.linspace(0, 4 * np.pi, n)) + rng.normal(0, 0.4, n)
    yprd = yobs + rng.normal(0, 0.5, n)
    cols = [yobs, yprd]
    if bench:
        cols.append(np.full(n, yobs.mean()))
    write_in_file(np.column_stack(cols), path)
    return n


def test_parse_file_field():
    assert parse_file_field("a.in") == ("a.in", False, "")
    assert parse_file_field("a.in norep") == ("a.in", True, "")
    assert parse_file_field("a.in NOREP run 1") == ("a.in", True, "run 1")
    assert parse_file_field("a.in my label") == ("a.in", False, "my label")


def test_option_none_and_per(tmp_path):
    assert option_to_spec("0", tmp_path) == (None, None)
    spec, case = option_to_spec("0.2", tmp_path)
    assert spec.method == "per_mixed" and spec.per == 0.2 and case is None


def test_option_errfile(tmp_path):
    (tmp_path / "e.err").write_text("0.1\n0.2\n")
    spec, _ = option_to_spec("1 e.err", tmp_path)
    assert spec.method == "errfile" and spec.err_data.shape == (2, 1)
    assert spec.err_as_cf is False
    # option '2' forces the CF method (MR_MixedMethod=1)
    spec2, _ = option_to_spec("2 e.err", tmp_path)
    assert spec2.method == "errfile" and spec2.err_as_cf is True
    with pytest.raises(UncError, match="provide error file name"):
        option_to_spec("1", tmp_path)
    with pytest.raises(UncError, match="not found"):
        option_to_spec("2 missing.err", tmp_path)


def test_option2_errfile_uses_cf_on_2col_data():
    # option '1' -> bounds method (meas 1); option '2' -> CF method (meas 3)
    from fiteval_core.uncertainty import UncSpec, prepare_unc_cases
    data = np.column_stack([np.linspace(1, 5, 6), np.linspace(1.1, 4.8, 6)])
    err = np.full((6, 1), 0.1)
    b_case, _ = prepare_unc_cases(data, UncSpec(method="errfile", err_data=err))
    cf_case, _ = prepare_unc_cases(
        data, UncSpec(method="errfile", err_data=err, err_as_cf=True))
    assert b_case.meas_unc == 1.0
    assert cf_case.meas_unc == 3.0


def test_parse_list_file():
    text = ("data_ex1.in Noisy fit ; 0\n"
            "data_ex3.in norep Remove repeated ; 0\n"
            "data_ex0.in Obs. uncertainty (CF) ; 3 9 oN 17\n"
            "data_ex0c.in PER method , 1 data_ex0_PER.err\n"
            "\n"
            "data_bare.in\n")
    rows = parse_list_file(text)
    assert rows[0] == ("data_ex1.in Noisy fit", "0")
    assert rows[1] == ("data_ex3.in norep Remove repeated", "0")
    assert rows[2] == ("data_ex0.in Obs. uncertainty (CF)", "3 9 oN 17")
    # a comma is accepted as the separator too (MATLAB strrep ',' -> ';')
    assert rows[3] == ("data_ex0c.in PER method", "1 data_ex0_PER.err")
    # blank line skipped; a line with no separator -> option '0'
    assert rows[4] == ("data_bare.in", "0")


def test_option_cf(tmp_path):
    spec, case = option_to_spec("3 11 oN 10 pL 20", tmp_path)
    assert (spec.method, spec.obs_dist, spec.prd_dist) == ("cf", 1, 2)
    assert (spec.cvo, spec.cvp, case) == (10.0, 20.0, 11)
    with pytest.raises(UncError, match="not compatible"):
        option_to_spec("3 13 pN 10", tmp_path)
    with pytest.raises(UncError, match="Invalid option"):
        option_to_spec("7 nonsense", tmp_path)


def test_run_multi_batch(tmp_path):
    _write_data(tmp_path / "a.in", seed=1)
    _write_data(tmp_path / "b.in", seed=2)
    _write_data(tmp_path / "c.in", seed=3)
    (tmp_path / "c.err").write_text("\n".join(["0.05"] * 30) + "\n")
    cfg = FitevalConfig(n_resamples=5000)
    rows = [("a.in", "0"), ("b.in", "0.15"), ("c.in", "1 c.err"),
            ("missing.in", "0")]
    out = run_multi(rows, tmp_path, cfg, "mylist.cf",
                    rng=np.random.default_rng(9))
    assert len(out.logs) == 4
    assert out.logs[0] == "OK" and out.logs[1] == "OK" and out.logs[2] == "OK"
    assert "not found" in out.logs[3]
    assert out.summary_path.name == "mylist_summary.csv"
    lines = out.summary_path.read_text().splitlines()
    # row 0 = section band, row 1 = column labels, then one row per success
    assert lines[0].startswith(",,No Unc.")
    assert "With Unc." in lines[0]          # b/c carry uncertainty
    assert lines[1].startswith(
        "Case,Option,NSE,NSE 95%CI,KGE*,KGE* 95%CI,RMSE,RMSE 95%CI,NRMSE,"
        "p-value,threshold,Indicator,NSE,NSE 95%CI,RMSE,RMSE 95%CI,NRMSE,"
        "p-value,threshold,Indicator,Bias,Outlier,N")
    assert len(lines) == 5  # band + header + 3 successful rows
    assert lines[2].startswith("a.in,0,")
    assert lines[3].startswith("b.in,0.15,")
    # a.in has no uncertainty: its With-Unc value cells are "--"
    assert lines[2].split(",")[12] == "--"
    # uncertainty rows produce U-suffixed outputs too
    assert (tmp_path / "bU_out.png").exists()
    assert (tmp_path / "cU_out.txt").exists()
    assert (tmp_path / "a_out.txt").exists()


def test_no_unc_only_omits_with_section(tmp_path):
    """A list with no uncertainty options has no 'With Unc.' section."""
    _write_data(tmp_path / "a.in", seed=1)
    _write_data(tmp_path / "b.in", seed=2)
    cfg = FitevalConfig(n_resamples=5000)
    out = run_multi([("a.in", "0"), ("b.in", "0")], tmp_path, cfg,
                    rng=np.random.default_rng(9))
    lines = out.summary_path.read_text().splitlines()
    assert "With Unc." not in lines[0]
    assert lines[1].endswith("threshold,Indicator,Bias,Outlier,N")
    assert len(lines[1].split(",")) == 15  # 2 + 10 + 3


def test_run_multi_norep_and_text(tmp_path):
    n = _write_data(tmp_path / "d.in", seed=4)
    import numpy as np
    data = np.loadtxt(tmp_path / "d.in")
    write_in_file(np.vstack([data, data[5]]), tmp_path / "d.in")
    cfg = FitevalConfig(n_resamples=5000)
    out = run_multi([("d.in norep trial 7", "0")], tmp_path, cfg,
                    rng=np.random.default_rng(10))
    assert "repeated case was removed" in out.logs[0]


def test_kge_star_config_two_section_summary(tmp_path):
    """KGE* config: No-Unc section reports NSE & KGE* with the KGE*-scale
    threshold (0.73); the with-uncertainty run is reported under NSE with the
    NSE-scale threshold (0.65)."""
    _write_data(tmp_path / "a.in", seed=1)
    _write_data(tmp_path / "b.in", seed=2)
    cfg = FitevalConfig(gof_index=2, class_lim=(0.73, 0.85, 0.93),
                        n_resamples=5000)
    out = run_multi([("a.in", "0"), ("b.in", "3 9 oN 17")], tmp_path, cfg,
                    rng=np.random.default_rng(3))
    hdr = out.header
    assert hdr[2] == "NSE" and hdr[4] == "KGE*"        # No-Unc value columns
    assert hdr[10] == "threshold" and hdr[11] == "Indicator"
    assert hdr[12] == "NSE" and hdr[19] == "Indicator"  # With-Unc block
    rows = out.summary_path.read_text().splitlines()
    a = rows[2].split(",")   # no-unc row
    b = rows[3].split(",")   # uncertainty row
    assert a[11] == "KGE*" and a[10] == "0.73"          # No-Unc: KGE*, 0.73
    assert a[12] == "--"                                # a.in: blank With-Unc
    assert b[19] == "NSE" and b[18] == "0.65"           # With-Unc: NSE, 0.65


def test_kge_and_e1_relabel_columns(tmp_path):
    """KGE selection puts KGE in the 2nd index column; E1 selection puts E1
    in the 1st (user-specified column logic)."""
    _write_data(tmp_path / "a.in", seed=1)
    kge = run_multi([("a.in", "0")], tmp_path,
                    FitevalConfig(gof_index=3, class_lim=(0.73, 0.85, 0.93),
                                  n_resamples=5000),
                    rng=np.random.default_rng(3))
    assert kge.header[2] == "NSE" and kge.header[4] == "KGE"
    e1 = run_multi([("a.in", "0")], tmp_path,
                   FitevalConfig(gof_index=4, n_resamples=5000),
                   rng=np.random.default_rng(3))
    assert e1.header[2] == "E1" and e1.header[4] == "KGE*"


def test_cli_multi(tmp_path, capsys):
    """`python -m fiteval_core --multi list.txt` writes the two-section CSV."""
    from fiteval_core.__main__ import main

    _write_data(tmp_path / "a.in", seed=1)
    _write_data(tmp_path / "b.in", seed=2)
    (tmp_path / "runs.txt").write_text(
        "a.in Deterministic ; 0\n"
        "b.in Obs. uncertainty ; 3 9 oN 17\n")

    rc = main([str(tmp_path / "runs.txt"), "--multi", "--seed", "3"])
    assert rc == 0

    summary = tmp_path / "runs_summary.csv"
    assert summary.is_file()
    lines = summary.read_text().splitlines()
    assert lines[0].startswith(",,No Unc.") and "With Unc." in lines[0]
    assert lines[3].split(",")[19] == "NSE"      # forced-NSE With-Unc row

    out = capsys.readouterr().out
    assert "a.in: OK" in out and "b.in: OK" in out
    assert "runs_summary.csv" in out


def test_cli_multi_empty_list(tmp_path, capsys):
    from fiteval_core.__main__ import main

    (tmp_path / "empty.txt").write_text("\n  \n")
    assert main([str(tmp_path / "empty.txt"), "--multi"]) == 1
    assert "No runs found" in capsys.readouterr().err
