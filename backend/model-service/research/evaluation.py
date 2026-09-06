"""Chronological, target-maturity-purged experiments on one frozen snapshot.

The bundled CSV has no historical release/vintage provenance. These experiments
measure validation and specification sensitivity, NOT a certified spot/PIT edge.
All estimator choices are declared before the run. Calibration sees only labels
that matured before the outer test. No estimator is selected or deployed here.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import subprocess
import warnings
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import scipy
import sklearn
from scipy.optimize import minimize
from scipy.stats import kurtosis, skew, spearmanr
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_selection import mutual_info_regression
from sklearn.linear_model import ElasticNet, LinearRegression, LogisticRegression, Ridge
from sklearn.neural_network import MLPRegressor
from threadpoolctl import threadpool_limits

from app.services.xau_dataset_service import FEATURES, HORIZONS

SEEDS = (17, 42, 91)
RATIOS = (.55, .70, .85)
COVERAGES = (.5, .7, .8, .9)


def finite(value):
    """JSON-safe scalars, including undefined correlations (never fake zero)."""
    if isinstance(value, dict): return {str(k): finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)): return [finite(v) for v in value]
    if isinstance(value, (np.floating, float)): return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer): return int(value)
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(finite(value), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def metrics(y, p, price=None):
    y, p = np.asarray(y), np.asarray(p)
    e = p - y
    ae = np.abs(e)
    base_mae, base_mse = np.mean(np.abs(y)), np.mean(y * y)
    active = np.abs(p) > 1e-12
    positive, negative = y > 0, y < 0
    # Abstention is not secretly counted as an up prediction.
    direction_all = np.mean(np.sign(y) == np.sign(p))
    directional = active & (y != 0)
    direction = np.mean(np.sign(y[directional]) == np.sign(p[directional])) if directional.any() else np.nan
    pos_active,neg_active=positive & active,negative & active
    balanced = (np.mean(p[pos_active] > 0) + np.mean(p[neg_active] < 0)) / 2 if pos_active.any() and neg_active.any() else np.nan
    denom = np.sum((p - p.mean()) ** 2)
    total = np.sum((y - y.mean()) ** 2)
    return finite({"n": len(y), "mae": ae.mean(), "rmse": np.sqrt(np.mean(e * e)),
        "median_absolute_error": np.median(ae), "direction": direction,"direction_all_rows":direction_all,
        "balanced_direction": balanced,
        "active_direction": np.mean(np.sign(y[active]) == np.sign(p[active])) if active.any() else np.nan,
        "active_fraction": active.mean(), "correlation": np.corrcoef(y, p)[0, 1] if np.std(y) > 0 and np.std(p) > 1e-12 else np.nan,
        "r2": 1 - np.sum(e * e) / total if total else np.nan,
        "calibration_slope": np.sum((y - y.mean()) * (p - p.mean())) / denom if denom > 1e-18 else np.nan,
        "bias": e.mean(), "mae_skill": 1 - ae.mean() / base_mae if base_mae else np.nan,
        "mse_skill": 1 - np.mean(e * e) / base_mse if base_mse else np.nan,
        "price_mae_usd": np.mean(ae * price) if price is not None else np.nan,
        "within_2_usd": np.mean(ae * price <= 2) if price is not None else np.nan,
        "always_up_direction": positive.mean()})


def block_ci(y, p, block=30, repetitions=500, seed=104):
    """Paired moving-block bootstrap: preserves serial/overlap dependence locally."""
    rng = np.random.default_rng(seed)
    count = len(y)
    block = min(block, count)
    result = []
    for _ in range(repetitions):
        starts = rng.integers(0, count - block + 1, size=math.ceil(count / block))
        indexes = np.concatenate([np.arange(s, s + block) for s in starts])[:count]
        yy, pp = y[indexes], p[indexes]
        denominator = np.mean(np.abs(yy))
        valid=(np.abs(pp)>1e-12)&(yy!=0)
        result.append([np.mean(np.abs(yy - pp)), np.mean(np.sign(yy[valid]) == np.sign(pp[valid])) if valid.any() else np.nan,
                       1 - np.mean(np.abs(yy - pp)) / denominator if denominator else np.nan])
    result=np.asarray(result)
    bounds=np.array([np.nanquantile(result[:,i],[.025,.975]) if np.isfinite(result[:,i]).any() else [np.nan,np.nan] for i in range(3)]).T
    return {key: finite(bounds[:, i]) for i, key in enumerate(("mae", "direction", "mae_skill"))}


def shrink_weight(actual, prediction):
    centered = prediction - prediction.mean()
    denominator = float(np.sum(centered ** 2))
    if denominator < 1e-18: return 0.0
    weight = float(np.clip(np.sum((actual - actual.mean()) * centered) / denominator, 0, 1))
    if np.mean((actual - weight * prediction) ** 2) >= np.mean(actual ** 2): return 0.0
    return weight


def conformal_quantile(residual, coverage):
    residual = np.sort(np.asarray(residual))
    if not len(residual): return np.nan
    rank = min(len(residual), math.ceil((len(residual) + 1) * coverage)) - 1
    return float(residual[rank])


@dataclass(frozen=True)
class Spec:
    name: str
    model: str = "mlp"
    group: str = "full"
    target: str = "simple"
    calibration: str = "none"
    loss: str = "squared_error"
    window_years: int = 0
    recency_days: int = 0
    winsor: bool = False
    replay_frozen: bool = False


def specs():
    result = [Spec("persistence", "zero"), Spec("historical_mean", "mean"),
        Spec("rolling_mean_126", "rolling"), Spec("momentum_20d", "momentum"),
        Spec("direction_majority", "majority"),
        Spec("linear", "linear"), Spec("ridge", "ridge"), Spec("elasticnet", "elasticnet"),
        Spec("random_forest", "forest"), Spec("gradient_boosting", "boosting"),
        Spec("mlp_raw"), Spec("mlp_nested", calibration="slope"),
        Spec("mlp_serving_replay", calibration="slope", replay_frozen=True),
        Spec("mlp_log_target", target="log", calibration="slope"),
        Spec("mlp_price_target", target="price", calibration="slope"),
        Spec("mlp_winsor_train_only", calibration="slope", winsor=True),
        Spec("boosting_huber", "boosting", loss="huber"),
        Spec("boosting_mae", "boosting", loss="absolute_error"),
        Spec("heterogeneous_calibrated", "ensemble"),
        Spec("direction_logistic", "direction"),
        Spec("mlp_shrinkage_calibration", calibration="shrinkage"),
        Spec("mlp_rolling_calibration", calibration="rolling"),
        Spec("mlp_rolling3y", calibration="slope", window_years=3),
        Spec("mlp_rolling5y", calibration="slope", window_years=5),
        Spec("mlp_recency_1y", calibration="slope", recency_days=365)]
    for group in ("technical", "macro", "regime", "minus_dollar", "minus_real_yield",
                  "minus_inflation", "minus_vix", "minus_oil", "minus_momentum", "minus_volatility",
                  "macro_lag_stress", "engineered", "lookback_10_20_40"):
        result.append(Spec("mlp_" + group, group=group, calibration="slope"))
    for group in ("technical", "macro", "regime", "engineered", "lookback_10_20_40"):
        result.append(Spec("ridge_" + group, "ridge", group=group))
    return result


def load_snapshot(path):
    data = Path(path).read_bytes()
    rows = list(csv.DictReader(data.decode("utf-8").splitlines()))
    dates = np.array([np.datetime64(row["date"], "D") for row in rows])
    if np.any(dates[1:] <= dates[:-1]): raise ValueError("Dataset must be strictly chronological and unique")
    price = np.array([float(row["xauusd_close"]) for row in rows])
    x = np.array([[float(row[name]) for name in FEATURES] for row in rows])
    if not np.isfinite(x).all() or not np.isfinite(price).all() or (price <= 0).any():
        raise ValueError("Nonfinite features or impossible prices")
    targets, ends = {}, {}
    for h in HORIZONS:
        y = np.array([float(row[f"target_return_{h}d"]) if row.get(f"target_return_{h}d") else np.nan for row in rows])
        target_indexes = np.searchsorted(dates, dates + np.timedelta64(h, "D"))
        end = np.array([dates[i] if i < len(dates) else np.datetime64("NaT") for i in target_indexes])
        labelled = np.isfinite(y)
        if np.any(labelled & np.isnat(end)): raise ValueError("Target has no observed maturity date")
        recalculated = price[np.minimum(target_indexes, len(price) - 1)] / price - 1
        if not np.allclose(y[labelled], recalculated[labelled], atol=1e-10, rtol=0):
            raise ValueError("Stored target does not match the snapshot's actual future close")
        targets[h], ends[h] = y, end
    return data, rows, dates, price, x, targets, ends


def engineered_features(price, x):
    """Past-only price candidates; unavailable H/L and macro levels not invented."""
    columns, names = [], []
    def append(name, values): names.append(name); columns.append(np.asarray(values))
    for window in (10, 20, 40, 100, 200):
        values = np.full(len(price), np.nan)
        for i in range(window, len(price)):
            values[i] = price[i] / (price[i - window] if window in (10, 40) else np.mean(price[i - window + 1:i + 1])) - 1
        append("return_" + str(window) if window in (10, 40) else "sma_distance_" + str(window), values)
    log_returns = np.r_[np.nan, np.diff(np.log(price))]
    for name in ("zscore20", "percentile60", "vol5_over20", "vol20_over60", "trend_slope20", "rsi_slope5", "momentum_acceleration"):
        values = np.full(len(price), np.nan)
        for i in range(60, len(price)):
            w = price[i-19:i+1]
            if name == "zscore20": values[i] = (price[i] - w.mean()) / max(w.std(), 1e-12)
            elif name == "percentile60": values[i] = np.mean(price[i-59:i+1] <= price[i])
            elif name == "vol5_over20": values[i] = np.std(log_returns[i-4:i+1]) / max(np.std(log_returns[i-19:i+1]), 1e-12)
            elif name == "vol20_over60": values[i] = np.std(log_returns[i-19:i+1]) / max(np.std(log_returns[i-59:i+1]), 1e-12)
            elif name == "trend_slope20": values[i] = np.polyfit(np.arange(20), np.log(w), 1)[0]
            elif name == "rsi_slope5": values[i] = x[i, 4] - x[i-5, 4]
            else: values[i] = x[i, 1] - x[i-5, 1]
        append(name, values)
    def ema(period):
        result = np.empty(len(price)); result[0] = price[0]
        for i in range(1, len(price)): result[i] = 2 / (period + 1) * price[i] + (1 - 2 / (period + 1)) * result[i-1]
        return result
    macd = ema(12) - ema(26)
    signal = np.empty(len(price)); signal[0] = macd[0]
    for i in range(1, len(price)): signal[i] = .2 * macd[i] + .8 * signal[i-1]
    append("macd_histogram_ratio", (macd - signal) / price)
    e = ema(20); append("ema20_slope5", np.r_[np.full(5, np.nan), e[5:] / e[:-5] - 1])
    return np.column_stack(columns), names


def feature_design(x, dates, extra, group, train):
    indexes = list(range(19))
    exclusions = {"dollar": [10,11], "real_yield": [8,9], "inflation": [12,16],
                  "vix": [14,15], "oil": [17,18], "momentum": [0,1,2,3,4], "volatility": [5,6]}
    if group == "technical": indexes = list(range(8))
    elif group == "macro": indexes = list(range(8,19))
    elif group.startswith("minus_"): indexes = [i for i in indexes if i not in exclusions[group[6:]]]
    features = x[:, indexes].copy()
    if group == "regime":
        thresholds = np.quantile(x[train,6], [1/3,2/3])
        regimes = np.column_stack([x[:,6] < thresholds[0], x[:,6] > thresholds[1],
            x[:,9] > 0, x[:,11] > 0, x[:,3] > .02, x[:,3] < -.02, x[:,14] > 20])
        features = np.column_stack([features, regimes.astype(float)])
    if group == "macro_lag_stress":
        for j in range(8,19):
            lag = 45 if j == 16 else 10 if j in (10,11) else 2
            previous = np.searchsorted(dates, dates - np.timedelta64(lag,"D"), side="right") - 1
            features[:,j] = np.where(previous >= 0, x[np.maximum(previous,0),j], np.nan)
    if group in ("engineered", "lookback_10_20_40"):
        features = np.column_stack([features, extra if group == "engineered" else extra[:,:3]])
    # Missing warm-up candidates are filled with TRAIN medians only.
    medians = np.nanmedian(features[train], axis=0)
    return np.where(np.isfinite(features), features, np.where(np.isfinite(medians), medians, 0)), indexes


def split_fold(dates, target_ends, labelled, start, end, calibration_rows=126):
    test = labelled[start:end]
    history = labelled[(labelled < test[0]) & (target_ends[labelled] < dates[test[0]])]
    if len(history) < 250: raise ValueError("Insufficient chronology for train+calibration")
    cal = history[-calibration_rows:]
    train = history[(history < cal[0]) & (target_ends[history] < dates[cal[0]])]
    if len(train) < 100: raise ValueError("Insufficient purged train")
    return train, cal, test


def estimator(spec, seed=17):
    return {
        "linear": lambda: LinearRegression(), "ridge": lambda: Ridge(alpha=30),
        "elasticnet": lambda: ElasticNet(alpha=.001,l1_ratio=.25,max_iter=5000),
        "forest": lambda: RandomForestRegressor(n_estimators=100,max_depth=4,min_samples_leaf=20,random_state=seed,n_jobs=1),
        "boosting": lambda: GradientBoostingRegressor(n_estimators=80,max_depth=2,min_samples_leaf=20,learning_rate=.03,loss=spec.loss,random_state=seed),
        "mlp": lambda: MLPRegressor(hidden_layer_sizes=(8,4),activation="tanh",solver="lbfgs",alpha=.08,max_iter=600,random_state=seed),
    }[spec.model]()


def fit_spec(spec, features, x, price, y, dates, train, cal, test, horizon, frozen):
    if spec.window_years:
        train = train[dates[train] >= dates[cal[0]] - np.timedelta64(365 * spec.window_years, "D")]
    if len(train) < 100: raise ValueError("Window has fewer than 100 purged training rows")
    mean, std = features[train].mean(0), features[train].std(0)
    std[std < 1e-9] = 1
    raw_z = (features - mean) / std
    z = np.clip(raw_z, -6,6)
    train_z = z
    if spec.replay_frozen:
        # Exact old serving transform: training was NOT clipped/neutralized.
        train_z = raw_z
        z = z.copy(); z[frozen] = 0
    yy = y[train].copy()
    if spec.target == "log": yy = np.log1p(yy)
    target_mean, target_std = 0.0, 1.0
    if spec.target == "price":
        yy = price[train] * (1 + yy)
        target_mean, target_std = yy.mean(), max(yy.std(), 1e-9)
        yy = (yy - target_mean) / target_std
    if spec.winsor: yy = np.clip(yy, *np.quantile(yy, [.01,.99]))
    sample_weight = np.exp(-np.log(2) * (dates[cal[0]]-dates[train]).astype(float) / spec.recency_days) if spec.recency_days else None
    selected = np.r_[cal,test]
    if spec.model == "zero": predict = lambda zz, ii: np.zeros(len(ii))
    elif spec.model in ("mean","rolling","majority"):
        def predict(zz,ii):
            result=[]
            for index in ii:
                known=np.flatnonzero(np.isfinite(y)&(target_end_global<dates[index]))
                if spec.model=="rolling":known=known[-126:]
                if spec.model=="majority":result.append((1 if np.mean(y[known]>0)>=.5 else -1)*np.median(np.abs(y[known])))
                else:result.append(np.mean(y[known]))
            return np.asarray(result)
    elif spec.model == "momentum": predict = lambda zz, ii: x[ii,2] * horizon / 28
    elif spec.model == "direction":
        labels = y[train] > 0
        if len(np.unique(labels)) < 2:
            predict = lambda zz, ii: np.full(len(ii), np.median(y[train]))
        else:
            classifier = LogisticRegression(C=.1, max_iter=1000, random_state=17).fit(train_z[train], labels)
            amplitude = np.median(np.abs(y[train]))
            predict = lambda zz, ii: (2 * classifier.predict_proba(zz)[:,1] - 1) * amplitude
    elif spec.model == "ensemble":
        components = [Spec("component_ridge","ridge"),Spec("component_boosting","boosting"),Spec("component_mlp")]
        members = []
        for component in components:
            for seed in (SEEDS if component.model == "mlp" else (17,)):
                members.append((component.model,estimator(component,seed).fit(train_z[train],y[train])))
        def component_predictions(zz):
            return np.column_stack([np.mean([m.predict(zz) for kind,m in members if kind == name],axis=0)
                                    for name in ("ridge","boosting","mlp")])
        cal_matrix = component_predictions(z[cal])
        opt = minimize(lambda w: np.mean((y[cal] - cal_matrix@w)**2), np.ones(3)/3,
            bounds=[(0,1)]*3, constraints={"type":"eq","fun":lambda w:w.sum()-1},
            method="SLSQP", options={"ftol":1e-12,"maxiter":200})
        if not opt.success: raise RuntimeError("Ensemble calibration failed: " + opt.message)
        predict = lambda zz, ii: component_predictions(zz) @ opt.x
    else:
        models = [estimator(spec,seed).fit(train_z[train],yy,**({"sample_weight":sample_weight} if sample_weight is not None else {}))
                  for seed in (SEEDS if spec.model == "mlp" else (17,))]
        def predict(zz, ii):
            result = np.mean([m.predict(zz) for m in models],axis=0)
            if spec.target == "log": result = np.expm1(np.clip(result,-2,2))
            if spec.target == "price": result = (result*target_std+target_mean) / price[ii] - 1
            return result
    raw_cal, raw_test = predict(z[cal],cal), predict(z[test],test)
    weight = 1.0
    if spec.calibration != "none":
        cc = slice(-63,None) if spec.calibration == "rolling" else slice(None)
        weight = shrink_weight(y[cal][cc], raw_cal[cc])
        if spec.calibration == "shrinkage": weight *= len(cal)/(len(cal)+126)
    pred_cal, pred_test = weight * raw_cal, weight * raw_test
    residual = np.abs(y[cal] - pred_cal)
    # Split calibration again for interval fitting: weights use early segment;
    # quantiles are measured on the later segment without reusing its outcomes
    # for slope/ensemble selection. Base fits remain before both segments.
    mid = len(cal)//2
    weight_cal = cal[:mid]
    interval_cal = cal[(target_end_global[cal[:mid]].max() < dates[cal])]
    if len(interval_cal) < 20:
        interval_cal = cal[-max(20,len(cal)//3):]
        cutoff = dates[interval_cal[0]]
        weight_cal = cal[target_end_global[cal] < cutoff]
    if len(weight_cal) < 15 or len(interval_cal) < 20:
        raise ValueError("Insufficient non-overlapping weight/residual calibration; no fallback to shared labels")
    if spec.calibration != "none":
        loc = np.searchsorted(cal,weight_cal)
        weight = shrink_weight(y[weight_cal],raw_cal[loc])
        if spec.calibration == "shrinkage": weight *= len(weight_cal)/(len(weight_cal)+126)
        if spec.calibration == "rolling":
            weight = shrink_weight(y[weight_cal[-32:]],raw_cal[np.searchsorted(cal,weight_cal[-32:])])
        pred_cal, pred_test = weight*raw_cal,weight*raw_test
    if spec.model == "ensemble":
        # Refit ensemble weights on early calibration only, then estimate errors
        # on later calibration with non-overlapping label windows.
        wm=component_predictions(z[weight_cal])
        opt=minimize(lambda w:np.mean((y[weight_cal]-wm@w)**2),np.ones(3)/3,bounds=[(0,1)]*3,
                     constraints={"type":"eq","fun":lambda w:w.sum()-1},method="SLSQP",options={"ftol":1e-12})
        if not opt.success: raise RuntimeError("Ensemble calibration failed")
        pred_cal=component_predictions(z[cal])@opt.x; pred_test=component_predictions(z[test])@opt.x
    residual=np.abs(y[interval_cal]-pred_cal[np.searchsorted(cal,interval_cal)])
    reference = max(np.median(x[train,6]),1e-9)
    volscale = np.clip(x[test,6]/reference,.75,2)
    cal_volscale = np.clip(x[interval_cal,6]/reference,.75,2)
    widths = {}
    for coverage in COVERAGES:
        widths["split_"+str(coverage)] = np.full(len(test),conformal_quantile(residual,coverage))
        widths["volnorm_"+str(coverage)] = conformal_quantile(residual/cal_volscale,coverage)*volscale
        rolling, adaptive, alpha = [], [], 1-coverage
        feedback_seen=set()
        for j,index in enumerate(test):
            matured = test[(test < index) & (target_end_global[test] < dates[index])]
            observed_errors = np.abs(y[matured] - pred_test[np.searchsorted(test,matured)])
            scores = np.r_[residual,observed_errors]
            rolling.append(conformal_quantile(scores[-126:],coverage))
            # Delayed-feedback ACI-style update: each target is consumed once,
            # only AFTER maturity, against its actual issued interval. Clipped
            # alpha/rolling residuals are research choices, not a coverage proof.
            for old_index in matured:
                if int(old_index) in feedback_seen: continue
                old_position=int(np.searchsorted(test,old_index))
                miss=float(abs(y[old_index]-pred_test[old_position])>adaptive[old_position])
                alpha=float(np.clip(alpha+.01*((1-coverage)-miss),.01,.99))
                feedback_seen.add(int(old_index))
            adaptive.append(conformal_quantile(scores[-126:],1-alpha))
        widths["rolling_"+str(coverage)]=np.asarray(rolling)
        widths["adaptive_"+str(coverage)]=np.asarray(adaptive)
    widths["legacy_claimed70"] = np.quantile(residual,.8)*volscale
    cov=LedoitWolf().fit(z[train])
    distances=cov.mahalanobis(z[test]); threshold=np.quantile(cov.mahalanobis(z[train]),.99)
    diagnostics={"calibration_weight":weight,"training_rows":len(train),"weight_calibration_rows":len(weight_cal),
        "interval_calibration_rows":len(interval_cal),"ood_fraction":float(np.mean(distances>threshold)),
        "ood_distances":distances,"ood_threshold":float(threshold),"zmax":np.max(np.abs((features[test]-mean)/std),axis=1)}
    if spec.model == "ensemble": diagnostics["ensemble_weights"] = opt.x.tolist()
    # Out-of-fold block permutation: never fit or select features on test targets.
    permutation={}
    if spec.name in ("mlp_nested","ridge"):
        rng=np.random.default_rng(27)
        base=np.mean(np.abs(y[test]-pred_test))
        for j,name in enumerate(FEATURES):
            differences=[]
            for _ in range(3):
                perm=z[test].copy(); blocks=[np.arange(s,min(s+20,len(test))) for s in range(0,len(test),20)]
                order=np.concatenate([blocks[k] for k in rng.permutation(len(blocks))])
                perm[:,j]=perm[order,j]
                pp=weight*predict(perm,test)
                differences.append(float(np.mean(np.abs(y[test]-pp))-base))
            permutation[name]=float(np.mean(differences))
    return pred_test,widths,diagnostics,permutation


# Set by the per-horizon runner; isolated single-process execution only.
target_end_global=np.array([],dtype="datetime64[D]")


def frozen_matrix(rows):
    frozen=np.zeros((len(rows),19),dtype=bool)
    for i in range(15,len(rows)):
        for j,name in enumerate(FEATURES[8:],8):
            frozen[i,j]=len({row[name] for row in rows[i-15:i+1]})==1
    return frozen


def legacy_reproduction(x,y,epochs=600):
    """Frozen copy of HEAD=033e9eb's recipe; intentionally retain its optimism."""
    p=np.full(len(y),np.nan)
    for fold,start in enumerate([int(len(y)*r) for r in RATIOS]):
        end=int(len(y)*RATIOS[fold+1]) if fold<2 else len(y)
        # Caller sets calendar horizon, original code purged that many ROWS.
        train_end=start-legacy_horizon
        mean,std=x[:train_end].mean(0),x[:train_end].std(0);std[std<1e-9]=1
        models=[MLPRegressor(hidden_layer_sizes=(8,4),activation="tanh",solver="lbfgs",alpha=.08,max_iter=epochs,random_state=seed)
                .fit((x[:train_end]-mean)/std,y[:train_end]) for seed in SEEDS]
        p[start:end]=np.mean([m.predict((x[start:end]-mean)/std) for m in models],axis=0)
    mask=np.isfinite(p);weight=shrink_weight(y[mask],p[mask])
    return mask,p[mask],weight*p[mask],weight


