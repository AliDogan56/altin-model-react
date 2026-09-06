"""`technical/trend.py` — log fiyat regresyonu, kanal ve trend bloğu.

İlk iki grup `frontend/src/domain/chart/trend.test.ts`'in (15 test) birebir
taşınmasıdır; beklentiler aynı. Sonra blok davranışı (dilimleme, önceki kapanış,
fitil, oluşan kova), etiketler ve fixture: 2026-09-06 günlük serisiyle beş
aralık ve eski arayüzün aynı seriden ürettiği çıktıyla (`trend_expected_…`)
1e-6 toleranslı parite. Formül ya da sabit değişirse parite kırılır; niyet budur.
"""
import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.technical.candles import (
    Candle, Timeframe, aggregate, normalize_daily, period_key,
)
from app.services.technical.trend import (
    CHANNEL_ABOVE_1, CHANNEL_ABOVE_2, CHANNEL_BELOW_1, CHANNEL_BELOW_2, CHANNEL_NEAR,
    DIRECTION_DOWN, DIRECTION_FLAT, DIRECTION_UP, FIT_GOOD, FIT_MODERATE, FIT_WEAK,
    STATUS_INSUFFICIENT_DATA, STATUS_OK, TrendFit, TrendParams, TrendRange, TrendRow,
    band, channel_state, fit_at, fit_state, trend_block, trend_fit,
)

FIXTURES = Path(__file__).parent / "fixtures"
DAILY_FIXTURE = FIXTURES / "xau_daily_20260906.json"
EXPECTED_FIXTURE = FIXTURES / "trend_expected_20260906.json"
TODAY = date(2026, 9, 6)

# vitest `toBeCloseTo(x, 6)` = |a − b| < 5e-7; aynı sıkılık.
CLOSE6 = 5e-7
CLOSE9 = 5e-10


def geometrik(n: int, baslangic: float, oran: float) -> list[float]:
    return [baslangic * oran ** i for i in range(n)]


def mum(gun: date, kapanis: float, yuksek: float | None = None, dusuk: float | None = None) -> Candle:
    return Candle(date=gun, high=kapanis + 1 if yuksek is None else yuksek,
                  low=kapanis - 1 if dusuk is None else dusuk, close=kapanis)


def is_gunleri(baslangic: date, adet: int, kapanislar=None) -> list[Candle]:
    """Hafta içi günlerden oluşan sentetik günlük seri; kapanış verilmezse 100 + i."""
    out: list[Candle] = []
    gun = baslangic
    while len(out) < adet:
        if gun.isoweekday() <= 5:
            i = len(out)
            out.append(mum(gun, 100.0 + i if kapanislar is None else kapanislar[i]))
        gun += timedelta(days=1)
    return out


# --- trendLine (taşınan 9 test) ----------------------------------------------------

def test_sabit_yuzde_buyumede_kusursuz_uyum():
    # Her adımda %2: log uzayında tam doğru.
    t = trend_fit(geometrik(20, 100, 1.02))
    assert t.r2 == pytest.approx(1, abs=CLOSE6)
    assert t.slope_pct == pytest.approx(0.02, abs=CLOSE6)
    assert t.direction == DIRECTION_UP
    assert t.first == pytest.approx(100, abs=CLOSE6)
    assert t.n == 20


def test_gurultulu_seride_uclara_degil_egilime_uyar():
    """Asıl iddia: trend noktaları birleştirmez, genel yönü verir."""
    seri = [100 + i + (8 if i % 2 else -8) for i in range(40)]
    t = trend_fit(seri)
    assert t.direction == DIRECTION_UP
    # Son nokta gürültüyle aşağı sapsa da trend son değeri onu izlemez.
    assert abs(t.last - seri[-1]) > 3
    assert t.r2 > 0.6   # ±8 gürültüde ölçülen: 0,685


def test_dusen_seride_yon_asagidir():
    t = trend_fit(geometrik(15, 200, 0.97))
    assert t.direction == DIRECTION_DOWN
    assert t.slope_pct < 0
    assert t.change_pct < 0


