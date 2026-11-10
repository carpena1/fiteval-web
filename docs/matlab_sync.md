# MATLAB sync — `FITEVAL_GUI.m` v4.0 and the Python port

This file shows where the desktop program and the Python port still differ.
It also gives the changes to make in the desktop source.

- Desktop source:
  `FITEVAL_GUI_src/FITEVAL_GUI_Installer_files/FITEVAL_GUI.m`, version 4.0
  (27 Oct 2026), with the CF fix of 9 Nov 2026 applied.
- Python port: `fiteval_core`.
- Line numbers come from that desktop file. They move when you edit it, so
  check each one before you change the code.
- Checked on 2026-11-10.

An earlier version of this file listed three gaps, A, B and C. Version 4.0
closed gap A and most of gap B. That older text is gone. Use the table below.

## Status

| Item | Desktop v4.0 | Python port | Action |
|------|--------------|-------------|--------|
| E1 threshold conversion | done, L313 | done | none |
| Two-section summary layout | done, L991–L1029 | done | none |
| Summary band row | **one column out**, L1002 | correct | fix the desktop |
| Column order in each block | Indicator before p-value | Indicator last | choose one |
| Force NSE for the uncertainty pass | **missing** | done | fix the desktop |
| CF from an external error file | done, L3041 | done | test the desktop |
| `computeCF` 0/0 guard | done, L5315 | done | test the desktop |
| Correlation/variability text | v4.0 text, L3476 | follows v4.0 | none |
| Greek letters in the report file | writes `rho`, `alpha` | writes ρ, α | cosmetic |
| 2026 reference in About | done, L184–L262 | done | check the window |

---

## Open 1 — the summary band row is one column out

The summary file has 23 columns. The first row is the band row. It says which
columns hold the run without measurement uncertainty, and which hold the run
with it.

The data sits like this:

| Columns | Content |
|---------|---------|
| 1–2 | Case, Option |
| 3–12 | run **without** uncertainty (10 columns) |
| 13–20 | run **with** uncertainty (8 columns) |
| 21–23 | Bias, Outlier, N |

The code proves it:

- L3335–L3342 fills `NUMOUT{1..10}` from the run without uncertainty, and
  `NUMOUT{19,20,21}` from the last three values of that same run.
- L3309–L3312 fills `NUMOUT{11,12}` and `NUMOUT{13..18}` from the run with
  uncertainty.
- L998 puts Case and Option in front. So `NUMOUT{k}` becomes column `k+2`.

The band row at L1002 says something different:

```matlab
UNCCONDLBL=cell(1,21); UNCCONDLBL(:)={''};
UNCCONDLBL(3:11)={'No Unc.'};UNCCONDLBL(12:20)={'With Unc.'};
```

Column 12 holds the threshold of the run **without** uncertainty. The band row
marks it "With Unc.". Every label in the second block is one column early. The
cell is also too short: it holds 21 entries for a 23-column header.

Replace both lines with:

```matlab
UNCCONDLBL=cell(1,23); UNCCONDLBL(:)={''};
UNCCONDLBL(3:12)={'No Unc.'}; UNCCONDLBL(13:20)={'With Unc.'};
```

The header row itself (L1004–L1029) is correct. Only the band row is wrong.

---

## Open 2 — force NSE for the uncertainty pass

When the user selects KGE* or KGE, the port evaluates the uncertainty run as
NSE, against NSE-scale class limits. The desktop does not do this.

The desktop swaps columns instead, at L991–L996:

```matlab
if strcmp(indexlabel{1},'KGE*') || strcmp(indexlabel{1},'KGE')
    NUMOUT=[NUMOUT(:,3:4) NUMOUT(:,1:2) NUMOUT(:,5:end)];
    idx1lbl=indexlabel{2}; idx2lbl=indexlabel{1};
```

The swap moves columns 1–4 only. `NUMOUT(:,5:end)` keeps columns 11 and 12
where they are, and those two columns carry the main index of the uncertainty
run. The result:

- Columns 3–6 read NSE, then KGE. This is correct.
- Columns 13–14 still hold the **KGE** value of the uncertainty run. The
  header calls them `idx1lbl`, which the swap has just set to NSE. The label
  does not match the number.

To fix it, force the index around the uncertainty run. Replace L3307:

```matlab
   OUTP=fitevaluation(Yobs,Yprd,Yben,GoF_Index_Flag,repeated_cases,handles);
```

