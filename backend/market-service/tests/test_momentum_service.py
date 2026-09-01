"""Gün içi momentum hesabı.

Kritik davranış: eşikler sabit değil, o seansın oynaklığına göre uyarlanır.
Aynı dolar hareketi sakin seansta güçlü, çalkantılı seansta zayıf okunmalı.
"""
import math
from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.momentum_service import (
    MIN_BARS, cluster_levels, daily_pivots, last_complete_week, macd_histogram,
    momentum, nearest_levels, rsi,
)

BASLANGIC = datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)
ONCEKI = datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc)


def mumlar(kapanislar, *, baslangic=BASLANGIC, hacim=100, aralik=0.4):
    """Verilen kapanışlardan 5 dakikalık mum listesi üretir."""
    out = []
    for i, c in enumerate(kapanislar):
        t = baslangic + timedelta(minutes=5 * i)
        out.append({"t": t.isoformat(), "o": c, "h": c + aralik, "l": c - aralik,
                    "c": c, "v": hacim})
    return out


def duz_seri(n, baslangic=4400.0, adim=0.0, gurultu=0.0):
    return [baslangic + adim * i + (gurultu if i % 2 else -gurultu) for i in range(n)]


def onceki_seans(n=120, taban=4400.0):
    """Gerçekçi bir önceki seans: ~%1,5 gün içi aralık.

    Düz bir önceki seans pivot merdivenini birkaç dolara sıkıştırır ve fiyat
    hemen merdivenin dışına çıkar; o zaman "ilk direnç" diye bir şey kalmaz.
    """
    orta = n // 2
    seri = [taban + 30 * math.sin(i / orta * math.pi) for i in range(n)]
    return mumlar(seri, baslangic=ONCEKI, aralik=2.0)


# --- temel sözleşme -----------------------------------------------------------

def test_yetersiz_mumda_hata_verir():
    with pytest.raises(ValueError, match="en az"):
        momentum(mumlar(duz_seri(MIN_BARS - 1)))


def test_oynaklik_sifirsa_hata_verir():
    # Tamamen sabit fiyat: normalize edecek bir ölçek yok.
    with pytest.raises(ValueError, match="oynaklık"):
        momentum(mumlar([4400.0] * (MIN_BARS + 40)))


def test_yanit_beklenen_alanlari_tasir():
    out = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.12, gurultu=0.3)))
    assert set(out) >= {"as_of", "price", "direction", "strength", "trend",
                        "support", "resistance", "breakout", "components", "session"}
    assert out["direction"] in {"UP", "DOWN", "NEUTRAL"}
    assert 0 <= out["strength"] <= 100
    assert out["trend"] in {"STRENGTHENING", "WEAKENING", "STABLE"}


# --- yön ----------------------------------------------------------------------

def test_istikrarli_yukselis_UP_verir():
    out = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.5, gurultu=0.2)))
    assert out["direction"] == "UP"
    assert out["strength"] > 50


def test_guc_surukleme_ile_birlikte_artar():
    """Yön ayırt edilebilir olsa da güç hareketin büyüklüğünü izlemeli.

    Mutlak bir eşik yerine sıralama denetlenir: eşik yazmak, bileşen kümesi
    her değiştiğinde testi kırar ama asıl iddiayı ölçmez.
    """
    guc = [momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=a, gurultu=0.2)))["strength"]
           for a in (0.15, 0.30, 0.50)]
    assert guc == sorted(guc), guc
    assert guc[0] < guc[-1] - 20, guc


def test_istikrarli_dusus_DOWN_verir():
    out = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=-0.5, gurultu=0.2)))
    assert out["direction"] == "DOWN"
    assert out["strength"] > 50


def test_suruklenmesiz_seri_NEUTRAL_verir():
    """Fiyat gidip geliyor ama hiçbir yere varmıyor: yön uydurulmamalı.

    Yalnız t istatistiğine bakmak yetmiyordu — küçük ama tutarlı bileşenler
    t'yi 1'in üstüne çıkarıp sahte yön üretiyordu (ölçüldü: hız 0,00 iken UP).
    """
    seri = [4400 + (2 if i % 4 in (0, 1) else -2) for i in range(90)]
    out = momentum(onceki_seans() + mumlar(seri))
    assert out["direction"] == "NEUTRAL"
    assert out["strength"] < 10


def test_ayni_suruklenme_calkantida_yon_bile_vermez():
    """Uyarlanabilirliğin en net kanıtı: aynı dolar sürüklenmesi, iki sonuç."""
    sakin = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.5, gurultu=0.2)))
    calkantili = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.5, gurultu=6.0)))
    assert sakin["direction"] == "UP"
    assert calkantili["direction"] == "NEUTRAL"


