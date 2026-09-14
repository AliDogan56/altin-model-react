"""Veri kaynakları, seriler ve teknik hesap sabitleri (editoryal tercihler; eşik değil ölçek)."""
from .config import settings

ROOT = settings.data_dir
DATA_DIR = settings.data_dir / "market"
LATEST_DIR = settings.data_dir / "latest"
LEDGER_DIR = settings.data_dir / "ledger"
VERSIONS_DIR = settings.data_dir / "versions"
CALENDAR_PATH = settings.calendar_path
PROMPTS_DIR = settings.llm_config_path.parent / "app" / "prompts"

PRICES_CSV = DATA_DIR / "prices_daily.csv"      # LBMA PM spot + GC=F OHLCV + basis
MARKET_CSV = DATA_DIR / "market_daily.csv"      # DXY, VIX, WTI, 10y nominal (Yahoo)
MACRO_CSV = DATA_DIR / "macro_obs.csv"          # FRED gözlemleri, available_at ile

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

LBMA_PM_URL = "https://prices.lbma.org.uk/json/gold_pm.json"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_PERIOD1 = 946684800  # 2000-01-01

YAHOO_MARKET_SYMBOLS = {
    "DX-Y.NYB": "dxy",
    "^VIX": "vix",
    "CL=F": "wti",
    "^TNX": "us10y_nominal",
}

# FRED serileri ve yaklaşık yayın gecikmesi (takvim günü). available_at = obs_date + lag.
# Gerçek vintage için ALFRED gerekir; bu değerler muhafazakâr yaklaşıklardır.
FRED_SERIES = {
    "DFII10":   {"lag_days": 1,  "freq": "günlük",  "desc": "10y TIPS reel getiri"},
    "DGS10":    {"lag_days": 1,  "freq": "günlük",  "desc": "10y nominal getiri"},
    "DGS2":     {"lag_days": 1,  "freq": "günlük",  "desc": "2y nominal getiri"},
    "T10YIE":   {"lag_days": 1,  "freq": "günlük",  "desc": "10y breakeven enflasyon"},
    "T5YIE":    {"lag_days": 1,  "freq": "günlük",  "desc": "5y breakeven enflasyon"},
    "T10Y2Y":   {"lag_days": 1,  "freq": "günlük",  "desc": "10y-2y eğri"},
    "DTWEXBGS": {"lag_days": 7,  "freq": "günlük",  "desc": "Geniş dolar endeksi (H.10, haftalık yayın)"},
    "VIXCLS":   {"lag_days": 1,  "freq": "günlük",  "desc": "VIX kapanış"},
    "DCOILWTICO": {"lag_days": 3, "freq": "günlük", "desc": "WTI spot"},
    "WALCL":    {"lag_days": 1,  "freq": "haftalık", "desc": "Fed bilançosu toplam varlık"},
    "M2SL":     {"lag_days": 28, "freq": "aylık",   "desc": "M2 para arzı"},
    "CPIAUCSL": {"lag_days": 42, "freq": "aylık",   "desc": "TÜFE manşet (SA)"},
    "CPILFESL": {"lag_days": 42, "freq": "aylık",   "desc": "TÜFE çekirdek (SA)"},
    "PCEPI":    {"lag_days": 58, "freq": "aylık",   "desc": "PCE fiyat endeksi"},
}
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
TREASURY_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type={kind}&field_tdr_date_value={year}&page&_format=csv"
)

ATR_PERIOD = 14
SWING_WING_DAILY = 5
SWING_WING_WEEKLY = 3
LEVEL_TOL_ATR = 0.5
TOUCH_MARGIN_ATR = 0.3
MOMENTUM_WINDOWS = {"daily": 252, "weekly": 156, "monthly": 120}
CHANNEL_WINDOWS = (60, 120, 250)
