"""Geriye dönük uyumluluk katmanı — asıl uygulama `technical/session.py`.

Bu dosya yalnız eski içe aktarma yolunun (`app.services.momentum_service`) ve ona
bağlı 37 testin, denetleyici `technical.session`'a geçene kadar çalışmaya devam
etmesi için var. Burada hesap yok: her ad `technical.session`'dan olduğu gibi,
aynı nesne olarak yeniden dışa verilir — alt çizgili yardımcılar dahil, çünkü
eski testler `_complete_days` gibi adları da içe aktarıyor. Yeni kod bu modülü
değil `app.services.technical.session`'ı içe aktarmalı.
"""
from .technical import session as _session
from .technical.session import *  # noqa: F401,F403

# Denetleyicinin ve `tests/test_momentum_service.py`'nin kullandığı adların açık
# listesi; okuyucu ve statik çözümleyici için. Yıldızlı içe aktarma alt çizgili
# adları atlar, o yüzden `_complete_days` burada ayrıca sayılır.
from .technical.session import (  # noqa: F401
    Bar, CLUSTER_BARS, EPS, MACD_FAST, MACD_SIGNAL, MACD_SLOW, MIN_BARS, RSI_PERIOD,
    SWING_LOOKBACK, SWING_WING, WEIGHTS, WINDOW,
    _complete_days, _components, _ema, _logistic, _mean, _stdev, _volume_confirmation,
    build_levels, cluster_levels, daily_pivots, last_complete_week, log_returns,
    macd_histogram, momentum, nearest_levels, parse_bars, rsi, session_drift,
    swing_levels,
)

# `import app.services.momentum_service as m; m._complete_days` gibi erişimler de
# çözülsün diye seans modülünün dunder dışı tüm adları modül sözlüğüne kopyalanır.
globals().update({name: getattr(_session, name) for name in dir(_session)
                  if not name.startswith("__")})
__all__ = [name for name in dir(_session) if not name.startswith("_")]
