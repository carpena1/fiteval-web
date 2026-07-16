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
printed on the run's figure. Example (`multi_run_test.txt`):

```
data_ex1.in Noisy fit ; 0
data_ex4.in Very good model fit ; 0
data_ex2.in Obs. uncertainty (CF method with PER) ; 0.25
data_ex3.in norep Remove repeated ; 0
data_ex0.in Obs. uncertainty (CF method) ; 3 9 oN 17
data_ex0a.in Model uncertainty (CF method) ; 4 13 pT 10 20
data_ex0b.in Obs. & Model uncertainty (CF method) ; 3 11 oT 25 25 pT 15 20
data_ex0c.in PER method (indiv. symmetric PER) ; 1 data_ex0_PER.err
data_ex0d.in PER method (indiv. asymmetric errors) ; 1 data_ex0_UBs.err
data_ex0e.in CF method (indiv. symmetric PER) ; 2 data_ex0_PER.err
data_ex0f.in CF method (indiv. asymmetric errors) ; 2 data_ex0_UBs.err
```

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
