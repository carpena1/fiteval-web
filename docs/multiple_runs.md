# Multiple runs (batch mode)

The **Multiple runs** dialog evaluates several data files in one pass and
writes a single summary table (`<list>_summary.csv`) with one row per run,
plus all the individual figures and reports. It reproduces the desktop
FITEVAL multi-run mode.

Each run is described by two fields:

| Field | Meaning |
|-------|---------|
| **File Name** | `datafile.in` optionally followed by `norep` and a free-text figure label. |
| **Option** | how to treat measurement uncertainty for that run (see below). |

## Two ways to fill the table

### 1. Load a list file (recommended)

Prepare a plain-text list file (extension `.txt`, `.cf`, `.mr` or `.lst`)
with **one run per line** in the form:

```
datafile [norep] label ; option
```

Everything **before** the first `;` (or `,`) is the *File Name* field;
everything **after** it is the *Option* field. The label is optional and is
printed on the run's figure. A complete, ready-to-run example ships in the
repo as [`examples/multi_run_test.txt`](../examples/multi_run_test.txt),
together with every `.in`/`.err` file it references:

```
data_ex1.in Good model fit; 0
data_ex2.in Outlier detected; 0
data_ex3.in norep Repeated values removed; 0
data_ex0.in Acceptable model fit; 0
data_ex0a.in Obs. uncertainty (CF method); 3 9 oN 17
data_ex0b.in Model uncertainty (CF method); 4 13 pT 10 20
data_ex0c.in Obs. & Model uncertainty (CF method); 3 11 oT 25 25 pT 15 20
data_ex0d.in CF method (common PER); 0.20
data_ex0e.in CF method (indiv. symmetric PER);2 data_ex0_PER.err
data_ex0f.in CF method (indiv. symmetric errors);2 data_ex0_UBs_sym.err
data_ex0g.in CF method (indiv. asymmetric errors);2 data_ex0_UBs_asym.err
data_ex0h.in PER method (indiv. symmetric PER);1 data_ex0_PER.err
data_ex0i.in PER method (indiv. symmetric errors);1 data_ex0_UBs_sym.err
data_ex0j.in PER method (indiv. asymmetric errors);1 data_ex0_UBs_asym.err
```

Reproduce it from the command line (writes `multi_run_test_summary.csv` and
every per-run output into `examples/`):

```bash
python -m fiteval_core examples/multi_run_test.txt --multi
```

Or, in the web GUI:

Click **Load list / data / error files…** and select the list file
**together with** every data (`.in`) and error (`.err`) file it references —
they all upload at once and the table fills automatically. Then click
**Run all**.

### 2. Fill the table by hand

Click **Add row** for each run, type the data file name into *File Name*
and the option into *Option*, and upload the referenced `.in`/`.err` files
with the same **Load…** button (any file that is not a list file is just
stored in the workspace so the runs can find it).

## Option field reference

| Option | Uncertainty method |
|--------|--------------------|
| `0` | none (deterministic run) |
| `0 < value < 1` | common probable-error range (PER) applied to every observation, e.g. `0.25` |
| `1 file.err` | error-data file, PER per point (1 column) or lower/upper error lengths (2 columns), applied with the *bounds* method |
| `2 file.err` | same error-data file, applied with the *correction-factor* (CF) method |
| `3 <case> o<D> v1 [v2] [p<D> v1 [v2]]` | CF from distributions, observation and/or **prediction** uncertainty |
| `4 <case> p<D> v1 [v2]` | CF from distributions, prediction (model) uncertainty only |

Where:

- **`<case>`** is the FITEVAL case number. For option `3` use a case in
  9–12; for option `4` use 13 or 14. Even case numbers require a benchmark
  (3rd) column in the data file; odd case numbers ignore it.
- **`o…`** describes **observation** uncertainty, **`p…`** describes
  **prediction** uncertainty.
- **`<D>`** is the distribution: `N` Normal, `L` Lognormal, `T` Triangular,
  `U` Uniform.
- **`v1 [v2]`** are the distribution values. For Normal/Lognormal give one
  value, the coefficient of variation CV(%). For Triangular/Uniform give the
  lower and upper bound lengths as a percentage, e.g. `oT 25 25`.

