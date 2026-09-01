"""Text IO must pin UTF-8, not inherit the locale code page.

The report carries the Greek rho/alpha of the timing/amplitude diagnostic,
which a legacy Windows code page (cp1252 on Spanish/Western installs, cp850
in consoles) cannot encode -- writing it with the default encoding raised
UnicodeEncodeError on a Spanish Windows host.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np

from fiteval_core.config import FitevalConfig, read_config, write_config
from fiteval_core.dataio import write_in_file
from fiteval_core.indices import gof_indexes, kge_nse_imbalance


def test_report_with_greek_round_trips(tmp_path):
    """A report line containing rho/alpha survives write -> read as UTF-8."""
    x = np.linspace(0, 4 * np.pi, 100)
    yobs, yprd = np.sin(x), 0.3 * np.sin(x)
    yben = np.full_like(yobs, yobs.mean())
    idx = gof_indexes(yobs, yprd, yben, yobs - yprd, 2)
    txt = kge_nse_imbalance(yobs, yprd, idx[1], idx[2])
    assert "ρ" in txt and "α" in txt

    p = tmp_path / "r_out.txt"
    p.write_text(txt, encoding="utf-8")
    p.read_bytes().decode("utf-8")          # valid UTF-8, not a locale page
    assert p.read_text(encoding="utf-8") == txt


def test_no_default_encoding_io(tmp_path):
    """No fiteval module opens a text file without an explicit encoding.

    Runs the CLI under -X warn_default_encoding, which makes CPython emit an
    EncodingWarning at every locale-dependent open()/read_text()/write_text().
    Third-party warnings (matplotlib's font cache) are ignored.
    """
    write_in_file([[1.0, 1.1], [2.0, 1.8], [3.0, 3.3], [4.0, 3.7],
                   [5.0, 5.2], [6.0, 5.6], [7.0, 7.4], [8.0, 7.9]],
                  tmp_path / "d.in")
    write_config(FitevalConfig(n_resamples=5000, dpi=72),
                 tmp_path / "fitevalconfig.txt")

    proc = subprocess.run(
        [sys.executable, "-X", "warn_default_encoding",
         "-W", "always::EncodingWarning", "-m", "fiteval_core",
         str(tmp_path / "d.in"), "--config",
         str(tmp_path / "fitevalconfig.txt"), "--seed", "1"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent)

    assert proc.returncode == 0, proc.stderr
    offenders = [ln for ln in proc.stderr.splitlines()
                 if "EncodingWarning" in ln
                 and ("fiteval_core" in ln or "fiteval_app" in ln)]
    assert not offenders, "locale-dependent text IO:\n" + "\n".join(offenders)


def test_config_round_trips_as_utf8(tmp_path):
    p = tmp_path / "fitevalconfig.txt"
    cfg = FitevalConfig(marker="r*", dpi=150)
    write_config(cfg, p)
    p.read_bytes().decode("utf-8")
    assert read_config(p) == cfg


def test_config_with_cp1252_comment_still_parses(tmp_path):
    """A config edited in Notepad on a Spanish Windows box must not crash."""
    p = tmp_path / "fitevalconfig.txt"
    text = (
        "0.65 %Umbral aceptable\n0.80 %Bueno\n0.90 %Muy bueno\n"
        "5 %Sesgo\n1 %Indice principal\n0 20000 % Remuestreo\n"
        "10 % Tamano de letra\n1 % Sin salida grafica\n"
        "0 % Incertidumbre en las observaciones (a\xf1o)\n"
        "bo % Color y simbolo\n5 % Tamano del simbolo\n100 % Resolucion\n"
    )
    p.write_bytes(text.encode("cp1252"))    # not valid UTF-8
    cfg = read_config(p)
    assert cfg.class_lim == (0.65, 0.80, 0.90)
    assert cfg.marker == "bo" and cfg.dpi == 100
