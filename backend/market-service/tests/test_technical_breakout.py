"""İki yönlü kırılım gücü (`technical/breakout.py`).

Arayüzdeki `breakPotential` testleri (13) kavramsal olarak taşındı: ulaşma 1'de
doyar, skor geometrik ortalamadır, etiketler skorun üçte birlik dilimleri, fiyat
çerçevesi ötelenince sonuç değişmez. Üstüne yeni sözleşmeler: iki yan her zaman,
taban yok, karşı yönde STRONG imkânsız, sönüm monoton, pivot yedeği, seans yokken
ATR çerçevesi ve "eski davranış bir yapılandırmadır" eşitliği (√0,22 → 47).
"""
import itertools
import json
import math
from datetime import date
from pathlib import Path

import pytest

from app.services.technical.breakout import (
    FRAME_NEXT_DAILY_BAR, FRAME_SESSION_REMAINING, LABEL_MODERATE, LABEL_STRONG, LABEL_WEAK,
    NO_TARGET_ABOVE, NO_TARGET_BELOW, NOTE_NO_EXPECTED_MOVE, NOTE_NOT_A_PROBABILITY,
    NOTE_UNTESTED_LEVEL, STATUS_FLAT_MARKET, STATUS_INSUFFICIENT_DATA, STATUS_OK,
    Breakout, BreakoutParams, BreakoutSide, BreakoutTarget, analyze_breakout, label_for,
)
from app.services.technical.candles import normalize_daily
from app.services.technical.levels import (
    KIND_RESISTANCE, KIND_SUPPORT, Levels, Zone, analyze_levels, strength_label,
)
from app.services.technical.momentum_daily import MomentumDaily, label_direction, momentum_daily
from app.services.technical.pivots import build_ladder

FIXTURES = Path(__file__).parent / "fixtures"
HAFTALIK_KLASIK = [("R3", 4824.467), ("R2", 4681.133), ("R1", 4578.867), ("P", 4435.533),
                   ("S1", 4333.267), ("S2", 4189.933), ("S3", 4087.667)]
REF, ATR = 4476.6, 86.66


# --- kurucular -----------------------------------------------------------------

def bolge(zid: str, mid: float, strength: int, kind: str, ref: float, half: float = 5.0) -> Zone:
    return Zone(id=zid, mid=mid, low=mid - half, high=mid + half, kind=kind, strength=strength,
                label=strength_label(strength), name=zid.upper(), sources=(), source_types=(),
                touches=0, rejections=0, breaks=0, pending=0, last_touch=None, last_break=None,
                confirmed=True, components={}, distance_pct=mid / ref - 1, distance_usd=mid - ref,
                distance_atr=(mid - ref) / ATR, distance_sigma=None, testing=False)


def seviyeler(ref: float = REF, support: tuple[float, int] | None = None,
              resistance: tuple[float, int] | None = None) -> Levels:
    """Elle kurulan `Levels`: yan başına en çok bir bölge (mid, güç)."""
    zones, ids = [], {"support": None, "resistance": None}
    if support is not None:
        zones.append(bolge("s", support[0], support[1], KIND_SUPPORT, ref)); ids["support"] = "s"
    if resistance is not None:
        zones.append(bolge("r", resistance[0], resistance[1], KIND_RESISTANCE, ref)); ids["resistance"] = "r"
    return Levels(status=STATUS_OK, as_of=None, atr=ATR, sigma=None, cluster_tolerance=None,
                  margin_usd=None, scan_range=None, min_strength=30, zones=tuple(zones),
                  nearest_support=ids["support"], next_support=None,
                  nearest_resistance=ids["resistance"], next_resistance=None, testing=(),
                  weakest_ignored=None,
                  side_status={k: "OK" if v else f"NO_VALID_{k.upper()}" for k, v in ids.items()})


def seans(direction: str = "NEUTRAL", strength: float = 50, expected_move: float = 30.0,
          sigma_pct: float | None = 0.15) -> dict:
    inner = {"expected_move": expected_move, "remaining_bars": 24}
    if sigma_pct is not None:
        inner["volatility_pct"] = sigma_pct
    return {"direction": direction, "strength": strength, "trend": "STABLE", "session": inner}