Examples:

- `3 9 oN 17` — observation uncertainty, Normal, CV = 17 %.
- `4 13 pT 10 20` — prediction uncertainty, Triangular, −10 % / +20 %.
- `3 11 oT 25 25 pT 15 20` — both observation (Triangular ±25 %) and
  prediction (Triangular −15 % / +20 %) uncertainty.

## Output

**Run all** writes, in the session workspace:

- `<datafile>_out.txt`, `<datafile>_out.png` and `<datafile>.pdf` for every
  run (with a `U` suffix, e.g. `<datafile>U_out.txt`, for the
  with-uncertainty version when an uncertainty option is used);
- `<list>_summary.csv` — one row per run (see the two-section layout below).

Use **Download summary CSV** for the table alone or **Download all results
(zip)** for everything. The *Logs* column reports `OK` (or the reason a run
failed) for each row.

## Summary table layout

The summary has two banded sections plus a common tail:

- **No Unc.** (always present) — the deterministic evaluation of every run:
  the two efficiency indices with their 95 % CIs (NSE and KGE* by default;
  E1 replaces NSE if E1 is selected, KGE replaces KGE* if KGE is selected),
  RMSE and its CI, NRMSE, p-value, threshold and the **Indicator** (the
  Configuration-selected main index).
- **With Unc.** (only when at least one row carries an uncertainty option) —
  because an uncertainty run is performed *in addition to* the deterministic
  one. It reports the uncertainty run's index (see below) with its CI, RMSE
  and CI, NRMSE, p-value, threshold and Indicator. Rows without an
  uncertainty option show `--` here.
- **Tail**: Bias, Outlier, N (from the deterministic run).

The main index and class limits come from the **Configuration** dialog —
click **Done** there to save the selection before running.

One rule is inherited from the evaluation method: when the configured index
is KGE* or KGE, the **With Unc.** run is evaluated with **NSE** (the
measurement-uncertainty methods are defined on NSE), and it is classified
against the NSE-scale class limits — so its threshold shows the NSE value
(e.g. 0.65) while the No-Unc threshold shows the KGE*/KGE value (e.g. 0.73).
The *Indicator* column of each section states which index that section used.

## Example summary

Two runs from `multi_run_test.txt` with **KGE\*** selected in Configuration —
a deterministic run (option `0`) and an observation-uncertainty run
(`3 9 oN 17`). The first fills only the **No Unc.** section (the **With Unc.**
columns show `--`); the second fills both, and its **With Unc.** *Indicator*
is `NSE` with the NSE-scale threshold `0.65`, versus `KGE*`/`0.73` in the
No-Unc section:

```
,,No Unc.,No Unc.,No Unc.,No Unc.,No Unc.,No Unc.,No Unc.,No Unc.,No Unc.,No Unc.,No Unc.,With Unc.,With Unc.,With Unc.,With Unc.,With Unc.,With Unc.,With Unc.,With Unc.,,,
Case,Option,NSE,NSE 95%CI,KGE*,KGE* 95%CI,RMSE,RMSE 95%CI,NRMSE,Indicator,p-value,threshold,Indicator,NSE,NSE 95%CI,RMSE,RMSE 95%CI,NRMSE,p-value,threshold,Indicator,Bias,Outlier,N
data_ex1.in Good model fit,0,0.857,[0.717 - 0.933],0.888,[0.811 - 0.965],0.02,[0.020 - 0.030],37%,KGE*,0.055,0.73,KGE*,--,,--,,--,--,--,--,3.20%,No,24
data_ex0a.in Obs. uncertainty (CF method),3 9 oN 17,0.718,[0.520 - 0.838],0.828,[0.794 - 0.889],0.61,[0.480 - 0.750],53%,KGE*,0.1,0.73,KGE*,0.816,[0.643 - 0.910],0.49,[0.360 - 0.660],42%,0.131,0.65,NSE,1.80%,No,48
```

Bootstrap CIs and p-values differ slightly from run to run (different RNG
draws) unless a seed is fixed. If only deterministic rows are present the
**With Unc.** section is omitted entirely; if every row carries an
uncertainty option, both sections are always populated.