# --- uyarlanabilirlik: asıl iddia ---------------------------------------------

def test_ayni_hareket_calkantili_seansta_daha_zayif_okunur():
    """Sabit eşik olmadığının kanıtı: aynı net yükseliş, farklı oynaklık."""
    sakin = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.5, gurultu=0.2)))
    calkantili = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.5, gurultu=6.0)))
    assert sakin["strength"] > calkantili["strength"]


def test_uzaklik_oynakliga_gore_olculuyor():
    # Aynı dolar mesafesi, farklı oynaklıkta farklı sayıda "sigma" eder.
    sakin = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.3, gurultu=0.2)))
    calkantili = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.3, gurultu=5.0)))
    assert sakin["session"]["volatility_pct"] < calkantili["session"]["volatility_pct"]


# --- momentumun yönü: güçleniyor mu -------------------------------------------

def test_hizlanan_hareket_STRENGTHENING():
    # Hızlanma son iki pencerede olmalı: ivme, son 12 mumu önceki 12 ile karşılaştırır.
    yavas = duz_seri(70, 4400, adim=0.02)
    hizli = [yavas[-1] + 0.5 * i for i in range(1, 13)]
    out = momentum(onceki_seans() + mumlar(yavas + hizli))
    assert out["trend"] == "STRENGTHENING"


def test_yavaslayan_hareket_WEAKENING():
    hizli = duz_seri(70, 4400, adim=0.5)
    yavas = [hizli[-1] + 0.01 * i for i in range(1, 13)]
    out = momentum(onceki_seans() + mumlar(hizli + yavas))
    assert out["trend"] == "WEAKENING"


# --- kırılım gücü -------------------------------------------------------------

def test_kirilim_etiketi_skordan_turer():
    out = momentum(onceki_seans() + mumlar(duz_seri(60, 4400, adim=0.12, gurultu=0.3)))
    kirilim = out["breakout"]
    assert kirilim is not None
    beklenen = ("STRONG" if kirilim["score"] >= 2/3
                else "MEDIUM" if kirilim["score"] >= 1/3 else "WEAK")
    assert kirilim["strength"] == beklenen


def test_seviyeye_yakin_ama_momentumsuzsa_kirilim_zayif():
    """Seviyenin dibinde olmak onu kırmakla aynı şey değil.

    Yalnız ulaşma oranına bakıldığında fiyat seviyeye 0,2 sigma yakınken oran
    88'e fırlıyor ve her şey STRONG çıkıyordu (gerçek veride ölçüldü).
    """
    seri = [4400 + (2 if i % 4 in (0, 1) else -2) for i in range(90)]
    out = momentum(onceki_seans() + mumlar(seri))
    assert out["strength"] < 10                     # momentum yok
    assert out["breakout"]["strength"] == "WEAK"    # seviye kırılmaz


def test_uzerinde_durulan_seviye_hedef_degil_ayrica_bildirilir():
    """Kullanıcı bildirdi: gösterilen seviye çoktan kırılmıştı.

    Fiyat bir seviyenin gürültü kadar yakınındaysa o seviye "kırılacak" değil
    **test ediliyor** demektir. Hedef bir sonraki gerçek seviye olmalı.
    """
    seri = [4400 + (2 if i % 4 in (0, 1) else -2) for i in range(90)]
    out = momentum(onceki_seans() + mumlar(seri))
    temas = out["touching"]
    assert temas is not None
    assert temas["distance_sigma"] < 1              # gürültü içinde
    assert out["breakout"]["level"] != temas["level"]
    assert out["breakout"]["distance"] > temas["distance"]


def test_yukselirken_hedef_direnc_dususte_destek():
    yukari = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.15, gurultu=0.2)))
    assert yukari["breakout"]["side"] == "resistance"
    asagi = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=-0.15, gurultu=0.2)))
    assert asagi["breakout"]["side"] == "support"


def test_seans_ilerledikce_kalan_mum_azalir():
    kisa = momentum(onceki_seans() + mumlar(duz_seri(60, 4400, adim=0.4, gurultu=0.3)))
    uzun = momentum(onceki_seans() + mumlar(duz_seri(110, 4400, adim=0.4, gurultu=0.3)))
    assert uzun["session"]["remaining_bars"] < kisa["session"]["remaining_bars"]


# --- hacim --------------------------------------------------------------------

def test_hacim_yoksa_hesap_hacimsiz_kurulur_ve_bildirilir():
    ham = onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.5, gurultu=0.3))
    for row in ham:
        row["v"] = 0
    out = momentum(ham)
    assert out["session"]["has_volume"] is False
    assert "volume" not in out["components"]