def gunluk(score: int | None, status: str = "OK") -> MomentumDaily:
    ok = status == "OK" and score is not None
    return MomentumDaily(status=status, date=None, score=score if ok else None,
                         direction=label_direction(score) if ok else None, strength=None,
                         trend=None, agreement=None, z=None, delta=None, acceleration=None,
                         note=None, components={}, weights={}, z_scale=2.0, history=(),
                         sigma=None, atr=ATR)


def hesapla(*, ref=REF, atr=ATR, levels=None, ladder=None, session=None, daily=None,
            params=BreakoutParams()) -> Breakout:
    return analyze_breakout(reference=ref, atr=atr, levels=levels, pivot_ladder=ladder,
                            session=session, momentum_daily=daily, params=params)


IKI_YAN = seviyeler(support=(REF - 40.0, 0), resistance=(REF + 40.0, 0))   # güç 0 → sönüm 1


# --- parametreler ----------------------------------------------------------------

def test_parametreler_dogrulanir():
    assert BreakoutParams().weight_session + BreakoutParams().weight_daily == pytest.approx(1.0)
    with pytest.raises(ValueError):
        BreakoutParams(weight_session=0.7)                    # 0,7 + 0,4 ≠ 1
    with pytest.raises(ValueError):
        BreakoutParams(opposed_factor=1.5)
    with pytest.raises(ValueError):
        BreakoutParams(level_damping=-0.1)
    with pytest.raises(ValueError):
        BreakoutParams(daily_span=0.0)
    with pytest.raises(ValueError):
        BreakoutParams(daily_horizon_bars=0)
    with pytest.raises(ValueError):
        BreakoutParams(moderate=0.7, strong=0.6)
    with pytest.raises(ValueError):
        BreakoutParams(strong=float("nan"))
    BreakoutParams(weight_session=1.0, weight_daily=0.0, level_damping=0.0)   # eski davranış


# --- iki yan, geometrik ortalama, doyma ---------------------------------------------

def test_iki_yan_her_zaman_hesaplanir_yon_hedef_secmez():
    out = hesapla(levels=IKI_YAN, session=seans("UP", 80), daily=gunluk(50))
    assert out.status == STATUS_OK and out.note == NOTE_NOT_A_PROBABILITY
    assert out.up.status == STATUS_OK and out.down.status == STATUS_OK
    assert out.up.target == BreakoutTarget("r", "R", REF + 40.0, 0, False)
    assert out.down.target == BreakoutTarget("s", "S", REF - 40.0, 0, False)
    # Seans yukarı: yukarı yan tam seans itişi, aşağı yan çeyreği.
    assert out.up.components["direction_factor"] == 1.0
    assert out.down.components["direction_factor"] == 0.25
    assert out.up.strength > out.down.strength > 0


def test_ulasma_1de_doyurulur_daha_yakin_olmak_sisirmez():
    """FE: 4400,4 ile 4400,04 aynı skoru verir; ulaşılabilir + güçlü = STRONG."""
    yakin = hesapla(levels=seviyeler(resistance=(REF + 20.0, 0)), session=seans("UP", 82), daily=gunluk(75))
    cok_yakin = hesapla(levels=seviyeler(resistance=(REF + 0.5, 0)), session=seans("UP", 82), daily=gunluk(75))
    assert yakin.up.reach == 1.0 and cok_yakin.up.reach == 1.0
    assert cok_yakin.up.components["score"] == pytest.approx(yakin.up.components["score"], abs=1e-12)
    assert yakin.up.label == LABEL_STRONG
    # Uzak seviyede güçlü momentum bile yetmez.
    uzak = hesapla(levels=seviyeler(resistance=(REF + 300.0, 0)), session=seans("UP", 90), daily=gunluk(75))
    assert uzak.up.reach == pytest.approx(0.1) and uzak.up.label == LABEL_WEAK
    assert uzak.up.strength < yakin.up.strength


