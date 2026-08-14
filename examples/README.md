# Example data

A complete, self-contained multi-run batch. Everything the list file
references lives in this folder, so it reproduces straight after a clone.

## Run it

```bash
python -m fiteval_core examples/multi_run_test.txt --multi
```

This writes `multi_run_test_summary.csv` (the two-section batch summary) plus
`<name>_out.txt`, `<name>_out.png` and `<name>.pdf` for every run — and the
`<name>U_*` with-uncertainty twins for the rows that carry an uncertainty
option — into this directory. Those generated outputs are git-ignored; only
the inputs below are tracked.

The same list file also loads in the web GUI: **Multiple runs → Load list /
data / error files…**, select `multi_run_test.txt` together with all the
`.in`/`.err` files, then **Run all**. See
[`../docs/multiple_runs.md`](../docs/multiple_runs.md) for the option-string
reference and the summary-table layout.

## Files

| File | Role |
|------|------|
| `multi_run_test.txt` | the batch list — 14 rows, one per line: `datafile [norep] label ; option` |
| `data_ex1.in`, `data_ex2.in`, `data_ex3.in`, `data_ex0.in` | deterministic runs (option `0`) — good fit, outlier, repeated-values (`norep`), acceptable fit |
| `data_ex0a.in` … `data_ex0j.in` | the same base case run under every measurement-uncertainty option (CF-from-distribution, common PER, error-file CF and PER, symmetric/asymmetric) |
| `data_ex0_PER.err` | per-point probable-error range (1 column) |
| `data_ex0_UBs_sym.err`, `data_ex0_UBs_asym.err` | lower/upper error-bound lengths (2 columns), symmetric and asymmetric |

Each `.in` file is whitespace-separated `[Yobs Yprd]` (or `[Yobs Yprd
Ybenchmark]`). Each `.err` file has one row per data point.
