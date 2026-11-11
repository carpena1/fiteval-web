"""The MATLAB-reference remapper (scripts/remap_matlab_refs.py).

References look like L1234 or L1234-1256, so the fixtures use line numbers
of that size; the pattern ignores one-digit numbers on purpose.
"""

import importlib.util
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "scripts" / "remap_matlab_refs.py"
_spec = importlib.util.spec_from_file_location("remap_matlab_refs", _SRC)
remap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(remap)

_M = "".join(f"line {i}\n" for i in range(1, 201))     # 200-line fake .m


def _project(tmp_path, py_text, old_m=_M, new_m=None):
    (tmp_path / "fiteval_core").mkdir(exist_ok=True)
    src = tmp_path / "fiteval_core" / "mod.py"
    src.write_text(py_text, encoding="utf-8")
    old, new = tmp_path / "old.m", tmp_path / "new.m"
    old.write_text(old_m, encoding="utf-8")
    new.write_text(old_m if new_m is None else new_m, encoding="utf-8")
    return src, old, new


def test_shifts_references_past_an_insertion(tmp_path):
    src, old, new = _project(tmp_path, "# port of foo (L105) and bar (L107-109)\n",
                             new_m="added\nadded\n" + _M)
    assert remap.main([str(old), str(new), "--apply", "--root", str(tmp_path)]) == 0
    assert src.read_text(encoding="utf-8") == \
        "# port of foo (L107) and bar (L109-111)\n"


def test_reference_before_an_insertion_does_not_move(tmp_path):
    new_m = _M.replace("line 150\n", "line 150\nadded\n")
    src, old, new = _project(tmp_path, "# foo (L100) bar (L160)\n", new_m=new_m)
    remap.main([str(old), str(new), "--apply", "--root", str(tmp_path)])
    assert src.read_text(encoding="utf-8") == "# foo (L100) bar (L161)\n"


def test_dry_run_writes_nothing(tmp_path, capsys):
    src, old, new = _project(tmp_path, "# foo (L105)\n", new_m="added\n" + _M)
    assert remap.main([str(old), str(new), "--root", str(tmp_path)]) == 0
    assert src.read_text(encoding="utf-8") == "# foo (L105)\n"
    assert "Nothing written" in capsys.readouterr().out


def test_identical_files_are_a_no_op(tmp_path):
    src, old, new = _project(tmp_path, "# foo (L105-108)\n")
    remap.main([str(old), str(new), "--apply", "--root", str(tmp_path)])
    assert src.read_text(encoding="utf-8") == "# foo (L105-108)\n"


def test_rewritten_line_is_estimated_and_reported(tmp_path, capsys):
    new_m = _M.replace("line 105\n", "line 105 rewritten\n")
    src, old, new = _project(tmp_path, "# foo (L105)\n", new_m=new_m)
    remap.main([str(old), str(new), "--apply", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "1 estimated" in out and "Check these by hand" in out


def test_reference_past_end_of_old_file_is_left_alone(tmp_path, capsys):
    src, old, new = _project(tmp_path, "# foo (L900)\n",
                             old_m="line 1\nline 2\n", new_m="line 1\nline 2\n")
    assert remap.main([str(old), str(new), "--apply",
                       "--root", str(tmp_path)]) == 1      # needs a human
    assert src.read_text(encoding="utf-8") == "# foo (L900)\n"
    assert "past the end" in capsys.readouterr().out


def test_missing_file_is_reported(tmp_path):
    assert remap.main([str(tmp_path / "nope.m"), str(tmp_path / "also.m")]) == 2