def test_hacim_varsa_bilesenlere_girer():
    out = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.5, gurultu=0.3)))
    assert out["session"]["has_volume"] is True
    assert "volume" in out["components"]


# --- destek / direnç ----------------------------------------------------------

def test_pivot_merdiveni_sirali():
    levels = daily_pivots(high=4450, low=4380, close=4420)
    assert levels["S3"] < levels["S2"] < levels["S1"] < levels["P"] < levels["R1"] < levels["R2"] < levels["R3"]


def test_en_yakin_seviyeler_fiyatin_iki_yaninda():
    levels = {"S1": 4380.0, "P": 4400.0, "R1": 4430.0, "R2": 4460.0}
    destek, direnc = nearest_levels(levels, 4410.0)
    assert destek == ("P", 4400.0)
    assert direnc == ("R1", 4430.0)


def test_tum_seviyeler_bir_yandaysa_diger_taraf_bos():
    levels = {"R1": 4430.0, "R2": 4460.0}
    destek, direnc = nearest_levels(levels, 4400.0)
    assert destek is None
    assert direnc == ("R1", 4430.0)


# --- göstergeler --------------------------------------------------------------

def test_rsi_yukselen_seride_yuksek_dusen_seride_dusuk():
    assert rsi(duz_seri(40, 4400, adim=1.0)) > 90
    assert rsi(duz_seri(40, 4400, adim=-1.0)) < 10


def test_rsi_yetersiz_veride_none():
    assert rsi([4400.0, 4401.0]) is None


def test_macd_histogrami_yon_degistirince_isaret_degistirir():
    yukselen = macd_histogram(duz_seri(60, 4400, adim=1.0))
    dusen = macd_histogram(duz_seri(60, 4400, adim=-1.0))
    assert yukselen > 0 > dusen


# --- çok çerçeveli seviye merdiveni -------------------------------------------
# Kusur gerçek veride ölçüldü (2026-09-01): merdiven 5 dakikalık akışın kırpılmış
# önceki seansından geliyordu, aralığı 32,14 $ çıkıyordu; günlük mumun gerçek
# aralığı 56,0 $. Seviyeler olduğu gibi yanlıştı.

def gunluk(satirlar):
    return [{"d": d, "h": h, "l": l, "c": c} for d, h, l, c in satirlar]


# 2026-08-24 → 08-31; 09-01 bilerek yok (devam eden gün merdivene girmemeli).
GUNLUK = gunluk([
    ("2026-08-24", 4670.9, 4635.1, 4640.8),
    ("2026-08-25", 4638.1, 4626.2, 4638.1),
    ("2026-08-26", 4615.3, 4598.2, 4598.2),
    ("2026-08-27", 4609.7, 4609.7, 4609.7),
    ("2026-08-28", 4625.5, 4451.8, 4478.1),
    ("2026-08-31", 4466.9, 4410.9, 4431.1),
])


def test_gunluk_seri_verilince_pivotlar_gunluk_mumdan_gelir():
    seans = onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.05, gurultu=0.3))
    kirpik = momentum(seans)
    gercek = momentum(seans, daily=GUNLUK)
    beklenen = daily_pivots(4466.9, 4410.9, 4431.1)
    assert gercek["ladder"], "merdiven boş kalmamalı"
    degerler = {round(lv["value"], 2) for lv in gercek["ladder"]}
    assert round(beklenen["S1"], 2) in degerler
    # Kırpık gün içi seans bu seviyeyi üretemiyordu: iki merdiven aynı olamaz.
    kirpik_degerler = {round(lv["value"], 2) for lv in kirpik["ladder"]}
    assert kirpik_degerler != degerler


def test_haftalik_ve_salinim_seviyeleri_de_merdivende():
    out = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.05, gurultu=0.3)),
                   daily=GUNLUK)
    etiketler = [lv["level"] for lv in out["ladder"]]
    kaynaklar = [k for lv in out["ladder"] for k in lv["sources"]]
    assert any(e.startswith("Haftalık") for e in kaynaklar), etiketler
    assert etiketler, "merdiven boş"


def test_ayni_yeri_gosteren_iki_cerceve_tek_seviyede_birlesir():
    """Gerçek örnek: haftalık S2 4314,50 ile 14 Ağustos dibi 4315,00."""
    seviyeler, kaynaklar = cluster_levels(
        [(0, "S3", 4324.30), (1, "Haftalık S2", 4314.50), (2, "14.08 dibi", 4315.00)],
        tolerance=8.0)
    assert len(seviyeler) == 2, seviyeler
    birlesik = [ad for ad, k in kaynaklar.items() if len(k) == 2]
    assert birlesik == ["Haftalık S2"]
    assert seviyeler["Haftalık S2"] == pytest.approx(4314.75)


