"""Teknik analiz paketinin tek yapılandırma kaynağı.

Her algoritmanın parametre sınıfı kendi modülünde durur (frozen dataclass);
burası onları tek bir `TechnicalConfig` altında toplar, `TA_` önekli ortam
değişkenleriyle ezilmelerini sağlar ve yanıta yazılan `config_hash`'i üretir.
Kod içinde sihirli sayı yoktur: bir eşik değişecekse ya buradaki varsayılan
ya da ortam değişkeni değişir ve hash'in değişmesi bunu görünür kılar.

Ortam değişkeni adı: `TA_<BLOK>_<ALAN>` (ör. `TA_LEVELS_MIN_STRENGTH=35`,
`TA_INDICATORS_RSI_PERIOD=14`, `TA_BREAKOUT_WEIGHT_SESSION=1`). Üst düzey
alanlar için `TA_<ALAN>` (`TA_CACHE_TTL_SECONDS=300`). Değer türü alanın
tipinden çıkarılır: int/float/bool/str, virgüllü sayı demeti (`5,10,20`),
`ad:ağırlık,...` çift demeti. `trend.ranges` gibi bileşik alanlar ortamdan
ezilemez (bilinçli: yapı değişikliği kod değişikliğidir).
"""
from __future__ import annotations

import dataclasses as dc
import hashlib
import json
import os
import typing
from dataclasses import dataclass, field
from typing import Any, Mapping

from .breakout import BreakoutParams
from .candles import CompletionParams
from .indicators import IndicatorParams
from .levels import LevelParams
from .momentum_daily import MomentumParams
from .pivots import PivotParams
from .trend import TrendParams

ENV_PREFIX = "TA_"


class ConfigError(RuntimeError):
    """Ortam değişkeni geçersiz: servis yanlış parametreyle sessizce çalışmasın."""


@dataclass(frozen=True)
class TechnicalConfig:
    indicators: IndicatorParams = field(default_factory=IndicatorParams)
    completion: CompletionParams = field(default_factory=CompletionParams)
    pivots: PivotParams = field(default_factory=PivotParams)
    trend: TrendParams = field(default_factory=TrendParams)
    momentum_daily: MomentumParams = field(default_factory=MomentumParams)
    levels: LevelParams = field(default_factory=LevelParams)
    breakout: BreakoutParams = field(default_factory=BreakoutParams)
    # üst düzey
    min_daily_rows: int = 35          # gösterge/trend/momentum için asgari tamamlanmış mum
    session_closed_after_min: int = 90  # son 5 dk bar bundan eskiyse piyasa CLOSED sayılır
    cache_ttl_seconds: int = 300      # güvenlik TTL'i; doğruluk anahtardan gelir
    chart_days: int = 0               # 0 = tüm tamamlanmış seri DTO'ya girer
    instrument: str = "GC=F"
    version: str = "technical-v1"

    def config_hash(self) -> str:
        payload = json.dumps(dc.asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "TechnicalConfig":
        env = os.environ if env is None else env
        overrides: dict[str, Any] = {}
        for f in dc.fields(cls):
            default = f.default if f.default is not dc.MISSING else f.default_factory()  # type: ignore[misc]
            if dc.is_dataclass(default):
                nested = _override_dataclass(default, f"{ENV_PREFIX}{f.name.upper()}_", env)
                if nested is not default:
                    overrides[f.name] = nested
            else:
                key = f"{ENV_PREFIX}{f.name.upper()}"
                if key in env:
                    overrides[f.name] = _parse(env[key], f.type, key)
        try:
            return cls(**overrides)
        except (TypeError, ValueError) as error:  # alt sınıfların __post_init__ doğrulamaları
            raise ConfigError(f"Teknik analiz yapılandırması geçersiz: {error}") from error


def _override_dataclass(instance: Any, prefix: str, env: Mapping[str, str]) -> Any:
    changes: dict[str, Any] = {}
    hints = typing.get_type_hints(type(instance))
    for f in dc.fields(instance):
        key = prefix + f.name.upper()
        if key in env:
            changes[f.name] = _parse(env[key], hints.get(f.name, f.type), key)
    if not changes:
        return instance
    try:
        return dc.replace(instance, **changes)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{prefix.rstrip('_')} bloğu geçersiz: {error}") from error


def _parse(raw: str, annotation: Any, key: str) -> Any:
    """Alan tipine göre ayrıştırır; ayrıştırılamayan tip → ConfigError (sessiz kabul yok)."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    try:
        if annotation is bool or annotation == "bool":
            return raw.strip().lower() in ("1", "true", "yes", "on")
        if annotation is int or annotation == "int":
            return int(raw)
        if annotation is float or annotation == "float":
            return float(raw)
        if annotation is str or annotation == "str":
            return raw
        if origin is tuple and args:
            inner = args[0]
            if inner in (int, float):
                return tuple(inner(x) for x in raw.split(",") if x.strip())
            if typing.get_origin(inner) is tuple:  # (ad, ağırlık) çiftleri
                pairs = []
                for item in raw.split(","):
                    name, _, value = item.partition(":")
                    if not _:
                        raise ValueError(f"'{item}' ad:değer biçiminde olmalı")
                    pairs.append((name.strip(), float(value)))
                return tuple(pairs)
    except ValueError as error:
        raise ConfigError(f"{key}={raw!r} ayrıştırılamadı: {error}") from error
    raise ConfigError(f"{key}: bu alan ortamdan ezilemez (tip {annotation})")


CONFIG = TechnicalConfig.from_env()