def test_geometrik_ortalama_ulasmak_ve_itilmek_ikisi_de_gerekir():
    """raw = √(reach · push): reach 0,25 & push 1 == reach 1 & push 0,25."""
    guclu = seans("NEUTRAL", 100, expected_move=10.0)
    p = BreakoutParams(weight_session=1.0, weight_daily=0.0, level_damping=0.0)
    a = hesapla(levels=seviyeler(resistance=(REF + 40.0, 0)), session=guclu, params=p)   # reach 0,25, push 1
    b = hesapla(levels=seviyeler(resistance=(REF + 10.0, 0)),
                session=seans("NEUTRAL", 25, expected_move=10.0), params=p)             # reach 1, push 0,25
    assert (a.up.reach, a.up.push) == (0.25, 1.0) and (b.up.reach, b.up.push) == (1.0, 0.25)
    assert a.up.components["raw"] == pytest.approx(0.5) == pytest.approx(b.up.components["raw"])
    assert a.up.strength == b.up.strength == 50
    # Seviyeye ulaşılsa da momentum yoksa zayıf (FE: reach > 1, güç 3 → WEAK).
    c = hesapla(levels=seviyeler(resistance=(REF + 2.0, 0)), session=seans("UP", 3), daily=gunluk(50))
    assert c.up.reach == 1.0 and c.up.label == LABEL_WEAK
    for side in (a.up, b.up, c.up):
        assert side.components["raw"] == pytest.approx(math.sqrt(side.reach * side.push))


def test_etiket_esikleri_skorun_kendisinden():
    p = BreakoutParams(weight_session=1.0, weight_daily=0.0, level_damping=0.0)

    def etiket(guc):
        out = hesapla(levels=seviyeler(resistance=(REF + 5.0, 0)), session=seans("NEUTRAL", guc), params=p)
        return out.up.strength, out.up.label
    # skor = √(güç/100): 11 → 0,332 · 12 → 0,346 · 44 → 0,663 · 45 → 0,671
    assert etiket(11) == (33, LABEL_WEAK)
    assert etiket(12) == (35, LABEL_MODERATE)
    assert etiket(44) == (66, LABEL_MODERATE)
    assert etiket(45) == (67, LABEL_STRONG)
    assert label_for(1 / 3) == LABEL_MODERATE and label_for(2 / 3) == LABEL_STRONG
    ozel = BreakoutParams(moderate=0.5, strong=0.9)
    assert label_for(0.49, ozel) == LABEL_WEAK and label_for(0.89, ozel) == LABEL_MODERATE


# --- taban yok, sıfır hareket, karşı yön ----------------------------------------------

def test_beklenen_hareket_sifirsa_guc_sifir_ama_durum_ok():
    out = hesapla(levels=IKI_YAN, session=seans("UP", 90, expected_move=0.0), daily=gunluk(80))
    assert out.expected_move == 0.0 and out.expected_move_pct == 0.0
    for side in (out.up, out.down):
        assert side.status == STATUS_OK and side.reach == 0.0
        assert side.strength == 0 and side.label == LABEL_WEAK and side.note == NOTE_NO_EXPECTED_MOVE
        assert side.target is not None            # hedef var, hareket yok


def test_taban_yok_momentum_sifirsa_sifir():
    out = hesapla(levels=IKI_YAN, session=seans("NEUTRAL", 0), daily=gunluk(50))
    for side in (out.up, out.down):
        assert side.push == 0.0 and side.strength == 0 and side.label == LABEL_WEAK
    # Girdi hiç yoksa da uydurulmaz: seans yok, günlük yok → 0.
    bos = hesapla(levels=IKI_YAN)
    assert bos.up.strength == 0 and bos.down.strength == 0


