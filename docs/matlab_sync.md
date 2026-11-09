# MATLAB sync spec — changes to `FITEVAL_GUI.m`

Changes needed in the desktop source
(`FITEVAL_GUI_src/FITEVAL_GUI_Installer_files/FITEVAL_GUI.m`, the Jul-16
revised copy) to match the current Python app. Line numbers are from that
copy.

> **Status (2026-11-09): mostly superseded.** The desktop source is now
> v4.0 (`FITEVAL_GUI.m`, 27 Oct 2026). It already contains **section A**
> (the E1 threshold conversion, now at L303-327) and **section B** (the
> two-section summary labels, L989). The line numbers below point at the
> old Jul-16 copy and no longer match. v4.0 also replaced the rho/alpha
> diagnostic that this file lists as "already in sync"; the Python port now
> follows the v4.0 text (`indices.kge_nse_imbalance`). Read the current
> source before you act on anything below. Section C was not re-checked.

Already in sync (no action): the ρ/α output line (`\rho/\alpha`, L3448/3451),
the 3 bold output lines, and the 3 earlier bug fixes (L3439, L4164,
L3447–3452).

Three behaviours still diverge:

- **A. E1 threshold conversion** — small, localized.
- **B. Two-section multi-run summary CSV** — structural.
- **C. Forced-NSE reclassification** of the with-uncertainty run — part of B.

---

## A. E1 threshold conversion (`GoFIndexSelection`, L299–312)

MATLAB currently knows only the NSE↔KGE pair and treats **E1 as identical to
NSE** (switching NSE→E1 does nothing; KGE*→E1 stops at NSE). The app converts
E1 with `E1 = 1 − √(1 − NSE)`, pivoting every conversion through NSE.

**Replace L299–312** with:

```matlab
      function GoFIndexSelection(~,~)
        % Convert the three class limits between index scales. NSE(1),
        % KGE*/KGE(2,3) and E1(4) are three distinct scales, so every
        % conversion pivots through NSE:
        %   NSE->KGE: 1-sqrt(2)*(1-sqrt(NSE));  KGE->NSE: 0.5*(sqrt(2)-(1-KGE))^2
        %   NSE->E1 : 1-sqrt(1-NSE);            E1->NSE : 1-(1-E1)^2
        val=c_GoFIndex.Value;
        scal=[1 2 2 4];                 % scale id per index: NSE / KGE / E1
        if scal(preval)~=scal(val)
          for aa=1:3
            x=str2double(cV(aa).String);
            if     scal(preval)==2, nse=0.5*(sqrt(2)-(1-x)).^2;  % KGE -> NSE
            elseif scal(preval)==4, nse=1-(1-x).^2;              % E1  -> NSE
            else                    nse=x;                       % NSE
            end
            if     scal(val)==2, x=1-sqrt(2).*(1-sqrt(nse));     % NSE -> KGE
            elseif scal(val)==4, x=1-sqrt(1-nse);                % NSE -> E1
            else                 x=nse;                          % NSE
            end
            cV(aa).String=sprintf('%.2f',x);
          end% aa
        end
        preval=val;
       end %e - GoFIndexSelection
```

Result matches the app: NSE `0.65/0.80/0.90` → E1 `0.41/0.55/0.68`; the
two-step KGE*→E1 gives `0.41/0.55/0.69` (the +0.01 on the top limit is the
2-decimal pivot-rounding drift, inherent unless limits are stored in NSE).
No other site changes: classification compares the computed E1 against these
displayed limits.

---

## B + C. Two-section multi-run summary + forced-NSE

### The gap

MATLAB's multi-run (`MR_RunButtonPushed`, L846–1027) runs **each case once**
and writes a **single-section** summary (header built at L953–967, one row
per case appended at L952, CSV written at L977–983).

The app runs each **uncertainty** case **twice** — deterministic *and*
with-uncertainty — and writes a **two-section** CSV: a **No Unc.** block
(always) and a **With Unc.** block (only if at least one row has an
uncertainty option). Rows with no uncertainty show `--` in the With Unc.
block. The with-uncertainty run is forced to **NSE** and classified against
NSE-scale limits when the configured index is KGE*/KGE (kept as E1 when E1 is
selected).

### Target layout (authoritative: `fiteval_core/multirun.py`)

Band row (line 1) and header row (line 2), joined by `,` with **no trailing
comma**:

```
,,No Unc.×10,[With Unc.×8],,,                      <- band row
Case,Option,<idx1>,<idx1> 95%CI,<idx2>,<idx2> 95%CI,RMSE,RMSE 95%CI,NRMSE,p-value,threshold,Indicator,[<uidx>,<uidx> 95%CI,RMSE,RMSE 95%CI,NRMSE,p-value,threshold,Indicator,]Bias,Outlier,N
```

Labels by `GoF_Index_Flag`:

| | flag 1 (NSE) | flag 2 (KGE*) | flag 3 (KGE) | flag 4 (E1) |
|---|---|---|---|---|
| `idx1` | NSE | NSE | NSE | E_1 |
| `idx2` | KGE* | KGE* | KGE | KGE* |
| `uidx` (With Unc.) | NSE | NSE | NSE | E_1 |

The No Unc. section has **one** Indicator column (= configured index label);
the reference CSV `revised_multirun_table.csv` had a duplicate Indicator that
the app dropped — match the app, i.e. 10 No-Unc columns.

Cell sources, in terms of the existing `NUMOUT{1..12}`
(`{1}`idx1 `{2}`idx1CI `{3}`idx2 `{4}`idx2CI `{5}`RMSE `{6}`RMSECI
`{7}`p-value `{8}`threshold `{9}`NRMSE `{10}`bias `{11}`outlier `{12}`N):

- **No Unc. (10)** from the deterministic run `Nd`:
  `Nd{1} Nd{2} Nd{3} Nd{4} Nd{5} Nd{6} Nd{9} Nd{7} Nd{8}` + `idx1_label`
  (note the reorder: NRMSE before p-value/threshold, and Indicator appended).
- **With Unc. (8)** from the uncertainty run `Nu`:
  `Nu{1} Nu{2} Nu{5} Nu{6} Nu{9} Nu{7} Nu{8}` + `uidx_label`.
  Blank fill for a no-uncertainty row: `{'--','','--','','--','--','--','--'}`.
- **Tail (3)** from the deterministic run: `Nd{10} Nd{11} Nd{12}`.

### B1. Run each case twice; collect, then write once

Restructure the loop body (L881–992) so that, per case:

1. Run the **deterministic** pass with uncertainty fully off
   (`MR_MixedMethod=0`, `DATA_CASE_5_8=[]`, uncertainty button 0), capture
   `Nd = NUMOUT`, and record `idx1_label = indexlabel{1}`.
2. If the option is not `0`, set up uncertainty (as today for `1`/`2` at
   L916–946; see the caveat below for `3`/`4`), apply the forced-NSE override
   (B2), run the **uncertainty** pass, capture `Nu = NUMOUT` and
   `uidx_label = indexlabel{1}`, then restore the override.
3. Store `{fldStr, Option, Nd, Nu-or-[]}` in an accumulator and set
   `anyUnc = anyUnc || ~isempty(Nu)`.

Move the CSV write **out of the loop** to after L993 (currently it rewrites
the file every iteration, which cannot know `anyUnc` for later rows). Each
`Run_Callback` call resets `NUMOUT=[]` before running, since `NUMOUT` is
built only `if isempty(NUMOUT)` (L3726).

### B2. Forced-NSE override for the uncertainty pass

Immediately before the uncertainty `Run_Callback`:

```matlab
    fFlag=GoF_Index_Flag; fCL=CLASSLIM;          % save
    if GoF_Index_Flag==2 || GoF_Index_Flag==3    % KGE*/KGE -> NSE
      GoF_Index_Flag=1;
      CLASSLIM=0.5*(sqrt(2)-(1-CLASSLIM)).^2;    % KGE-scale -> NSE-scale
    end
```

and immediately after it:

```matlab
    GoF_Index_Flag=fFlag; CLASSLIM=fCL;          % restore
```

(NSE and E1 configs need no forcing — the uncertainty run already reports NSE
or E1 respectively.) `GoF_Index_Flag` and `CLASSLIM` are the globals declared
at L490.

### B3. Header — replace L953–967