def test_yatay_seride_yon_yatay_ve_uyum_tanimli():
    """Sabit seride kayan nokta yüzünden r² 0 çıkıyordu; eşikle düzeltildi."""
    t = trend_fit([1500.0] * 12)
    assert fit_at(t, 5) == pytest.approx(1500, abs=CLOSE6)
    assert t.direction == DIRECTION_FLAT
    assert t.slope_pct == pytest.approx(0, abs=CLOSE9)
    assert t.r2 == 1


def test_yon_esigi_donem_boyu_toplam_degisimdir():
    """Eşik toplam değişime bakar; kova uzunluğundan bağımsızdır. Önce adım
    başına eğime bakılıyordu ve 90 günde −%6,37 olan gerçek seri yatay çıkıyordu."""
    zayif = trend_fit(geometrik(30, 100, 1.0001))    # 30 adımda toplam %0,3: yatay
    assert zayif.change_pct < 0.01
    assert zayif.direction == DIRECTION_FLAT
    dusen = trend_fit(geometrik(90, 100, 0.99927))   # aynı adım, toplam %6 düşüş
    assert dusen.change_pct < -0.05
    assert dusen.direction == DIRECTION_DOWN


def test_kova_uzunlugu_degisince_yon_karari_degismez():
    # Aynı toplam değişim, farklı nokta sayısı: ikisi de yukarı.
    assert trend_fit([100, 103, 106]).direction == DIRECTION_UP
    assert trend_fit(geometrik(60, 100, 1.001)).direction == DIRECTION_UP


def test_fit_at_uydurulmus_dogruyu_verir_veriyi_degil():
    t = trend_fit([100, 300, 100, 300, 100, 300])
    assert fit_at(t, 0) != 100
    assert fit_at(t, 0) == pytest.approx(t.first, abs=CLOSE9)


def test_yetersiz_ya_da_gecersiz_veride_hata():
    """Arayüzde `null`; burada ValueError — imza `TrendFit` döner, `None` değil."""
    for seri in ([], [100], [0, -5, math.nan], [100, math.nan, 0]):   # sonuncuda tek geçerli nokta
        with pytest.raises(ValueError):
            trend_fit(seri)


def test_r2_dusuk_oldugunda_bunu_bildirir():
    assert trend_fit([100, 180, 95, 190, 92, 200, 90]).r2 < 0.35


# --- regresyon kanalı (taşınan 6 test) ----------------------------------------------

def test_sigma_artiklarin_oransal_yayilimidir():
    # Trend etrafında ±%10 salınan seri: sigma ~0,1 civarında.
    t = trend_fit([100 * (1.1 if i % 2 else 0.9) for i in range(40)])
    assert 0.08 < t.sigma < 0.12


def test_kusursuz_uyumda_kanal_sifir_genislikte():
    t = trend_fit(geometrik(20, 100, 1.02))
    assert t.sigma == pytest.approx(0, abs=CLOSE9)
    alt, ust = band(t, 5, 2)
    assert alt == pytest.approx(fit_at(t, 5), abs=CLOSE6)
    assert ust == pytest.approx(fit_at(t, 5), abs=CLOSE6)


def test_bant_fiyat_ekseninde_carpimsal_acilir():
    """Bant log uzayında simetrik, fiyat ekseninde çarpımsal: %8 sapma yüksek
    fiyatta daha çok dolar eder ve bant öyle açılmalıdır."""
    t = trend_fit([100 * 1.05 ** i + (i % 3) * 4 for i in range(30)])
    ust_bas = band(t, 0, 1)[1] - fit_at(t, 0)
    ust_son = band(t, 29, 1)[1] - fit_at(t, 29)
    assert ust_son > ust_bas
    # oran ise sabit
    assert band(t, 0, 1)[1] / fit_at(t, 0) == pytest.approx(band(t, 29, 1)[1] / fit_at(t, 29), abs=CLOSE9)