def test_karsi_yonde_strong_imkansiz():
    """Seans o yana karşı VE günlük o yana karşı → push ≤ 0,25·0,6 = 0,15 → ≤ 39."""
    en_yuksek = 0
    for guc, skor, uzaklik in itertools.product((0, 25, 50, 75, 100), (0, 10, 30, 50), (1.0, 20.0, 60.0)):
        lv = seviyeler(support=(REF - uzaklik, 0), resistance=(REF + uzaklik, 0))
        yukari = hesapla(levels=lv, session=seans("DOWN", guc, expected_move=60.0), daily=gunluk(skor))
        asagi = hesapla(levels=lv, session=seans("UP", guc, expected_move=60.0), daily=gunluk(100 - skor))
        for side in (yukari.up, asagi.down):
            assert side.push <= 0.15 + 1e-12 and side.label != LABEL_STRONG
            en_yuksek = max(en_yuksek, side.strength)
    assert en_yuksek == 39                      # √0,15 = 0,387: sınır fiilen dokunuluyor


def test_seans_yonu_ceza_faktoru_ve_notr():
    asagi = hesapla(levels=IKI_YAN, session=seans("DOWN", 100), daily=gunluk(50))
    assert asagi.up.components["session"] == pytest.approx(0.25)
    assert asagi.down.components["session"] == pytest.approx(1.0)
    notr = hesapla(levels=IKI_YAN, session=seans("NEUTRAL", 100), daily=gunluk(50))
    assert notr.up.components["session"] == notr.down.components["session"] == pytest.approx(1.0)
    assert notr.up.components["direction_factor"] == 1.0
    ozel = hesapla(levels=IKI_YAN, session=seans("DOWN", 100), params=BreakoutParams(opposed_factor=0.0))
    assert ozel.up.components["session"] == 0.0 and ozel.up.strength == 0


def test_gunluk_itis_yone_bagli_ve_doyar():
    ust = hesapla(levels=IKI_YAN, daily=gunluk(75))
    assert ust.up.components["daily"] == pytest.approx(1.0) and ust.down.components["daily"] == 0.0
    alt = hesapla(levels=IKI_YAN, daily=gunluk(30))
    assert alt.up.components["daily"] == 0.0 and alt.down.components["daily"] == pytest.approx(0.8)
    assert hesapla(levels=IKI_YAN, daily=gunluk(100)).up.components["daily"] == 1.0   # kırpma
    # Günlük OK değilse 0 sayılır, bağlam alanları boş.
    yok = hesapla(levels=IKI_YAN, session=seans("UP", 50), daily=gunluk(None, status="FLAT_MARKET"))
    assert yok.up.components["daily"] == 0.0 and yok.daily_score is None and yok.daily_direction is None
    assert yok.weights == {"session": 0.6, "daily": 0.4}          # seans varken dağılım değişmez


# --- sönüm ----------------------------------------------------------------------------

def test_sonum_monoton_guclu_bolge_daha_zor_kirilir():
    onceki, sonumler = None, []
    for guc in (0, 30, 60, 100):
        out = hesapla(levels=seviyeler(resistance=(REF + 20.0, guc)), session=seans("UP", 90), daily=gunluk(75))
        sonumler.append(out.up.damping)
        assert onceki is None or out.up.strength < onceki
        onceki = out.up.strength
    assert sonumler == pytest.approx([1.0, 0.85, 0.7, 0.5])
    kapali = hesapla(levels=seviyeler(resistance=(REF + 20.0, 100)), session=seans("UP", 90),
                     daily=gunluk(75), params=BreakoutParams(level_damping=0.0))
    assert kapali.up.damping == 1.0


# --- çerçeveler ve hedef çözümü -----------------------------------------------------------

def test_seans_yokken_atr_cercevesi_ve_agirliklar():
    out = hesapla(levels=IKI_YAN, daily=gunluk(75))
    assert out.expected_move == pytest.approx(ATR) and out.expected_move_frame == FRAME_NEXT_DAILY_BAR
    assert out.weights == {"session": 0.0, "daily": 1.0}
    assert out.session_direction is None and out.session_strength is None and out.headline is None
    assert out.up.components["session"] == 0.0 and out.up.push == pytest.approx(1.0)
    assert out.up.distance_sigma is None                     # seans sigması yok
    dort = hesapla(levels=IKI_YAN, daily=gunluk(75), params=BreakoutParams(daily_horizon_bars=4))
    assert dort.expected_move == pytest.approx(2 * ATR)
    var = hesapla(levels=IKI_YAN, session=seans("UP", 50, expected_move=53.25))
    assert var.expected_move == 53.25 and var.expected_move_frame == FRAME_SESSION_REMAINING
    assert var.expected_move_pct == pytest.approx(53.25 / REF)


