# XAU/USD feature and time-alignment audit — 2026-09-05

## Scope and snapshot identity

The audit began read-only. The initial local CSV contained 1,197 rows dated
2021-12-01–2026-09-04, SHA-256
`bf0ff9d4294281583710540ffcaf7cdb97a42ee3fa3f7ded1e4ff21bc9566ca3`.
The already-running hourly local service subsequently refreshed four records;
the audit did not overwrite or revert that dataset. All comparative experiments
use the root report's immutable snapshot,
`reports/model-audit-20260905/dataset_snapshot.csv`, SHA-256
`c7a87939ea08cac69112b12576015dabd730d57f475fa1d4b1aca67c7cd3e240`.
The numerical integrity observations below refer to the explicitly identified
initial snapshot, not a claim that the two snapshots have identical values.

No original raw OHLC archive, raw FRED archive, release-time archive or vintage
manifest accompanied the initial CSV. Exact historical point-in-time correctness
therefore **cannot be recovered or certified from this CSV alone**.

## Notation and code mapping

`i` is the ordered gold-bar index; `t` is its calendar date. `C/H/L` denote close,
high and low. `S(t)` is the latest nonmissing FRED observation with
`observation_date <= t`. This legacy operation is **not** an information-availability
join. Returns are fractions unless specified; yield changes are percentage points.

The actual formulas are in
`backend/model-service/app/services/xau_dataset_service.py`, functions
`_gold_features`, `_macro_features`, `Series.as_of/change/ratio` and `build_rows`.
`FEATURES` contains exactly 19 columns. The API receives those columns through
`feature_service.latest_features`; `data_quality.feature_vector` now defines their
canonical order and numeric validation.

## Per-feature audit

| Feature | Source | Actual formula | Lookback | Publication / availability | Missing-value treatment | Risk and status |
|---|---|---|---|---|---|---|
| `gold_return_1d` | xaus daily OHLC; Yahoo `GC=F` fallback | `C[i]/C[i-1]-1` | 1 bar | Completed daily close required; legacy stores date only | Missing price bars omitted; first 60 bars excluded globally | Past-only formula; completed-bar time/source unverified |
| `gold_return_5d` | Same gold source | `C[i]/C[i-5]-1` | **5 bars**, not calendar days | Same | Same | Past-only; naming must not imply macro's 5-calendar-day window |
| `gold_return_20d` | Same gold source | `C[i]/C[i-20]-1` | **20 bars** | Same | Same | Past-only; source/availability unverified |
| `gold_ma_ratio_50d` | Same gold source | `C[i]/mean(C[i-49:i+1])-1` | 50 closes including current | Same | No fill; global warmup | Past-only |
| `gold_rsi14_centered` | Same gold source | `(RSI-50)/50`; `RSI=100-100/(1+mean(gains)/(mean(losses) or 1e-9))` | 14 one-bar changes | Same | Loss denominator guarded by `1e-9` | **Simple rolling RSI**, not Wilder smoothing; flat window produces near -1 rather than neutral 0; legacy behavior retained for measured comparison |
| `gold_atr14_pct` | Same gold source | `mean(max(H-L,abs(H-Cprev),abs(L-Cprev)))/C[i]` | 14 true ranges | Completed high/low and close required | No fill | Simple rolling ATR, not Wilder ATR; original raw H/L absent, independent reconstruction unavailable |
| `gold_volatility_20d` | Same gold source | Population std of 20 `log(C[j]/C[j-1])` × `sqrt(252)` | 20 one-bar log returns | Completed closes | No fill | Past-only; population `ddof=0`, annualized, not percentage display units |
| `gold_drawdown_60d` | Same gold source | `C[i]/max(C[i-59:i+1])-1` | 60 **closing** prices | Completed closes | No fill | Past-only; not drawdown from intraday 60-day high |
| `real_yield_change_5d` | FRED `DFII10` | `S(t)-S(t-5 days)` | 5 calendar days | Observation date used; actual publication timestamp absent | Unlimited backward as-of carry-forward; missing prehistory drops row | HIGH: unverified release timing/current revisions |
| `real_yield_change_20d` | FRED `DFII10` | `S(t)-S(t-20 days)` | 20 calendar days | Same | Same | HIGH: PIT unverified |
| `dollar_return_5d` | FRED `DTWEXBGS` | `S(t)/S(t-5 days)-1` | 5 calendar days | H.10 daily observations are published in a later weekly release | Same; zero denominator drops row | CRITICAL historical timing risk; **broad trade-weighted USD, not ICE DXY** |
| `dollar_return_20d` | FRED `DTWEXBGS` | `S(t)/S(t-20 days)-1` | 20 calendar days | Same | Same | CRITICAL historical timing risk; not DXY |
| `breakeven_change_20d` | FRED `DGS10` minus `DFII10` | `(DGS10(t)-DFII10(t))-(DGS10(t-20)-DFII10(t-20))` | 20 calendar days | Two series independently observation-date joined | Each series independently carried forward | HIGH: mixed availability dates possible; derived yield spread, not a directly fetched inflation-expectations series |
| `yield_curve_10y_2y` | FRED `DGS10`, `DGS2` | `DGS10(t)-DGS2(t)` | Current available observation | Publication timestamp absent | Independent carry-forward | HIGH: two components may represent different dates; level in percentage points |
| `vix_level` | FRED `VIXCLS` | `S(t)` | Latest daily close | Market close and FRED update time differ | Unlimited carry-forward | HIGH: date-only join cannot prove it was available at forecast cutoff |
| `vix_change_5d` | FRED `VIXCLS` | `S(t)-S(t-5 days)` | 5 calendar days | Same | Same | HIGH: absolute index-point change, **not VIX return** |
| `core_cpi_yoy` | FRED `CPILFESL`, seasonally adjusted core CPI index | Legacy `(S(t)/S(t-365 days)-1)*100` | 365 days, not exact reference month | Monthly observation is released later; seasonal history can be revised | Unlimited carry-forward | CRITICAL: monthly lookahead + current-vintage history + leap-year reference-month bug |
| `oil_return_5d` | FRED `DCOILWTICO`, Cushing WTI spot | `S(t)/S(t-5 days)-1` | 5 calendar days | Observation date is not necessarily FRED availability date | Unlimited carry-forward; zero denominator drops row | HIGH: availability/revision unverified; not oil futures |
| `oil_return_20d` | FRED `DCOILWTICO` | `S(t)/S(t-20 days)-1` | 20 calendar days | Same | Same | HIGH: PIT unverified |

