"""Fraktal salınım noktaları (`technical/swings.py`).

Elle kurulmuş kısa serilerde tepe/dip indeksleri bilinir; testler kanat
asimetrisini (sol katı, sağ eşitliğe açık), kuyruktaki DEVELOPING durumunu ve
ileri bakış olmadığını sabitler.
"""
from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.services.technical.swings import (
    KIND_HIGH, KIND_LOW, STATUS_CONFIRMED, STATUS_DEVELOPING, Swing, swing_points,
)


@dataclass(frozen=True)
class Mum:
    date: date
    high: float
    low: float
    close: float


def mumlar(kapanislar, r=1.0, start=date(2025, 1, 1)):
    """Kapanış ± r aralıklı mumlar; tepe = kapanış + r, dip = kapanış − r."""
    return [Mum(start + timedelta(days=i), c + r, c - r, c) for i, c in enumerate(kapanislar)]


# Tepe 5 (high 16), dip 9 (low 10), tepe 12 (high 15), son mum 15 DEVELOPING dip.
BILINEN = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 12, 13, 14, 13, 12, 11]


def ozet(swings):
    return [(s.kind, s.index, s.status) for s in swings]


def test_bilinen_tepe_ve_dipler():
    swings = swing_points(mumlar(BILINEN), 3)
    assert ozet(swings) == [
        (KIND_HIGH, 5, STATUS_CONFIRMED), (KIND_LOW, 9, STATUS_CONFIRMED),
        (KIND_HIGH, 12, STATUS_CONFIRMED), (KIND_LOW, 15, STATUS_DEVELOPING),
    ]
    assert swings[0].price == 16.0 and swings[1].price == 10.0
    assert swings[0].date == date(2025, 1, 6)
    assert isinstance(swings[0], Swing)


def test_platoda_ilk_mum_kazanir():
    """Eşit iki tepe tek noktadır: sol kanat katı, sağ kanat eşitliğe açık."""
    swings = swing_points(mumlar([10, 11, 12, 13, 15, 15, 13, 12, 11, 10]), 3)
    tepeler = [s for s in swings if s.kind == KIND_HIGH]
    assert [(s.index, s.status) for s in tepeler] == [(4, STATUS_CONFIRMED)]


def test_kuyruktaki_developing_daha_yuksek_mum_gelince_silinir():
    yukselen = [10, 11, 12, 13, 14, 15, 16]
    assert ozet(swing_points(mumlar(yukselen), 3)) == [(KIND_HIGH, 6, STATUS_DEVELOPING)]
    # Daha yüksek mum: 6 artık tepe değil, yeni son mum DEVELOPING.
    assert ozet(swing_points(mumlar(yukselen + [17]), 3)) == [(KIND_HIGH, 7, STATUS_DEVELOPING)]
    # Daha düşük mumlar: 6 sağ kanadı dolana kadar DEVELOPING, sonra CONFIRMED.
    def tepeler(kapanislar):
        return [t for t in ozet(swing_points(mumlar(kapanislar), 3)) if t[0] == KIND_HIGH]

    assert tepeler(yukselen + [15]) == [(KIND_HIGH, 6, STATUS_DEVELOPING)]
    assert tepeler(yukselen + [15, 14]) == [(KIND_HIGH, 6, STATUS_DEVELOPING)]
    assert tepeler(yukselen + [15, 14, 13]) == [(KIND_HIGH, 6, STATUS_CONFIRMED)]


def test_developing_eldeki_sag_mumlarin_en_buyugu_olmali():
    assert ozet(swing_points(mumlar([10, 11, 12, 13, 14, 12]), 3)) == [(KIND_HIGH, 4, STATUS_DEVELOPING)]
    # Sağdaki tek mum daha yüksekse 4 tepe değildir; 5 DEVELOPING olur.
    assert ozet(swing_points(mumlar([10, 11, 12, 13, 14, 16]), 3)) == [(KIND_HIGH, 5, STATUS_DEVELOPING)]


def test_lookback_yalniz_aday_mumlari_sinirlar():
    bars = mumlar(BILINEN)
    assert [s.index for s in swing_points(bars, 3, lookback=6)] == [12, 15]
    # Pencerenin ilk mumu da salınım olabilir: sol kanat pencere dışını görür.
    assert [s.index for s in swing_points(bars, 3, lookback=4)] == [12, 15]
    # İndeksler mutlak: pencere kaydığında değişmez.
    assert swing_points(bars, 3, lookback=4)[0] == swing_points(bars, 3)[2]


def test_ileri_bakis_yok_onayli_noktalar_kalici():
    bars = mumlar(BILINEN)
    tam = {(s.kind, s.index): s for s in swing_points(bars, 3) if s.status == STATUS_CONFIRMED}
    for t in range(4, len(bars) + 1):
        for swing in swing_points(bars[:t], 3):
            assert swing.index < t
            if swing.status == STATUS_CONFIRMED:
                assert tam[(swing.kind, swing.index)] == swing


def test_kanat_dogrulamasi_ve_kisa_seri():
    with pytest.raises(ValueError):
        swing_points(mumlar(BILINEN), 0)
    with pytest.raises(ValueError):
        swing_points(mumlar(BILINEN), True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        swing_points(mumlar(BILINEN), 3, lookback=0)
    assert swing_points(mumlar([10, 11, 12]), 3) == []
    assert swing_points([], 3) == []


def test_dev_aralikli_mum_hem_tepe_hem_dip():
    bars = mumlar([10, 10, 10, 10])
    bars.append(Mum(date(2025, 1, 5), 20.0, 0.0, 10.0))
    assert ozet(swing_points(bars, 3)) == [
        (KIND_HIGH, 4, STATUS_DEVELOPING), (KIND_LOW, 4, STATUS_DEVELOPING)]


def test_belirlenimci_ve_indeks_sirali():
    bars = mumlar([((i * 7919) % 97) / 10.0 for i in range(400)])
    once, sonra = swing_points(bars, 3, lookback=250), swing_points(bars, 3, lookback=250)
    assert once == sonra
    assert [s.index for s in once] == sorted(s.index for s in once)
    assert all(s.index >= 150 for s in once)
    assert len(once) > 20