def test_bozuk_seans_yok_sayilir():
    for bozuk in ({"direction": "UP"}, {"direction": "SIDEWAYS", "strength": 50, "session": {"expected_move": 10}},
                  {"direction": "UP", "strength": float("nan"), "session": {"expected_move": 10}},
                  {"direction": "UP", "strength": 50, "session": {"expected_move": -1}},
                  {"direction": "UP", "strength": 50, "session": {}}, "UP", 42):
        out = hesapla(levels=IKI_YAN, session=bozuk, daily=gunluk(75))
        assert out.expected_move_frame == FRAME_NEXT_DAILY_BAR and out.weights["session"] == 0.0


def test_pivot_yedegi_levels_o_yanda_bossa():
    lv = seviyeler(support=(REF - 40.0, 45))                     # direnç yok
    ladder = build_ladder(HAFTALIK_KLASIK, REF)                  # nearest_up R1, nearest_down P
    out = hesapla(levels=lv, ladder=ladder, session=seans("UP", 80), daily=gunluk(70))
    assert out.up.status == STATUS_OK
    assert out.up.target == BreakoutTarget(None, "R1", 4578.867, None, True)
    assert out.up.damping == 1.0 and out.up.note == NOTE_UNTESTED_LEVEL
    assert out.down.target.fallback is False and out.down.target.zone_id == "s"
    assert out.down.damping == pytest.approx(1 - 0.5 * 0.45) and out.down.note is None
    # Levels hiç yoksa iki yan da merdivenden.
    ikisi = hesapla(ladder=ladder, session=seans("UP", 80))
    assert (ikisi.up.target.name, ikisi.down.target.name) == ("R1", "P")
    assert ikisi.up.target.fallback and ikisi.down.target.fallback


def test_yanlis_taraftaki_aday_atlanir():
    """Tutarsız `Levels` (direnç kimliği referansın altında bir bölgeyi gösteriyor):
    bölge atlanır, merdiven yedeği devreye girer."""
    lv = seviyeler(resistance=(REF - 10.0, 50))
    out = hesapla(levels=lv, ladder=build_ladder(HAFTALIK_KLASIK, REF), session=seans("UP", 80))
    assert out.up.target.fallback and out.up.target.name == "R1"
    assert hesapla(levels=lv, session=seans("UP", 80)).up.status == NO_TARGET_ABOVE


def test_hedef_yoksa_durum_bildirir():
    out = hesapla(session=seans("UP", 80), daily=gunluk(75))
    assert out.status == STATUS_OK
    assert out.up.status == NO_TARGET_ABOVE and out.down.status == NO_TARGET_BELOW
    assert out.up.target is None and out.up.strength is None and out.up.label is None
    assert out.up.components == {}
    # Fiyat merdivenin üstünde: yukarıda hedef yok, aşağıda var.
    ustte = hesapla(ref=5000.0, ladder=build_ladder(HAFTALIK_KLASIK, 5000.0), session=seans("UP", 80))
    assert ustte.up.status == NO_TARGET_ABOVE and ustte.down.target.name == "R3"


def test_baslik_seans_yonunden_notr_bos():
    assert hesapla(levels=IKI_YAN, session=seans("NEUTRAL", 60)).headline is None
    assert hesapla(levels=IKI_YAN, session=seans("UP", 60)).headline == "up"
    assert hesapla(levels=IKI_YAN, session=seans("DOWN", 60)).headline == "down"
    assert hesapla(levels=IKI_YAN).headline is None
    # Başlık hedefi seçmez: yön aşağıyken yukarı yan yine hesaplı.
    assert hesapla(levels=IKI_YAN, session=seans("DOWN", 60)).up.status == STATUS_OK