def test_kumeleme_toleransi_oynakliktan_gelir_sabit_degil():
    ham = [(0, "A", 4400.0), (1, "B", 4404.0)]
    assert len(cluster_levels(ham, tolerance=8.0)[0]) == 1    # çalkantılı: aynı seviye
    assert len(cluster_levels(ham, tolerance=1.0)[0]) == 2    # sakin: ayrı seviyeler


def test_hafta_cumartesi_girince_tamamlanmis_sayilir():
    """Koşulsuz 'sondan bir önceki hafta' seviyeleri bir hafta bayat bırakıyordu."""
    from app.services.momentum_service import _complete_days
    gunler = _complete_days(GUNLUK, date(2026, 9, 1))          # salı
    hafta = last_complete_week(gunler, date(2026, 9, 1))
    assert [r["day"].isoformat() for r in hafta][0] == "2026-08-24"

    cumartesi = _complete_days(GUNLUK, date(2026, 8, 29))
    hafta2 = last_complete_week(cumartesi, date(2026, 8, 29))
    assert [r["day"].isoformat() for r in hafta2][-1] == "2026-08-28"


BUGUN = gunluk([("2026-09-01", 4510.5, 4374.1, 4379.6)])


def test_devam_eden_gun_merdivene_girmez():
    from app.services.momentum_service import _complete_days
    gunler = _complete_days(GUNLUK + BUGUN, date(2026, 9, 1))
    assert all(r["day"] < date(2026, 9, 1) for r in gunler)


def test_merdiven_fiyat_civarina_kirpilir():
    out = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.05, gurultu=0.3)),
                   daily=GUNLUK)
    fiyat = out["price"]
    # Uzaktaki haftalık uçlar çizimde fiyat çizgisini ezmesin diye dışarıda kalır.
    assert all(abs(lv["value"] - fiyat) < fiyat * 0.05 for lv in out["ladder"])


# --- seans sürüklenmesi -------------------------------------------------------
# Hız yalnız son bir saate bakıyordu ve gün boyu süren yavaş trendi görmüyordu
# (ölçüldü 2026-09-01: 1 saat z = -0,83, seansın tamamı -96 $ ve z = -1,65).

def test_seans_suruklenmesi_yavas_trendi_yakalar():
    """Saatlik itiş eşiğin altında kalsa da gün boyu süren trend yön vermeli."""
    # Mum başına küçük ama hiç bozulmayan bir düşüş: 1 saatlik pencerede zayıf,
    # seansın tamamında belirgin.
    seri = duz_seri(120, 4400, adim=-0.08, gurultu=0.35)
    out = momentum(onceki_seans() + mumlar(seri))
    assert abs(out["components"]["velocity"]) < 2
    assert abs(out["components"]["drift"]) > abs(out["components"]["velocity"])
    assert out["direction"] == "DOWN"


def test_surukleme_bileseni_yanitta_bildirilir():
    out = momentum(onceki_seans() + mumlar(duz_seri(80, 4400, adim=0.3, gurultu=0.2)))
    assert "drift" in out["components"]


def test_seans_cok_kisayken_surukleme_hesaba_katilmaz():
    """Birkaç mumdan hesaplanan oran anlamsız; bileşen hiç katılmamalı."""
    from app.services.momentum_service import session_drift
    assert session_drift([4400.0] * 5, 0.001) is None
    assert session_drift(duz_seri(40, 4400, adim=0.2), 0.0) is None


def test_surukleme_oynakliga_gore_olculur():
    """Aynı dolar sürüklenmesi, çalkantılı seansta daha küçük okunmalı."""
    sakin = momentum(onceki_seans() + mumlar(duz_seri(90, 4400, adim=0.2, gurultu=0.2)))
    calkantili = momentum(onceki_seans() + mumlar(duz_seri(90, 4400, adim=0.2, gurultu=6.0)))
    assert abs(sakin["components"]["drift"]) > abs(calkantili["components"]["drift"])


def test_surukleme_yonu_gostergelerle_celisirse_yon_verilmez():
    """Tek başına sürüklenme yetmez; bileşenlerin de hemfikir olması gerekir."""
    # Fiyat gün boyu yükselmiş ama son saatlerde sert dönmüş: t düşer.
    yukselis = duz_seri(70, 4400, adim=0.35)
    donus = [yukselis[-1] - 0.9 * i for i in range(1, 26)]
    out = momentum(onceki_seans() + mumlar(yukselis + donus))
    assert out["components"]["drift"] > 0          # gün hâlâ artıda
    assert out["direction"] != "UP"                # ama yukarı denmez