“Past-only” means array indexes do not access future bars; it does **not** establish
that the underlying close/revised raw value was available at the prediction time.
No row contains the macro observation dates actually used, their release times or
ages. A flat forward-filled feature is not evidence that the source is fresh.

## Critical evidence

1. **Observation time is not release time.** Legacy `parse_fred` retains only a date
   and float, and `Series.as_of` compares only that observation date. There is no
   release/vintage parameter in the legacy FRED download. The necessary condition
   is `available_at <= prediction_time` (the opposite direction to the inequality
   accidentally written in the request). No arbitrary one-day/month delay can be
   advertised as a fully repaired point-in-time dataset.
2. **CPI exact-month defect.** `2024-04-30 - 365 days = 2023-05-01`; the current
   April reference month can be divided by prior-year May rather than April.
   The initial snapshot contains eight extra month-end CPI changes:
   2024-02-29, 04-30, 05-31, 07-31, 09-30, 10-31, 12-31 and 2025-01-31.
   The offline PIT implementation uses the latest *released* CPI reference month
   and that exact month one year earlier, selecting only vintages already known.
3. **Source identity.** The fallback is `GC=F` futures, not spot XAU/USD. Basis and
   contract-roll changes need not disappear when converting prices to returns.
   The existing CSV does not identify its source, so its instrument cannot be
   proven from the stored schema. New download manifests expose this proxy and
   prohibit treating it as verified spot provenance for model promotion.
4. **Serving transforms are part of the model.** Before this audit, CSV/serving raw
   vector parity was exact, but serving alone clipped standardized inputs at ±6
   and neutralized macro features constant for 15 changes (16 observations).
   The training/OOF path did neither. On the initial snapshot, this heuristic
   would neutralize CPI on 330/1,197 dates (27.57%); no other macro feature met it.
   Monthly release frequency is not proof of missing predictive information.
   Existing production behavior must be replayed in diagnostic OOS evaluation,
   not mistaken for historically validated freshness handling.
5. **Live anchoring changes the forecast contract.** FE obtains daily features
   and then reanchors the expected return to a live Harem spot quote. Training
   targets were measured from daily historical closes. This can be a scenario,
   but is not by itself an independently validated live-to-live horizon forecast.