def test_band_i_0_trend_cizgisinin_kendisidir():
    t = trend_fit([100, 120, 110, 140, 130])
    alt, ust = band(t, 3, 0)
    assert alt == pytest.approx(fit_at(t, 3), abs=CLOSE9)
    assert ust == pytest.approx(fit_at(t, 3), abs=CLOSE9)


def test_last_z_son_gozlemin_kanaldaki_yerini_verir():
    temiz = geometrik(30, 100, 1.01)
    ustunde = trend_fit(temiz[:29] + [temiz[29] * 1.25])
    altinda = trend_fit(temiz[:29] + [temiz[29] * 0.8])
    assert ustunde.last_z > 1
    assert altinda.last_z < -1


def test_yatay_seride_kanal_sifir_ve_konum_sifirdir():
    t = trend_fit([2000.0] * 12)
    assert t.sigma == 0
    assert t.last_z == 0
    alt, ust = band(t, 4, 2)
    # exp(log(2000)) kayan noktada tam 2000 değil; kanal genişliği sıfır olması yeter.
    assert alt == pytest.approx(2000, abs=CLOSE6)
    assert alt == fit_at(t, 4) and ust == fit_at(t, 4)


# --- fit_at / band şekli ve kaynağa sadakat ----------------------------------------

def test_band_alt_ust_sirali_ve_k_ile_simetrik():
    t = trend_fit([100, 130, 105, 140, 120, 160])
    assert t.sigma > 0
    alt, ust = band(t, 2, 1.5)
    merkez = fit_at(t, 2)
    assert alt < merkez < ust
    assert ust / merkez == pytest.approx(math.exp(1.5 * t.sigma), abs=CLOSE9)
    assert merkez / alt == pytest.approx(math.exp(1.5 * t.sigma), abs=CLOSE9)
    assert alt * ust == pytest.approx(merkez * merkez, rel=1e-12)  # log uzayında simetri


def test_gecersiz_noktalar_atlanir_ama_dizin_korunur():
    """Kaynakla aynı: atlanan nokta x eksenini kaydırmaz, `last` girdinin SON
    dizinine uzatılır (geçerli nokta sayısına değil)."""
    temiz = geometrik(10, 100, 1.02)
    delikli = list(temiz)
    delikli[4] = math.nan
    delikli[9] = 0.0            # son nokta geçersiz
    t = trend_fit(delikli)
    assert t.n == 8
    assert t.slope_pct == pytest.approx(0.02, abs=CLOSE6)
    assert t.last == pytest.approx(temiz[9], abs=CLOSE6)   # 9. dizine uzatılmış
    assert t.first == pytest.approx(100, abs=CLOSE6)


def test_bool_ve_metin_sayi_sayilmaz():
    with pytest.raises(ValueError):
        trend_fit([True, False, "100"])


def test_sigma_populasyon_sapmasidir_ddof_0():
    seri = [100, 110, 95, 120, 105]
    t = trend_fit(seri)
    ys = [math.log(v) for v in seri]
    artiklar = [y - (t.intercept + t.slope * i) for i, y in enumerate(ys)]
    assert t.sigma == pytest.approx(math.sqrt(sum(e * e for e in artiklar) / len(seri)), abs=1e-12)
    assert t.last_z == pytest.approx(artiklar[-1] / t.sigma, abs=1e-12)


def test_flat_limit_parametrelenir():
    seri = geometrik(10, 100, 1.005)   # toplam ~%4,6
    assert trend_fit(seri).direction == DIRECTION_UP
    assert trend_fit(seri, TrendParams(flat_limit=0.05)).direction == DIRECTION_FLAT


def test_fit_donmus_ve_deterministik():
    t = trend_fit([100, 120, 110])
    assert isinstance(t, TrendFit)
    with pytest.raises(AttributeError):
        t.slope = 0.0  # type: ignore[misc]
    assert trend_fit([100, 120, 110]) == t


