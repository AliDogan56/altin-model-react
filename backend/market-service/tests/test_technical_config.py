import pytest

from app.services.technical.config import CONFIG, ConfigError, TechnicalConfig


def test_varsayilan_hash_kararli():
    a, b = TechnicalConfig(), TechnicalConfig()
    assert a.config_hash() == b.config_hash() == CONFIG.config_hash() and len(a.config_hash()) == 12


def test_ic_ice_alan_ortamdan_ezilir_ve_hash_degisir():
    cfg = TechnicalConfig.from_env({"TA_LEVELS_MIN_STRENGTH": "35", "TA_INDICATORS_RSI_PERIOD": "21",
                                    "TA_BREAKOUT_WEIGHT_SESSION": "1", "TA_BREAKOUT_WEIGHT_DAILY": "0"})
    assert cfg.levels.min_strength == 35 and cfg.indicators.rsi_period == 21
    assert cfg.breakout.weight_session == 1.0 and cfg.breakout.weight_daily == 0.0
    assert cfg.config_hash() != TechnicalConfig().config_hash()
    assert cfg.pivots == TechnicalConfig().pivots  # dokunulmayan blok aynı nesne semantiğinde


def test_ust_duzey_alanlar():
    cfg = TechnicalConfig.from_env({"TA_CACHE_TTL_SECONDS": "60", "TA_INSTRUMENT": "XAUUSD", "TA_CHART_DAYS": "260"})
    assert (cfg.cache_ttl_seconds, cfg.instrument, cfg.chart_days) == (60, "XAUUSD", 260)


def test_demet_ve_agirlik_ayristirma():
    cfg = TechnicalConfig.from_env({"TA_INDICATORS_MA_PERIODS": "5,20,50",
                                    "TA_MOMENTUM_DAILY_WEIGHTS": "velocity:0.5,drift:0.5"})
    assert cfg.indicators.ma_periods == (5, 20, 50)
    assert cfg.momentum_daily.weights == (("velocity", 0.5), ("drift", 0.5))


def test_gecersiz_deger_hata_verir():
    with pytest.raises(ConfigError):
        TechnicalConfig.from_env({"TA_LEVELS_MIN_STRENGTH": "otuz"})
    with pytest.raises(ConfigError):  # ağırlık toplamı 1 değil → alt sınıf doğrulaması
        TechnicalConfig.from_env({"TA_MOMENTUM_DAILY_WEIGHTS": "velocity:0.9,drift:0.5"})
    with pytest.raises(ConfigError):  # bileşik alan ortamdan ezilemez
        TechnicalConfig.from_env({"TA_TREND_RANGES": "x"})


def test_ilgisiz_ortam_degiskeni_yok_sayilir():
    assert TechnicalConfig.from_env({"TA_BILINMEYEN": "1", "PATH": "/x"}) == TechnicalConfig()