# --- uzaklıklar, değişmezlik, belirlenimcilik ------------------------------------------

def test_uzakliklar():
    out = hesapla(levels=IKI_YAN, session=seans("NEUTRAL", 50, sigma_pct=0.2))
    assert out.up.distance_usd == pytest.approx(40.0) and out.down.distance_usd == pytest.approx(40.0)
    assert out.up.distance_pct == pytest.approx(40.0 / REF)
    assert out.down.distance_pct == pytest.approx(-40.0 / REF)          # işaretli
    assert out.up.distance_atr == pytest.approx(40.0 / ATR)
    assert out.up.distance_sigma == pytest.approx(40.0 / (REF * 0.002))
    assert hesapla(levels=IKI_YAN, session=seans(sigma_pct=None)).up.distance_sigma is None


def test_fiyat_cercevesi_otelenince_sonuc_degismez():
    """Spot ↔ vadeli: referans, hedefler, ATR ve beklenen hareket ×1,0095."""
    k = 1.0095
    lv = seviyeler(support=(REF - 55.0, 40), resistance=(REF + 35.0, 25))
    lv_k = seviyeler(ref=REF * k, support=((REF - 55.0) * k, 40), resistance=((REF + 35.0) * k, 25))
    spot = hesapla(levels=lv, session=seans("UP", 61, expected_move=53.25), daily=gunluk(59))
    vadeli = hesapla(ref=REF * k, atr=ATR * k, levels=lv_k,
                     session=seans("UP", 61, expected_move=53.25 * k), daily=gunluk(59))
    for a, b in ((spot.up, vadeli.up), (spot.down, vadeli.down)):
        assert a.strength == b.strength and a.label == b.label
        assert a.components["score"] == pytest.approx(b.components["score"], abs=1e-10)
        assert a.distance_pct == pytest.approx(b.distance_pct, abs=1e-10)
        assert a.distance_atr == pytest.approx(b.distance_atr, abs=1e-10)
        assert a.distance_sigma == pytest.approx(b.distance_sigma, abs=1e-8)
    assert spot.expected_move_pct == pytest.approx(vadeli.expected_move_pct, abs=1e-10)


def test_deterministik():
    lv = seviyeler(support=(REF - 55.0, 40), resistance=(REF + 35.0, 25))
    a = hesapla(levels=lv, session=seans("UP", 61), daily=gunluk(59))
    b = hesapla(levels=lv, session=seans("UP", 61), daily=gunluk(59))
    assert a == b and a.up == b.up and a.down == b.down


# --- eski davranış, boş durumlar --------------------------------------------------------

def test_eski_davranis_bir_yapilandirmadir():
    """weight_session=1, weight_daily=0, level_damping=0 + canlı fixture seansı
    (NEUTRAL, 22, 53,25 $) + ulaşılabilir hedef → √0,22 = 0,469 → 47.
    Eski servis (`breakout.score` 0,469) ve arayüz aynı sayıyı veriyordu."""
    canli = json.loads((FIXTURES / "momentum_live_20260906.json").read_text(encoding="utf-8"))
    assert (canli["direction"], canli["strength"], canli["session"]["expected_move"]) == ("NEUTRAL", 22, 53.25)
    eski = BreakoutParams(weight_session=1.0, weight_daily=0.0, level_damping=0.0)
    ladder = build_ladder([("R1", REF + 40.0), ("S1", 4443.4)], REF)     # ikisi de 53,25 içinde
    out = hesapla(ladder=ladder, session=canli, daily=gunluk(59), params=eski)
    for side in (out.up, out.down):
        assert side.reach == 1.0 and side.damping == 1.0
        assert side.components["score"] == pytest.approx(math.sqrt(0.22), abs=1e-12)
        assert round(side.components["score"], 3) == canli["breakout"]["score"] == 0.469
        assert side.strength == 47 and side.label == LABEL_MODERATE
    # Bölge gücü olsa bile sönüm kapalı: sayı aynı.
    lv = seviyeler(support=(4443.4, 80), resistance=(REF + 40.0, 80))
    assert hesapla(levels=lv, session=canli, params=eski).up.strength == 47