# --- etiketler ----------------------------------------------------------------------

@pytest.mark.parametrize("z, beklenen", [
    (2.5, CHANNEL_ABOVE_2), (2.0, CHANNEL_ABOVE_1), (1.5, CHANNEL_ABOVE_1),
    (1.0, CHANNEL_NEAR), (0.0, CHANNEL_NEAR), (-1.0, CHANNEL_NEAR),
    (-1.5, CHANNEL_BELOW_1), (-2.0, CHANNEL_BELOW_1), (-2.5, CHANNEL_BELOW_2),
])
def test_kanal_konumu_esikleri_katidir(z, beklenen):
    assert channel_state(z) == beklenen


@pytest.mark.parametrize("r2, beklenen", [
    (1.0, FIT_GOOD), (0.75, FIT_GOOD), (0.7499, FIT_MODERATE), (0.40, FIT_MODERATE),
    (0.3999, FIT_WEAK), (0.0, FIT_WEAK),
])
def test_uyum_etiketi_esikleri(r2, beklenen):
    assert fit_state(r2) == beklenen


def test_etiket_esikleri_parametrelenir():
    p = TrendParams(channel_z=(0.5, 3.0), fit_r2=(0.9, 0.5))
    assert channel_state(0.7, p) == CHANNEL_ABOVE_1
    assert channel_state(2.9, p) == CHANNEL_ABOVE_1
    assert channel_state(-3.1, p) == CHANNEL_BELOW_2
    assert fit_state(0.8, p) == FIT_MODERATE
    assert fit_state(0.49, p) == FIT_WEAK


# --- trend_block: dilimleme ve satırlar --------------------------------------------

def test_varsayilan_aralik_tanimlari():
    ids = [r[0] for r in TrendParams().ranges]
    assert ids == ["gunluk", "haftalik", "aylik", "ceyreklik", "yarim"]
    assert {r[0]: (r[1], r[2]) for r in TrendParams().ranges} == {
        "gunluk": (Timeframe.DAILY, 90), "haftalik": (Timeframe.WEEKLY, 104),
        "aylik": (Timeframe.MONTHLY, 60), "ceyreklik": (Timeframe.QUARTERLY, 24),
        "yarim": (Timeframe.SEMIANNUAL, 12),
    }


def test_blok_anahtarlari_sirali_ve_candles_yalniz_gunlukte():
    seri = is_gunleri(date(2026, 1, 5), 30)
    blok = trend_block(seri, date(2026, 3, 1))
    assert list(blok) == ["gunluk", "haftalik", "aylik", "ceyreklik", "yarim"]
    for rid, rng in blok.items():
        assert isinstance(rng, TrendRange) and rng.id == rid
        assert rng.candles is (rng.timeframe is Timeframe.DAILY)


def test_son_n_kova_dilimlenir_ve_ilk_satirin_pc_si_dilimden_onceki_kovadan_gelir():
    seri = is_gunleri(date(2026, 1, 5), 100)   # 100 gün, gunluk 90 ister
    blok = trend_block(seri, date(2026, 6, 1))
    g = blok["gunluk"]
    assert g.status == STATUS_OK and len(g.rows) == 90
    assert g.rows[0].d == seri[10].date and g.rows[-1].d == seri[-1].date
    # 9. günün kapanışı (dilimin hemen öncesi) ilk gövdenin diğer ucu.
    assert g.rows[0].pc == seri[9].close
    for onceki, satir in zip(g.rows, g.rows[1:]):
        assert satir.pc == onceki.c


def test_seri_dilimden_kisaysa_hepsi_alinir_ve_ilk_pc_none():
    seri = is_gunleri(date(2026, 1, 5), 20)
    g = trend_block(seri, date(2026, 6, 1))["gunluk"]
    assert len(g.rows) == 20 and g.rows[0].pc is None
    assert g.fit is not None and g.fit.n == 20


