import json
from pathlib import Path
import joblib
import numpy as np

from ..config import ROOT, settings
from .xau_dataset_service import FEATURES, HORIZONS
from .preprocessing import transform_features

# Yükleme sırası: MODEL_DIR/active.json -> (varsa) imaja gömülü yedek.
# Yedek build sırasında artık üretilmiyor, o yüzden normalde yoktur; `reload`
# var olmayan adayı sessizce atlar ve model bulunamazsa `predict` 503 verir.
BUNDLED_MODEL = ROOT / "data" / "xauusd_model.joblib"

# Ağırlığı bu eşiğin altında kalan ufukta ağın katkısı neredeyse tamamen kısılmıştır;
# çıktı "sıfıra yakın tahmin" değil "görüş yok" olarak sunulmalıdır.
CONFIDENT_WEIGHT = 0.2


class ModelService:
    def __init__(self):
        self.active = None
        self.version = "xauusd-model-not-trained"
        self.rejected: list[str] = []
        self.reload()

    @property
    def features(self): return list(FEATURES)

    @property
    def horizons(self): return list(HORIZONS)

    @staticmethod
    def _schema_error(artifact: dict) -> str | None:
        """Artefaktın şeması koddaki FEATURES/HORIZONS ile birebir olmalı.

        Doğrulama yokken, eski şemalı bir artefakt sessizce yükleniyor ve
        `x_mean` uzunluğu tutmadığı için tahmin ya 500 veriyor ya da girdileri
        kaydırıp anlamsız sonuç üretiyordu.
        """
        if not isinstance(artifact, dict):
            return "artefakt sözlük değil"
        if list(artifact.get("features", [])) != list(FEATURES):
            return "girdi listesi koddaki FEATURES ile uyuşmuyor"
        if list(artifact.get("horizons", [])) != list(HORIZONS):
            return "ufuk listesi koddaki HORIZONS ile uyuşmuyor"
        if "per_horizon" not in artifact:
            return "per_horizon bölümü yok"
        if not isinstance(artifact.get("version"), str) or not artifact["version"]:
            return "model version eksik"
        try:
            for horizon in HORIZONS:
                state = artifact["per_horizon"][horizon]
                mean, std = np.asarray(state["x_mean"]), np.asarray(state["x_std"])
                if mean.shape != (len(FEATURES),) or std.shape != mean.shape:
                    return f"{horizon}: scaler boyutu geçersiz"
                if not np.isfinite(mean).all() or not np.isfinite(std).all() or np.any(std <= 0):
                    return f"{horizon}: scaler sonlu/pozitif değil"
                weight = float(state.get("weight", 1.0))
                error = float(state.get("error80", state.get("error70", .03)))
                if not np.isfinite(weight) or not 0 <= weight <= 1 or not np.isfinite(error) or error < 0:
                    return f"{horizon}: weight/error geçersiz"
                networks = state.get("networks") or [state.get("network")]
                for network in networks:
                    if not callable(getattr(network, "predict", None)):
                        return f"{horizon}: ağ eksik"
                    if getattr(network, "n_features_in_", len(FEATURES)) != len(FEATURES):
                        return f"{horizon}: ağ girdi boyutu geçersiz"
                    if any(not np.isfinite(value).all() for value in
                           list(getattr(network, "coefs_", [])) + list(getattr(network, "intercepts_", []))):
                        return f"{horizon}: ağ ağırlıkları sonlu değil"
        except (KeyError, TypeError, ValueError, AttributeError):
            return "per_horizon yapısı geçersiz"
        return None

    def reload(self):
        pointer = settings.model_dir / "active.json"
        candidates: list[Path] = []
        if pointer.exists():
            try: candidates.append(Path(json.loads(pointer.read_text())["artifact_path"]))
            except (KeyError, OSError, ValueError): pass
        candidates.append(BUNDLED_MODEL)
        self.rejected = []
        for artifact_path in candidates:
            if not artifact_path.exists():
                continue
            try:
                artifact = joblib.load(artifact_path)
            except Exception as error:                       # bozuk dosya sıradakine geçmeli
                self.rejected.append(f"{artifact_path}: okunamadı ({type(error).__name__})")
                continue
            problem = self._schema_error(artifact)
            if problem:
                self.rejected.append(f"{artifact_path}: {problem}")
                continue
            self.active = artifact
            self.version = artifact["version"]
            return

    def predict(self, features: dict, price: float, neutralize: tuple[str, ...] = ()):
        """`neutralize` içindeki girdiler eğitim ortalamasına çekilir.

        Donmuş bir girdi (ör. aylık yayımlanan `core_cpi_yoy`, 20 işlem günüdür
        aynı) tahmin edilen dönem hakkında bilgi taşımaz ama ağırlığı sürer:
        2026-08-31'de 30 günlük tahminin +%3,54'ünün +3,02 puanı tek başına
        ondan geliyordu. Nötrlemek modeli değiştirmez, yalnız o girdiye
        dayanmamasını sağlar."""
        # One immutable object reference for the entire request; reload must not
        # mix horizons from different artifacts mid-prediction.
        artifact = self.active
        if artifact is None: raise ValueError("MODEL_UNAVAILABLE: XAU/USD modeli henüz eğitilmedi")
        if not np.isfinite(price) or price <= 0:
            raise ValueError("Fiyat pozitif ve sonlu olmalı")
        missing = [name for name in self.features if name not in features]
        if missing: raise ValueError(f"Eksik XAU/USD model girdileri: {', '.join(missing)}")
        vector = np.asarray([float(features[name]) for name in self.features])
        if not np.isfinite(vector).all():
            raise ValueError("Model girdileri sonlu olmalı")
        if artifact.get("input_policy") == "canonical-asof-no-neutralization-v1":
            neutralize = ()
        neutral_index = [self.features.index(name) for name in neutralize if name in self.features]
        means, errors, weights, disagreements, intervals, diagnostics = [], [], [], [], [], []
        effects: dict[str, dict[str, float]] = {}
        clipped: set[str] = set()
        for horizon in self.horizons:
            state = artifact["per_horizon"][horizon]
            raw_scaled = (vector - state["x_mean"]) / state["x_std"]
            scaled = transform_features(vector, state["x_mean"], state["x_std"])
            for index in neutral_index:
                scaled[index] = 0.0
            # Eğitim aralığının dışına düşen girdi sessizce kırpılıyordu; çağıran
            # tahminin hangi girdide dayanağını yitirdiğini göremiyordu.
            clipped.update(name for name, value in zip(self.features, raw_scaled)
                           if abs(value) > 6)
            networks = state.get("networks") or [state["network"]]
            members = np.asarray([network.predict(scaled.reshape(1, -1))[0] for network in networks])
            raw = float(np.mean(members))
            weight = float(state.get("weight", 1.0))
            weights.append(weight)
            means.append(weight * raw)
            disagreements.append(float(np.std(weight * members)))
            diagnostics.append({"max_abs_z": float(np.max(np.abs(raw_scaled))),
                                "feature_z_scores": dict(zip(self.features, raw_scaled.tolist()))})
            # Her girdiyi kendi eğitim ortalamasına döndürerek güncel tahmindeki
            # marjinal katkısını ölçer. Bu nedensellik değil, model duyarlılığıdır.
            horizon_effects = {}
            for index, name in enumerate(self.features):
                neutral = scaled.copy()
                neutral[index] = 0.0
                neutral_prediction = float(np.mean([
                    network.predict(neutral.reshape(1, -1))[0] for network in networks]))
                horizon_effects[name] = weight * (raw - neutral_prediction)
            effects[str(horizon)] = horizon_effects
            volatility = float(features.get("gold_volatility_20d", state.get("training_volatility", 1)))
            reference = max(float(state.get("training_volatility", volatility)), 1e-9)
            errors.append(float(state.get("error80", state.get("error70", .03))) *
                          float(np.clip(volatility / reference, .75, 2.0)))
            interval = state.get("interval_calibration") or {}
            intervals.append({"nominal_coverage": .80 if "error80" in state else .70,
                              "method": "absolute_residual_quantile_volatility_scaled",
                              "empirical_coverage": interval.get("empirical_coverage"),
                              "empirical_scope": interval.get("empirical_scope", "unmeasured_for_served_interval"),
                              "live_coverage_verified": False})
        if not np.isfinite(np.asarray(means + errors + disagreements)).all():
            raise ValueError("Model sonlu çıktı üretmedi")
        return {"version": artifact.get("version", self.version), "source": "XAU/USD", "horizons": self.horizons,
                "mean": means, "error": errors, "base_price": price,
                "prices": [price * (1 + value) for value in means],
                "clipped_features": sorted(clipped),
                "neutralized_features": sorted(name for name in neutralize if name in self.features),
                "weights": weights,
                "confident": [w >= CONFIDENT_WEIGHT for w in weights],
                "no_view_reasons": [["historical_weight_below_threshold"] if w < CONFIDENT_WEIGHT else [] for w in weights],
                "status": "OUT_OF_DISTRIBUTION" if clipped else "OK",
                "input_policy": artifact.get("input_policy", "legacy-clip-and-frozen-neutralization"),
                "intervals": intervals, "model_disagreement": disagreements,
                "ood": {"method": "per_feature_training_z_score", "threshold": 6.0,
                        "threshold_validated": False, "affects_model_weight": False,
                        "per_horizon": diagnostics},
                "feature_effects": effects}


model_service = ModelService()