6. **No trusted market calendar.** Observed date gaps of 2–4 days cannot be called
   missing trading days without choosing the instrument, session and holiday
   calendar. That quality check remains explicitly unverified, not silently
   satisfied. Extreme returns similarly require source/event investigation,
   not arbitrary deletion because the value is large.

## Measured integrity and target checks (initial snapshot)

No duplicate/out-of-order date, missing feature, NaN or Infinity was present in
the initial stored dataset. All 19 latest raw API inputs equalled their CSV
columns exactly (`max(abs(delta))=0`). Seven close-derived technical features
were independently recomputed after the required lookback; all had max error 0.
ATR could not be independently recomputed because raw high/low were not stored.
These checks verify consistency, **not economic predictive value or PIT validity**.

The target is simple return to the first observed trading date on or after
`t + h calendar days`, not h bars and not a log-return target. All nonempty target
values in the initial CSV exactly matched this rule within `1e-10`.

| Target | Labelled / blank | Effective elapsed calendar days | Mean | Median | Sample std | Skew | Excess kurtosis | Min | Max |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 7d | 1192 / 5 | 7–10 | 0.4017% | 0.4217% | 2.5393% | -0.1969 | 1.9887 | -12.0316% | 9.7231% |
| 14d | 1187 / 10 | 14–17 | 0.8244% | 0.5969% | 3.4588% | 0.0564 | 1.8310 | -15.8785% | 15.4135% |
| 30d | 1175 / 22 | 30–33 | 1.7787% | 1.5125% | 4.9546% | 0.0946 | 0.5101 | -15.1344% | 22.5775% |

Skew/kurtosis above are population central-moment statistics; std uses `ddof=1`.
Log-return distributions were also calculated; they do not remove the heavy
tails (7d excess kurtosis 2.2834; 14d 2.0513; 30d 0.5087). Selection between targets,
losses or winsorization must use the common frozen walk-forward benchmark, not
these descriptive statistics alone.

## Changes and automated checks

- `data_quality.py`: strict ordered/unique ISO dates, finite 19-vector, positive
  OHLC and close, `low <= close <= high`, finite simple targets greater than -1;
  blanks remain valid for not-yet-mature labels. Shared `feature_vector` is used
  by training and serving. Manifest SHA-256 and feature schema must match.
- `xau_dataset_service.py`: legacy mathematical definitions are intentionally
  unchanged. Normalized price bars/rows and macro finite values/duplicate dates
  are validated. CSV and manifest are written by atomic file replacement;
  inter-file hash mismatch fails closed. New legacy manifests declare
  `availability=unverified`, `macro_vintage=current_revision`, `validated=false`.
- `feature_service.py`: one complete CSV byte snapshot, strict validation,
  canonical vector and hash/provenance metadata; missing manifest is explicit
  `UNVERIFIED_PROVENANCE`, not `OK`.
- `point_in_time.py`: opt-in offline release/vintage model; future-release and
  future-revision exclusion; CPI exact reference month; mandatory aware
  prediction and completed-price timestamps. Missing released inputs drop the
  row; no backwards fill. It neither fetches nor replaces the live CSV.
- `test_data_quality.py`, `test_point_in_time.py`: all-19 raw-to-training-to-serving
  parity at `epsilon=1e-12`, future perturbation invariance, release boundary and
  revision fixtures, leap-year CPI regression, completed-bar enforcement,
  invalid input rejection, atomic validation failure and hash-tamper rejection.

New production promotion requires explicit verified PIT **spot** provenance;
legacy diagnostic experiments may still run. Producing a genuine revised-data-
free five-year dataset remains dependent on obtaining and archiving trusted raw
release/vintage/price-source data. This change does not claim to have obtained it.

## Primary source references

- [BLS seasonal adjustment](https://www.bls.gov/cpi/seasonal-adjustment/): seasonal
  adjustment recalculates prior history; current historical values are not
  automatically the values published at the historical forecast time.
- [Federal Reserve H.10 release](https://www.federalreserve.gov/Releases/h10/default.htm):
  the weekly release schedule demonstrates why daily observation dates in the
  broad-dollar series do not imply same-day publication availability.
- [FRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html):
  retrieving information as it is known now differs from retrieving what was
  known during a historical real-time period.