def test_fitil_govdeyi_kapsar():
    """wh = max(h, c, pc), wl = min(l, c, pc): önceki kapanış günün aralığının
    dışındaysa (hafta sonu boşluğu) fitil oraya kadar uzar."""
    seri = [mum(date(2026, 1, 5), 100, 101, 99),
            mum(date(2026, 1, 6), 120, 121, 119),     # boşlukla açıldı: 100 → 120
            mum(date(2026, 1, 7), 110, 111, 109),
            mum(date(2026, 1, 8), 112, 113, 111)]
    g = trend_block(seri, date(2026, 2, 1))["gunluk"]
    ilk, ikinci, ucuncu = g.rows[0], g.rows[1], g.rows[2]
    assert (ilk.pc, ilk.wh, ilk.wl) == (None, 101, 99)
    assert (ikinci.pc, ikinci.wh, ikinci.wl) == (100, 121, 100)
    assert (ucuncu.pc, ucuncu.wh, ucuncu.wl) == (120, 120, 109)
    for satir in g.rows:
        assert satir.wl <= min(satir.l, satir.c) and satir.wh >= max(satir.h, satir.c)


def test_satirdaki_fit_ve_bantlar_fonksiyonlarla_ayni():
    seri = is_gunleri(date(2026, 1, 5), 12, [100, 104, 101, 108, 106, 112, 109, 115, 118, 114, 121, 125])
    g = trend_block(seri, date(2026, 2, 1))["gunluk"]
    z1, z2 = TrendParams().channel_z
    for i, satir in enumerate(g.rows):
        assert isinstance(satir, TrendRow)
        assert satir.fit == fit_at(g.fit, i)
        assert satir.b1 == band(g.fit, i, z1) and satir.b2 == band(g.fit, i, z2)
        assert satir.b2[0] <= satir.b1[0] <= satir.fit <= satir.b1[1] <= satir.b2[1]
    assert g.fit.direction == DIRECTION_UP
    assert g.realized_pct == pytest.approx(125 / 100 - 1, abs=1e-12)
    assert g.channel_state == channel_state(g.fit.last_z)
    assert g.fit_state == fit_state(g.fit.r2)


def test_gerceklesen_degisim_ilk_ve_son_kapanistir_trend_uclari_degil():
    """Karttaki sayı gerçekleşen değişim; trend uçları farklı ve fark büyük
    olabilir (ölçüldü: 60 aylık seride ham %148, trend uçları %203)."""
    kapanislar = [100, 150, 90, 160, 95, 170, 92, 180, 96, 190]
    g = trend_block(is_gunleri(date(2026, 1, 5), 10, kapanislar), date(2026, 2, 1))["gunluk"]
    assert g.realized_pct == pytest.approx(0.9, abs=1e-12)
    assert g.fit.change_pct != pytest.approx(0.9, abs=1e-3)


def test_yetersiz_veride_insufficient_ve_satir_yok():
    seri = is_gunleri(date(2026, 1, 5), 2)
    for rng in trend_block(seri, date(2026, 2, 1)).values():
        assert rng.status == STATUS_INSUFFICIENT_DATA
        assert rng.fit is None and rng.realized_pct is None
        assert rng.channel_state is None and rng.fit_state is None
        assert rng.rows == ()
    assert trend_block([], date(2026, 2, 1))["gunluk"].status == STATUS_INSUFFICIENT_DATA
    # Üç nokta yeter (min_points varsayılanı).
    assert trend_block(is_gunleri(date(2026, 1, 5), 3), date(2026, 2, 1))["gunluk"].status == STATUS_OK


def test_min_points_parametrelenir():
    seri = is_gunleri(date(2026, 1, 5), 5)
    assert trend_block(seri, date(2026, 2, 1), TrendParams(min_points=6))["gunluk"].status == STATUS_INSUFFICIENT_DATA
    assert trend_block(seri, date(2026, 2, 1), TrendParams(min_points=5))["gunluk"].status == STATUS_OK


