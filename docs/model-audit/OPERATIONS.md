# Model audit: local operational changes

No production deployment, retraining, artifact promotion, or existing forecast
history reconstruction was performed by this change. The current 7/14/30-day
artifacts remain the champion; especially the existing 30-day model is preserved.

## Compatibility and limits

Legacy artifacts retain their numeric mean-return and volatility-scaled band
formulas, including their legacy frozen-feature policy. New candidates use the
shared `standard-clip-v1` preprocessing and
`canonical-asof-no-neutralization-v1` input policy. A request holds one artifact
snapshot so a concurrent reload cannot mix horizons/model versions.

API `intervals[].nominal_coverage` describes the residual quantile (normally
0.80), not verified live coverage. `empirical_coverage` remains null for the
served final-fit band; candidate outer-test procedure results are separate.
Frontend no longer labels a server 80% residual band as 70% or multiplies it by
an unsupported normal-distribution conversion. Forecast prices stay anchored to
the API request's price; live spot ticks are shown separately. Client forecasts
are explicitly scenarios, not immutable official daily forecasts.

`status` can report `OK`, `OUT_OF_DISTRIBUTION`, `STALE_DATA`, or
`INSUFFICIENT_DATA`. A missing model returns HTTP 503 `MODEL_UNAVAILABLE`.
Unknown feature date or a date older than seven calendar days disables the
displayed view without changing the numeric legacy model mean/weight. The
seven-day guard is a conservative operational rule, not a market calendar or
macro-release SLA. OOD diagnostics are unvalidated ±6 training-z indications;
they do **not** change weights or invent a confidence probability.

## Explicit configuration

Set these on the model service only when intentionally enabling the capability:

| Variable | Default | Meaning |
|---|---|---|
| `MODEL_ADMIN_TOKEN` | empty | Empty disables administrative mutations in every environment. |
| `PREDICTION_LOGGING` | `false` | Opt-in append-only SQLite recording. |
| `PREDICTION_LOG_PATH` | `MODEL_DIR/predictions.sqlite3` | Put this on a durable, access-controlled volume. |
| `AUTO_TRAIN` | existing configuration | Candidate creation only; never silently promotes. |

Never place the admin token in frontend variables, source code, URLs, or public
logs. Administrative requests require `Authorization: Bearer <configured token>`.
The repository's production compose file does not set this token or enable
logging. No extra capability is silently enabled by deploying the code.

## Endpoints

Paths below are relative to the model service (gateway prefix `/model-service`).

- `GET /health`: liveness; does not claim a trained model exists.
- `GET /ready`: model readiness, HTTP 503 when unavailable.
- `GET /v1/features/latest`: canonical CSV vector with source date, dataset hash,
  feature version, provenance, and validation status.
- `POST /v1/predict`: finite positive price, all 19 finite features, optional
  `source_date`. Always a `client_scenario`; omitted date disables view. No
  client-provided flag can make this an official observation.
- `POST /v1/training/run`: admin-only candidate training; `promote=False`.
  This operation must not be used as an audit/health check.
- `POST /v1/forecasts/canonical`: admin-only; reads features/price server-side.
  Refuses unverified provenance, current-revision macro data, unknown instruments,
  and futures proxies. Requires validated point-in-time `XAUUSD_spot` provenance.
  Issuance must precede **every** target date, even if logging is disabled;
  retrospective forecasts with a target already reached are rejected.
- `GET /v1/monitoring`: read-only; does not create a database. Returns `DISABLED`,
  `NO_LOGGED_PREDICTIONS`, or `NO_OFFICIAL_PREDICTIONS` rather than fabricated metrics.

The current legacy dataset has no verified point-in-time manifest, so official
forecast issuance is intentionally blocked. Changing a label in a manifest is
not evidence; provider release times, vintages, instrument identity, hash, and
validation must actually be established before official issuance/promotion.

## Ledger, outcomes, and reconciliation

`PredictionLedger.append` stores immutable original forecast rows with unique ID,
issued time, origin/target dates, horizon, spot, expected return/price/bounds,
model version/weight, feature vector/hash, interval metadata, disagreement, and
training-z diagnostics. Canonical snapshot/model/horizon duplicates are ignored.
Scenario rows are stored separately by kind and **excluded** from official
monitoring. SQLite triggers reject updates/deletes to forecasts and outcomes.
Logging failures are surfaced in response `logging.error`; they do not silently
pretend a prediction was recorded or replace its numerical result.

There is **no automatic reconciliation scheduler or public write endpoint**.
An operator with verified historical observations may explicitly call
`PredictionLedger.reconcile(prediction_id, actual_date=..., actual_price=...,
instrument=..., source=..., first_session_verified=True, observed_at=...)` from a
trusted offline maintenance process. This writes a separate immutable outcome.
It requires a positive finite actual price, matching instrument, an observed
date on/after the target, a nonfuture timezone-aware observation timestamp, and
explicit verification that this was the first eligible trading session. The
observation timestamp must be strictly later than the immutable forecast issuance
timestamp. Dates are parsed and normalized before comparison. When canonical
provenance specifies a price provider, settlement must use that same provider.
The
code cannot independently prove an operator-supplied provider observation;
source verification remains a prerequisite. Duplicates/conflicts fail rather
than overwrite. Never use GC=F to settle a spot forecast or today's model to
reconstruct a forecast that was never recorded.

Monitoring reports rolling last-30/90 **issued** canonical forecasts separately
for each `instrument/model_version/horizon` group. Within a group, only the first
issuance for each origin date is counted; later feature-vector changes do not
inflate the sample and different model versions are never pooled. Window keys
are, for example, `XAUUSD_spot/model-version/7d/30`. Reported metrics:
resolved count, return/price MAE, bias, direction accuracy for published nonzero
views, interval coverage, disagreement, prediction mean drift, per-feature
training-z means, and zero-return MAE skill. Unresolved forecasts remain in the
window and do not become zero errors. Model/instrument groups are disclosed.
At least 30 resolved observations with negative MAE skill produce a diagnostic
alert only. Drift thresholds are not OOS-calibrated, and there is no automatic
confidence reweighting/promotion. At most 180 distinct dates per model/instrument/horizon group are loaded
for monitoring. Storage remains append-only: plan disk capacity/backups before
enabling high-volume client-scenario logging; no retention deletion job exists.

## Local checks and deployment prerequisites

From `backend/model-service` run:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_serving_contract.py tests/test_model_service.py tests/test_neutralize_frozen.py
```

Run the full backend tests and frontend build/tests before deployment. Verify
legacy numeric outputs, shared candidate preprocessing, ledger/auth protections,
and HTTP 503 readiness on an empty model directory. Back up the active model and
model volume first. Review candidate fold-by-fold/held-out evidence independently
for each horizon; no aggregate improvement may authorize degrading 30 days.
No deployment or promotion is authorized by this runbook itself.
