"""Sekizinci bölüm 'sesler' (Piyasa ne diyor): yalnız brifte piyasa_sesleri doluysa; sıra sabit; eksik/fazla düzeltme ister."""
import pytest

from app.services import commentary_pipeline as cp

SEVEN = [{"id": i, "baslik": cp.BOLUM_BASLIK[i], "metin": "x"} for i in cp.BOLUM_IDS]


def test_normalizer_accepts_seven_and_eight_and_fixes_order():
    assert [b["id"] for b in cp._normalize_anchor_output({"baslik": "b", "manset": "m", "ozet": "o", "bolumler": SEVEN})["bolumler"]] == cp.BOLUM_IDS
    eight = SEVEN + [{"id": "sesler", "baslik": "Piyasa ne diyor", "metin": "y"}]          # sona yazılmış; araya taşınmalı
    out = cp._normalize_anchor_output({"baslik": "b", "manset": "m", "ozet": "o", "bolumler": eight})
    assert [b["id"] for b in out["bolumler"]] == ["giris", "neden", "masa", "seviyeler", "buyuk_resim", "sesler", "takvim", "kapanis"]
    with pytest.raises(ValueError):
        cp._normalize_anchor_output({"baslik": "b", "manset": "m", "ozet": "o", "bolumler": SEVEN[:-1]})       # kapanis eksik
    with pytest.raises(ValueError):
        cp._normalize_anchor_output({"baslik": "b", "manset": "m", "ozet": "o", "bolumler": SEVEN + [{"id": "ek", "baslik": "?", "metin": "z"}]})


def test_section_problems_follow_the_brief():
    eight = SEVEN + [{"id": "sesler", "baslik": "Piyasa ne diyor", "metin": "y"}]
    assert cp.section_problems(SEVEN, wants_sesler=False) == []
    assert cp.section_problems(eight, wants_sesler=True) == []
    assert "eksik" in cp.section_problems(SEVEN, wants_sesler=True)[0]
    assert "kaldır" in cp.section_problems(eight, wants_sesler=False)[0]
    assert cp.BOLUM_MIN["sesler"] == 30 and cp.budget_problems([{"id": "sesler", "metin": "çok kısa"}])