def test_flat_market_ve_referans_yok():
    for atr in (0.0, None, -1.0, float("nan")):
        out = hesapla(atr=atr, levels=IKI_YAN, session=seans("UP", 80), daily=gunluk(75))
        assert out.status == STATUS_FLAT_MARKET and out.note == NOTE_NOT_A_PROBABILITY
        assert out.up.status == STATUS_FLAT_MARKET and out.up.strength is None
        assert out.expected_move is None and out.weights == {} and out.headline is None
    for ref in (None, 0.0, -5.0, float("inf")):
        out = hesapla(ref=ref, levels=IKI_YAN, session=seans("UP", 80))
        assert out.status == STATUS_INSUFFICIENT_DATA and out.down.status == STATUS_INSUFFICIENT_DATA
    assert isinstance(hesapla(levels=IKI_YAN).up, BreakoutSide)


# --- 2026-09-06 fixture -----------------------------------------------------------------

def test_fixture_2026_09_06_iki_yan():
    """Günlük fixture + haftalık klasik pivotlar + canlı seans + günlük momentum.
    Sayılar bu tarihte ölçülüp sabitlendi; formül değişirse burası kırılır."""
    veri = json.loads((FIXTURES / "xau_daily_20260906.json").read_text(encoding="utf-8"))
    bars, _ = normalize_daily(veri["points"])
    canli = json.loads((FIXTURES / "momentum_live_20260906.json").read_text(encoding="utf-8"))
    lv = analyze_levels(bars, REF, pivot_levels=HAFTALIK_KLASIK)
    md = momentum_daily(bars)
    ladder = build_ladder(HAFTALIK_KLASIK, REF, margin_usd=lv.margin_usd, atr=lv.atr)
    assert (lv.nearest_support, lv.nearest_resistance) == ("z-4351", "z-4533")
    assert (md.score, md.direction, md.date) == (59, "NEUTRAL", date(2026, 9, 4))

    out = analyze_breakout(reference=REF, atr=lv.atr, levels=lv, pivot_ladder=ladder,
                           session=canli, momentum_daily=md)
    assert out.status == STATUS_OK and out.headline is None
    assert (out.session_direction, out.session_strength, out.daily_score) == ("NEUTRAL", 22, 59)
    assert out.expected_move == 53.25 and out.expected_move_frame == FRAME_SESSION_REMAINING
    assert out.weights == {"session": 0.6, "daily": 0.4}

    up, down = out.up, out.down
    assert up.target.zone_id == "z-4533" and up.target.zone_strength == 31 and not up.target.fallback
    assert down.target.zone_id == "z-4351" and down.target.zone_strength == 38
    assert up.distance_usd == pytest.approx(55.956, abs=1e-3) and up.reach == pytest.approx(0.9516, abs=1e-4)
    assert down.distance_usd == pytest.approx(125.718, abs=1e-3) and down.reach == pytest.approx(0.4236, abs=1e-4)
    # up: push 0,6·0,22 + 0,4·0,36 = 0,276; √(0,9516·0,276)·0,845 = 0,433 → 43
    assert up.push == pytest.approx(0.276) and up.damping == pytest.approx(0.845)
    assert (up.strength, up.label, up.note) == (43, LABEL_MODERATE, None)
    # down: günlük 59 aşağıyı itmez; push 0,132; √(0,4236·0,132)·0,81 = 0,192 → 19
    assert down.push == pytest.approx(0.132) and down.damping == pytest.approx(0.81)
    assert (down.strength, down.label, down.note) == (19, LABEL_WEAK, None)
    assert up.distance_sigma == pytest.approx(9.184, abs=1e-3)
    print(f"\nfixture breakout: up={up.strength} {up.label} ({up.target.name} @ {up.target.value:.1f}) "
          f"down={down.strength} {down.label} ({down.target.name} @ {down.target.value:.1f})")
