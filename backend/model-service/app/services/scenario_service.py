"""Model senaryosu bölgeleri: tahmin bandının geometrisi, destek/direnç değil.

Bu hesap önceden yalnız tarayıcıdaydı (`frontend/src/domain/tradeZones.ts`).
Buraya taşınmasının sebebi bölgelerin ne olduğuyla ilgili:

- Bölgeler **modelin bandından** türer: `near = fiyat · (1 + ortalama)`,
  `band = fiyat · hata`; alım/satış aralıkları bu bandın sabit oranlarıdır.
  Fiyatın fiilen döndüğü seviyeler (pivot merdiveni) değildir; o iş
  `domain/pivots.ts` ve momentum servisinde kalır. Bandı üreten tek yer
  model servisi olduğu için bandın geometrisi de onunla aynı yerde ve aynı
  çapada (`base_price`) üretilir.
- İstemci bölgeleri `values.price` ile hesaplıyordu; bu, her Harem tick'inde
  güncellenen canlı satış fiyatıdır (`useForecastModel`: `setField('price',
  spotPrice)`). `mean`/`err` ise 700 ms debounce ile **istek anındaki** fiyata
  göre üretilmiş ve fiyat tick'i istek imzasını değiştirmediği için orada
  kalıyordu (`computeFeatures` `price` alanını atlar). Yani bölgeler her
  tick'te kayarken bandın çapası sabit duruyor, iki fiyat çerçevesi
  karışıyordu. Üstüne ATR oranı kapanış serisinden (xaus.com / GC=F) türeyip
  Harem spotuyla çarpılıyordu. Sunucu yanıtı tek çapaya bağlıdır:
  `base_price`, `mean`, `error` ve `scenario_zones` aynı fiyatla konuşur;
  canlı spot arayüzde ayrı gösterilir ("Hesaplama referansı").
- `gold_atr14_pct` **fiyatın kesridir** (`xau_dataset_service._gold_features`:
  `fmean(true_ranges) / close`; veri setinde 0,005–0,055 aralığında), yüzde
  değil. `atr = atr_pct · fiyat` bu yüzden dolar verir.

Sabitler editoryal tercihtir, model çıktısı değildir; `SCENARIO_*` ortam
değişkenleriyle değiştirilebilir ve hangi geometriyle üretildiği yanıtta
`params_version` olarak gider. Bu modül modele, artefakta ve girdi
tanımlarına dokunmaz; yalnız hazır `mean`/`error`/`confident` üzerinden
saf aritmetik yapar. Pozisyon büyüklüğü (portföy × risk ÷ birim risk)
kullanıcı girdisi olduğu için istemcide kalır; sunucu yalnız
`risk_per_unit` verir.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from numbers import Real

PARAMS_VERSION = "scenario-v1"
ENV_PREFIX = "SCENARIO_"


@dataclass(frozen=True)
class ScenarioParams:
    """Bant oranları; `frontend/src/domain/tradeZones.ts` ile birebir.

    buy  = [near − buy_low·band,  near − buy_high·band]
    sell = [near + sell_low·band, near + sell_high·band]
    stop = buy[0] − max(stop_atr·atr, stop_band·band)
    risk_per_unit = max(min_risk, entry − stop)
    """
    buy_low: float = 0.72
    buy_high: float = 0.38
    sell_low: float = 0.35
    sell_high: float = 0.72
    stop_atr: float = 1.5
    stop_band: float = 0.18
    min_risk: float = 1.0


def params_from_env(environ: Mapping[str, str] | None = None) -> ScenarioParams:
    """`SCENARIO_<ALAN>` değişkenlerini okur; bozuk değer yanlış geometriyle
    sessizce çalışmak yerine servisi açılışta durdurur."""
    source = os.environ if environ is None else environ
    values: dict[str, float] = {}
    for field in fields(ScenarioParams):
        key = ENV_PREFIX + field.name.upper()
        raw = source.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise RuntimeError(f"{key} ondalık sayı olmalı, alınan: {raw!r}") from None
        if not math.isfinite(value) or value < 0:
            raise RuntimeError(f"{key} sonlu ve negatif olmayan bir sayı olmalı, alınan: {raw!r}")
        values[field.name] = value
    return ScenarioParams(**values)


PARAMS = params_from_env()


def _finite(*values: float) -> bool:
    return all(isinstance(value, Real) and math.isfinite(value) for value in values)


def scenario_zones(price: float, mean: float, err: float, atr_pct: float, confident: bool,
                   params: ScenarioParams | None = None) -> dict | None:
    """Tek ufuk için bölgeler; görüş yoksa ya da girdi sonlu değilse `None`.

    `None` "sıfır bölge" değil "bölge üretilmedi" demektir: ağırlığı kısılmış
    ufukta bandın ortası anlamsızdır ve istemci bunu "görüş yok" olarak yazar.
    Değerler dolar cinsinden 2 ondalığa yuvarlanır.
    """
    params = PARAMS if params is None else params
    if not confident:
        return None
    if not _finite(price, mean, err, atr_pct) or price <= 0:
        return None
    price, mean, err, atr_pct = float(price), float(mean), float(err), float(atr_pct)
    near = price * (1 + mean)
    band = price * err
    atr = atr_pct * price
    buy = (near - band * params.buy_low, near - band * params.buy_high)
    sell = (near + band * params.sell_low, near + band * params.sell_high)
    stop = buy[0] - max(atr * params.stop_atr, band * params.stop_band)
    entry = (buy[0] + buy[1]) / 2
    risk_per_unit = max(params.min_risk, entry - stop)
    cents = lambda value: round(float(value), 2)  # noqa: E731 — tek satırlık yuvarlama
    return {"near": cents(near), "band": cents(band), "atr": cents(atr),
            "buy": [cents(buy[0]), cents(buy[1])], "sell": [cents(sell[0]), cents(sell[1])],
            "stop": cents(stop), "entry": cents(entry), "risk_per_unit": cents(risk_per_unit),
            "params_version": PARAMS_VERSION}