def test_olusan_son_kova_bildirilir():
    """`today` kovanın takvim sonunu geçmediyse son kova oluşuyor demektir."""
    seri = is_gunleri(date(2026, 8, 3), 15)          # 3 Ağustos → 21 Ağustos (cuma)
    son = seri[-1].date
    assert son == date(2026, 8, 21)
    # Çağıran oluşan günü zaten çıkarır: bugün son mumdan sonraysa günlük oluşmuyor.
    ertesi = trend_block(seri, son + timedelta(days=1))
    assert ertesi["gunluk"].last_bucket_forming is False
    assert ertesi["gunluk"].rows[-1].complete is True
    # Hafta takvimce pazar biter: cumartesi 22'de period_end (23) >= today → oluşuyor.
    assert ertesi["haftalik"].last_bucket_forming is True
    assert ertesi["haftalik"].rows[-1].complete is False
    assert ertesi["haftalik"].rows[-2].complete is True
    # Son mumun gününde günlük kova da oluşuyor sayılır.
    assert trend_block(seri, son)["gunluk"].last_bucket_forming is True
    # Ay bitince ay tamamlanır.
    assert trend_block(seri, date(2026, 9, 1))["aylik"].last_bucket_forming is False
    assert trend_block(seri, date(2026, 8, 31))["aylik"].last_bucket_forming is True


def test_toplanmis_kovalarin_tarihi_donem_basidir_ve_ohlc_toplamayla_ayni():
    seri = is_gunleri(date(2026, 1, 5), 40)
    h = trend_block(seri, date(2026, 6, 1))["haftalik"]
    haftalar = aggregate(seri, Timeframe.WEEKLY)
    assert [r.d for r in h.rows] == [c.date for c in haftalar]
    assert all(r.d.isoweekday() == 1 for r in h.rows)
    assert [(r.h, r.l, r.c) for r in h.rows] == [(c.high, c.low, c.close) for c in haftalar]


def test_sirasiz_girdi_ayni_sonucu_verir():
    seri = is_gunleri(date(2026, 1, 5), 30)
    duz = trend_block(seri, date(2026, 6, 1))
    ters = trend_block(list(reversed(seri)), date(2026, 6, 1))
    assert duz == ters


def test_aralik_listesi_parametrelenir():
    p = TrendParams(ranges=(("kisa", Timeframe.DAILY, 5),))
    blok = trend_block(is_gunleri(date(2026, 1, 5), 30), date(2026, 6, 1), p)
    assert list(blok) == ["kisa"] and blok["kisa"].bars == 5 and len(blok["kisa"].rows) == 5


# --- fixture: 2026-09-06 -------------------------------------------------------------

@pytest.fixture(scope="module")
def fixture_mumlari() -> list[Candle]:
    noktalar = json.loads(DAILY_FIXTURE.read_text(encoding="utf-8"))["points"]
    candles, quality = normalize_daily(noktalar)
    assert quality.status == STATUS_OK and len(candles) == 1257
    return candles


@pytest.fixture(scope="module")
def blok(fixture_mumlari) -> dict[str, TrendRange]:
    return trend_block(fixture_mumlari, TODAY)


def test_fixture_bes_aralik_ok(blok):
    assert set(blok) == {"gunluk", "haftalik", "aylik", "ceyreklik", "yarim"}
    for rng in blok.values():
        assert rng.status == STATUS_OK, rng.id
        assert rng.fit is not None and rng.rows and rng.realized_pct is not None
        assert rng.fit.n == len(rng.rows)
        assert rng.channel_state is not None and rng.fit_state is not None
    g, h = blok["gunluk"], blok["haftalik"]
    assert g.candles is True and len(g.rows) == 90
    assert h.candles is False and len(h.rows) == 104
    assert len(blok["aylik"].rows) == 60
    # Beş yıllık seri 24 çeyrek / 12 yarıyıl vermez; olan kadarı alınır.
    assert len(blok["ceyreklik"].rows) == 21 and len(blok["yarim"].rows) == 11