```matlab
            idx1lbl='NSE'; if GoF_Index_Flag==4, idx1lbl='E_1'; end
            idx2lbl='KGE*'; if GoF_Index_Flag==3, idx2lbl='KGE'; end
            uidxlbl=idx1lbl;   % NSE, or E_1 when E1 selected
            j=1;
            NUMOUTLBL{j}='Case'; j=j+1;
            NUMOUTLBL{j}='Option'; j=j+1;
            NUMOUTLBL{j}=idx1lbl; j=j+1;
            NUMOUTLBL{j}=[idx1lbl ' 95%CI']; j=j+1;
            NUMOUTLBL{j}=idx2lbl; j=j+1;
            NUMOUTLBL{j}=[idx2lbl ' 95%CI']; j=j+1;
            NUMOUTLBL{j}='RMSE'; j=j+1;
            NUMOUTLBL{j}='RMSE 95%CI'; j=j+1;
            NUMOUTLBL{j}='NRMSE'; j=j+1;
            NUMOUTLBL{j}='p-value'; j=j+1;
            NUMOUTLBL{j}='threshold'; j=j+1;
            NUMOUTLBL{j}='Indicator'; j=j+1;
            if anyUnc
              NUMOUTLBL{j}=uidxlbl; j=j+1;
              NUMOUTLBL{j}=[uidxlbl ' 95%CI']; j=j+1;
              NUMOUTLBL{j}='RMSE'; j=j+1;
              NUMOUTLBL{j}='RMSE 95%CI'; j=j+1;
              NUMOUTLBL{j}='NRMSE'; j=j+1;
              NUMOUTLBL{j}='p-value'; j=j+1;
              NUMOUTLBL{j}='threshold'; j=j+1;
              NUMOUTLBL{j}='Indicator'; j=j+1;
            end
            NUMOUTLBL{j}='Bias'; j=j+1;
            NUMOUTLBL{j}='Outlier'; j=j+1;
            NUMOUTLBL{j}='N';
```

### B4. Band row, row assembly and writer — replace L977–983

Build each row from the stored `Nd`/`Nu`, then write once:

```matlab
      band=[{'',''}, repmat({'No Unc.'},1,10)];
      if anyUnc, band=[band repmat({'With Unc.'},1,8)]; end
      band=[band {'','',''}];

      ALLNUMOUT={};
      for ii=1:numel(rows)   % rows: the per-case accumulator from B1
        Nd=rows(ii).Nd; Nu=rows(ii).Nu;
        nou={Nd{1},Nd{2},Nd{3},Nd{4},Nd{5},Nd{6},Nd{9},Nd{7},Nd{8},rows(ii).idx1lbl};
        if isempty(Nu)
          wu={'--','','--','','--','--','--','--'};
        else
          wu={Nu{1},Nu{2},Nu{5},Nu{6},Nu{9},Nu{7},Nu{8},rows(ii).uidxlbl};
        end
        tail={Nd{10},Nd{11},Nd{12}};
        if anyUnc
          ALLNUMOUT(ii,:)=[{rows(ii).Case,rows(ii).Option}, nou, wu, tail];
        else
          ALLNUMOUT(ii,:)=[{rows(ii).Case,rows(ii).Option}, nou, tail];
        end
      end

      fid=fopen(pathMRSummFnm,'w');
      fprintf(fid,'%s\n', strjoin(band,','));
      fprintf(fid,'%s\n', strjoin(NUMOUTLBL,','));
      for ii=1:size(ALLNUMOUT,1)
        fprintf(fid,'%s\n', strjoin(ALLNUMOUT(ii,:),','));
      end
      fclose(fid);
```

`strjoin` gives the no-trailing-comma format the app writes (MATLAB's current
`fprintf('%s,',...)` appends a stray comma — dropping it is required for
byte-identical CSVs).

### Caveats — verify on the MATLAB side

1. **Options `3`/`4` (CF-from-distribution) in multi-run.** The current loop
   only wires up error files for options `1`/`2` (L916). The deterministic +
   uncertainty split assumes the option string is parsed and the CF
   distribution parameters (`OptCase`, obs/prd distributions and values) are
   applied the same way single-run mode does. Confirm `Run_Callback` builds
   the CF from `UncStrRead`/`OptCase` for `3`/`4` under multi-run, or route it
   through the same setup single-run uses.
2. **Deterministic pass must be genuinely uncertainty-free.** Ensure the first
   pass has `MR_MixedMethod=0` and `DATA_CASE_5_8=[]` so `Nd` is the plain
   evaluation even when the option carries uncertainty.
3. **`NUMOUT` capture.** `NUMOUT` is global and built only when empty
   (L3726); set `NUMOUT=[]` before each `Run_Callback` and copy it out
   immediately after.
4. Untested here (no MATLAB runtime) — treat the B code as a structural
   blueprint and validate against the app's `<list>_summary.csv` on
   `multi_run_test.txt` with KGE* selected.