with:

```matlab
   fFlag=GoF_Index_Flag; fCL=CLASSLIM;          % save
   if GoF_Index_Flag==2 || GoF_Index_Flag==3    % KGE*/KGE -> NSE
     GoF_Index_Flag=1;
     CLASSLIM=0.5*(sqrt(2)-(1-CLASSLIM)).^2;    % KGE scale -> NSE scale
   end
   OUTP=fitevaluation(Yobs,Yprd,Yben,GoF_Index_Flag,repeated_cases,handles);
   GoF_Index_Flag=fFlag; CLASSLIM=fCL;          % restore
```

`CLASSLIM` is global (L529, and again inside `fitevaluation` at L3377).
`GoF_Index_Flag` is global as well, but `fitevaluation` also takes it as an
argument, so the call above passes the forced value.

An NSE or E1 configuration needs no forcing. The uncertainty run already
reports NSE or E1 there.

---

## Choose one — column order inside each block

Both programs put the same ten values in the block without uncertainty, and
the same eight in the block with it. They order the last three differently.

| Position in block | Desktop v4.0 (L3767–L3779) | Python port |
|-------------------|----------------------------|-------------|
| 8 | Indicator | p-value |
| 9 | p-value | threshold |
| 10 | threshold | Indicator |

Each program is correct on its own: in both, the header matches the data. But
a file written by one does not load into a reader built for the other.

The desktop format is the reference, so the port should follow v4.0. In
`fiteval_core/multirun.py`, move `primary` and `label` before the p-value in
`_no_unc_cells` and `_with_unc_cells`, and move `"Indicator"` to match in the
two header lists. `_WITH_UNC_BLANK` needs no change, because its last three
entries are all `--`.

---

## Already in sync

**E1 threshold conversion** (L313–L343). v4.0 converts the three class limits
between all four scales, and pivots every conversion through NSE. It converts
E1 to KGE in one step, so no rounding happens in between.

**Two-section summary layout** (L991–L1029, L3309–L3342). v4.0 runs each case
twice, keeps both results, and writes the two blocks described above. Only the
band row and the column order still need attention.

**CF from an external error file** (L3041). An error file with two columns
gives a lower and an upper bound length that differ, so the uniform
distribution around the observation is not symmetric and `CDF(O)` is not 0.5.
Both programs used to divide by a constant 0.5 anyway, which pushed
`CF/CFmax` outside the range 0 to 1. Both now take `CFmax` on the side where
the prediction lies: `F(O)` below the observation and `1 - F(O)` above it.
This is the rule `computeCF` already used for the triangular and uniform
distributions (L5292). Only two-column error files change.

**`computeCF` 0/0 guard** (L5315). When the observation sits exactly on a
bound, `CFmax` is 0 and the division gives 0/0. A prediction outside the
bounds now gets `CF/CFmax = 1`, which is the limit of the ratio.

**Second reference in the About box.** Both programs now list the 2013 and
the 2026 papers, each with its own DOI link. In the desktop the About
window grew by 60 px and the text block starts 60 px higher, so the older
lines keep their place. The disabled 2015 slot was renamed `ref3` and
`OpenURL3`, because `ref2` and `OpenURL2` now hold the 2026 link. Nobody
has seen this window on screen yet, so open it once in MATLAB.

**Correlation/variability text** (L3476–L3512). v4.0 replaced the older
"Timing ... amplitude ..." wording with four classes, and dropped the
`rho > 0.6` condition. The port follows the v4.0 text and classes. v4.0 also
hides the text when measurement uncertainty is on, and the port does the same.

---

## Cosmetic difference

The desktop writes the diagnostic twice. The figure gets TeX markup, which
draws Greek letters. The report file gets the same string with the backslashes
removed (L4017), so the file reads `rho` and `alpha`. The port writes the
Greek letters in both places. The numbers are identical. Change the port only
if you compare the two report files character by character.

---

## Test the desktop before you trust it

The two CF changes of 9 Nov 2026 were written without MATLAB on hand. Their
logic was checked by copying the patched block into Python and comparing it
with the port over 5000 random cases, which matched exactly. The MATLAB
**syntax** was never executed. Run one case with a two-column error file
before you rely on it. The file before those two changes is kept at
`_backup_2026-11-09/FITEVAL_GUI_v4.0_pre_CF_fix.m`.