def test_fixture_gunluk_pencere_ve_olusan_kova(blok):
    g = blok["gunluk"]
    assert g.rows[0].d == date(2026, 4, 29) and g.rows[-1].d == date(2026, 9, 4)
    assert g.rows[0].pc is not None          # 28 Nisan kapanışı dilimin hemen öncesi
    # Son mum cuma 4 Eylül, bugün pazar 6 Eylül: günlük kova oluşmuyor.
    assert g.last_bucket_forming is False and all(r.complete for r in g.rows)


def test_fixture_gunluk_yon_asagi(blok):
    """90 günlük pencerede yön aşağı. Trend çizgisinin toplam değişimi ≈ −%5,2;
    gerçekleşen (ilk→son kapanış) ise −%1,5 — haritadaki −%6,37 daha eski
    veriyle ölçülmüştü; eski arayüzün aynı seriden ürettiği fixture da −%1,51
    diyor (aşağıdaki parite testi). Dilimleme doğrulandı: 2026-04-29 → 09-04."""
    g = blok["gunluk"]
    assert g.fit.direction == DIRECTION_DOWN
    assert -0.08 < g.fit.change_pct < -0.04
    assert g.realized_pct == pytest.approx(g.rows[-1].c / g.rows[0].c - 1, abs=1e-12)
    assert -0.03 < g.realized_pct < 0
    assert g.fit_state == FIT_WEAK          # r² ≈ 0,09: 90 günde dağınık seyir


def test_fixture_deterministik(fixture_mumlari, blok):
    assert trend_block(fixture_mumlari, TODAY) == blok


# --- parite: eski arayüzün ürettiği çıktı ---------------------------------------------

FIT_KEYS = {"slopePct": "slope_pct", "first": "first", "last": "last", "r2": "r2",
            "changePct": "change_pct", "sigma": "sigma", "lastZ": "last_z"}


@pytest.fixture(scope="module")
def beklenen() -> dict:
    if not EXPECTED_FIXTURE.exists():
        pytest.skip(f"{EXPECTED_FIXTURE.name} yok: eski arayüz çıktısı henüz üretilmedi")
    return json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("rid", ["gunluk", "haftalik", "aylik", "ceyreklik", "yarim"])
def test_parite_eski_arayuz_ciktisiyla(blok, beklenen, rid):
    """Aynı seriden `trend.ts` + `TrendSection.tsx`'in ürettiği sayılarla 1e-6.

    Satır tarihlerinde bilinçli fark: arayüz kovanın ilk mumunun tarihini
    yazıyordu, backend dönem başını (`Candle.date` sözleşmesi); ikisi aynı
    döneme düşmeli. Günlükte tarih birebir aynı.
    """
    rng, e = blok[rid], beklenen[rid]
    assert e["bars"] == rng.bars and e["observations"] == len(rng.rows)
    assert rng.fit.direction == e["fit"]["direction"].upper()
    for js_key, py_key in FIT_KEYS.items():
        assert getattr(rng.fit, py_key) == pytest.approx(e["fit"][js_key], abs=1e-6), js_key
    assert rng.realized_pct == pytest.approx(e["realizedPct"], abs=1e-6)

    assert len(rng.rows) == len(e["rows"]) == len(e["fitLine"]) == len(e["band1"]) == len(e["band2"])
    for i, (row, er) in enumerate(zip(rng.rows, e["rows"])):
        js_date = date.fromisoformat(er["date"])
        assert period_key(js_date, rng.timeframe) == row.d, (rid, i)
        if rng.timeframe is Timeframe.DAILY:
            assert row.d == js_date
        assert (row.h, row.l, row.c) == (er["h"], er["l"], er["c"]), (rid, i)
        assert row.fit == pytest.approx(e["fitLine"][i], abs=1e-6), (rid, i)
        assert list(row.b1) == pytest.approx(e["band1"][i], abs=1e-6), (rid, i)
        assert list(row.b2) == pytest.approx(e["band2"][i], abs=1e-6), (rid, i)