legacy_horizon=7


def run(dataset:Path,output:Path,selected:list[str]|None=None):
    global target_end_global,legacy_horizon
    output.mkdir(parents=True,exist_ok=True)
    data,rows,dates,price,x,targets,target_ends=load_snapshot(dataset)
    digest=hashlib.sha256(data).hexdigest()
    snapshot=output/"dataset_snapshot.csv"
    if snapshot.exists() and hashlib.sha256(snapshot.read_bytes()).hexdigest()!=digest:
        raise ValueError("Output already belongs to another snapshot; use a new directory")
    snapshot.write_bytes(data)
    extra,extra_names=engineered_features(price,x)
    registry=specs();registry=[s for s in registry if selected is None or s.name in selected]
    commit=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True).stdout.strip()
    manifest={"dataset_hash":digest,"source_snapshot":str(dataset.resolve()),"rows":len(rows),"start":rows[0]["date"],"end":rows[-1]["date"],
        "git_commit":commit,"evaluator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "features":list(FEATURES),"extra_features":extra_names,"python":platform.python_version(),
        "numpy":np.__version__,"sklearn":sklearn.__version__,"scipy":scipy.__version__,"seeds":SEEDS,
        "validation":"3 expanding outer blocks .55/.70/.85; target-date purge; earlier 126-row calibration split for weights and residuals",
        "target":"simple return to first observed close on/after t+h calendar days","pit_verified":False,"instrument_verified":False,
        "promotion_allowed":False,"warning":"Latest-revision macro and unproven spot provenance. Experimental diagnostics, not certified point-in-time OOS.",
        "direction_semantics":"direction is conditional on nonzero predictions and nonzero targets; active_fraction must accompany it. Persistence has no directional accuracy. All-row hit rate separately recorded.",
        "selection_policy":"All registered candidates reported, no production winner selected. Final block is not a selection holdout; independent untouched PIT confirmation still required.",
        "interval_policy":"Weight calibration first, then maturity-purged residual calibration; rolling126 and delayed-feedback ACI-style gamma=.01, clipped alpha .01-.99; no exchangeability/conditional guarantee asserted.",
        "experiment_registry":[asdict(s) for s in registry],"bootstrap":"paired moving blocks of 30 observations, 500 resamples; conditional on this dataset"}
    write_json(output/"manifest.json",manifest)
    distributions={}
    for h,y in targets.items():
        v=y[np.isfinite(y)]
        distributions[h]={"n":len(v),"mean":v.mean(),"median":np.median(v),"std":v.std(),"skew":skew(v),
            "excess_kurtosis":kurtosis(v),"min":v.min(),"max":v.max(),"fraction_abs_over_10pct":np.mean(np.abs(v)>.1)}
    write_json(output/"target_distributions.json",distributions)
    corr={"features":list(FEATURES),"pearson":np.corrcoef(x.T),"spearman":spearmanr(x).statistic,
          "note":"Descriptive full-snapshot correlations; not used for selection. MI fit on earliest 50% labelled rows only."}
    for h,y in targets.items():
        idx=np.flatnonzero(np.isfinite(y))[:len(rows)//2]
        corr["mutual_information_"+str(h)]=mutual_info_regression(x[idx],y[idx],random_state=17)
    write_json(output/"feature_redundancy.json",corr)
    results={};all_predictions=[];legacy={};frozen=frozen_matrix(rows)
    warning_counts={}
    with threadpool_limits(limits=1):
        for h in HORIZONS:
            y=targets[h];labelled=np.flatnonzero(np.isfinite(y));target_end_global=target_ends[h];legacy_horizon=h
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always",ConvergenceWarning)
                mask,raw,weighted,weight=legacy_reproduction(x[labelled],y[labelled])
            legacy[h]={"label":"INDEPENDENT TEST INVALID: globally calibrated on the reporting OOF labels", "weight":weight,
                "raw":metrics(y[labelled][mask],raw,price[labelled][mask]),"reported":metrics(y[labelled][mask],weighted,price[labelled][mask])}
            tests=[int(len(labelled)*r) for r in RATIOS]+[len(labelled)]
            folds=[split_fold(dates,target_end_global,labelled,tests[i],tests[i+1]) for i in range(3)]
            results[h]={}
            for spec in registry:
                pred_parts=[];actual_parts=[];test_parts=[];fold_reports=[];interval_parts={};importance=[];diag_parts=[]
                for f,(train,cal,test) in enumerate(folds):
                    design,indexes=feature_design(x,dates,extra,spec.group,train)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always",ConvergenceWarning)
                        pred,widths,diag,permutation=fit_spec(spec,design,x,price,y,dates,train,cal,test,h,frozen)
                    warning_counts[f"{h}:{spec.name}:{f}"]=sum(issubclass(w.category,ConvergenceWarning) for w in caught)
                    fold_reports.append({"fold":f,"test_start":str(dates[test[0]]),"test_end":str(dates[test[-1]]),
                        **metrics(y[test],pred,price[test]),**{k:v for k,v in diag.items() if not isinstance(v,np.ndarray)}})
                    for key,w in widths.items():interval_parts.setdefault(key,[]).append(w)
                    pred_parts.append(pred);actual_parts.append(y[test]);test_parts.append(test);importance.append(permutation);diag_parts.append(diag)
                yy,pp,tt=np.concatenate(actual_parts),np.concatenate(pred_parts),np.concatenate(test_parts)
                report={"metrics":metrics(yy,pp,price[tt]),"confidence_intervals95":block_ci(yy,pp),"folds":fold_reports,
                    "positive_skill_folds":sum(f["mae_skill"]>0 for f in fold_reports),
                    "fold_mae_std":np.std([f["mae"] for f in fold_reports]),"intervals":{},"regimes":{}}
                for key,parts in interval_parts.items():
                    width=np.concatenate(parts)
                    coverage=float(key.split("_")[-1]) if key!="legacy_claimed70" else .7
                    outside=np.maximum(np.abs(yy-pp)-width,0)
                    report["intervals"][key]={"empirical":np.mean(np.abs(yy-pp)<=width),"nominal":coverage,
                        "mean_width_return":np.mean(2*width),"interval_score":np.mean(2*width+2/(1-coverage)*outside)}
                for regime in ("high_vol","low_vol","rising_real_yield","falling_real_yield","strong_dollar","weak_dollar","bull","bear","risk_off","risk_on"):
                    memberships=[]
                    for (train,cal,test) in folds:
                        thresholds=np.quantile(x[train,6],[1/3,2/3])
                        masks={"high_vol":x[test,6]>thresholds[1],"low_vol":x[test,6]<thresholds[0],
                          "rising_real_yield":x[test,9]>0,"falling_real_yield":x[test,9]<0,"strong_dollar":x[test,11]>0,
                          "weak_dollar":x[test,11]<0,"bull":x[test,3]>.02,"bear":x[test,3]<-.02,"risk_off":x[test,14]>20,"risk_on":x[test,14]<=20}
                        memberships.append(masks[regime])
                    membership=np.concatenate(memberships)
                    if membership.any():report["regimes"][regime]=metrics(yy[membership],pp[membership],price[tt][membership])
                if any(importance):report["oof_block_permutation_mae_increase"]={name:np.mean([a[name] for a in importance]) for name in FEATURES}
                if spec.name in ("mlp_nested","mlp_serving_replay","ridge","heterogeneous_calibrated"):
                    sigma=np.concatenate(interval_parts["volnorm_0.8"])/1.28155
                    zmax=np.concatenate([d["zmax"] for d in diag_parts])
                    distances=np.concatenate([d["ood_distances"]/d["ood_threshold"] for d in diag_parts])
                    masks={"signal_quarter_sigma":np.abs(pp)>=.25*sigma,"z6":zmax<=6,"mahalanobis_train99":distances<=1}
                    report["abstention_candidates"]={name:{"coverage":mask.mean(),"metrics":metrics(yy[mask],pp[mask],price[tt][mask]) if mask.any() else None} for name,mask in masks.items()}
                    largest=np.argsort(np.abs(yy-pp))[::-1][:20]
                    report["largest_errors"]=[{"date":str(dates[tt[i]]),"target_date":str(target_end_global[tt[i]]),
                        "predicted_return":pp[i],"actual_return":yy[i],"absolute_error_return":abs(yy[i]-pp[i]),
                        "absolute_error_usd":abs(yy[i]-pp[i])*price[tt[i]],"vix":x[tt[i],14],
                        "real_yield_change20":x[tt[i],9],"broad_dollar_return20":x[tt[i],11],"gold_volatility20":x[tt[i],6],
                        "event":"NOT ATTRIBUTED: no audited point-in-time event calendar"} for i in largest]
                results[h][spec.name]=report
                for i,index in enumerate(tt):
                    all_predictions.append({"horizon":h,"experiment":spec.name,"date":str(dates[index]),
                        "target_date":str(target_end_global[index]),"base_price":price[index],"actual_return":yy[i],"predicted_return":pp[i]})
                write_json(output/"results.json",results)
                print(f"{h}d {spec.name}: MAE={report['metrics']['mae']:.5f} skill={report['metrics']['mae_skill']:.3f} direction={report['metrics']['direction']} active={report['metrics']['active_fraction']:.3f}",flush=True)
    write_json(output/"legacy_reproduction.json",legacy)
    write_json(output/"convergence_warnings.json",warning_counts)
    with (output/"oos_predictions.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(all_predictions[0]),lineterminator="\n");writer.writeheader();writer.writerows(all_predictions)
    return results
