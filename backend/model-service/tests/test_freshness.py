from app.services.freshness import FROZEN_AFTER_ROWS, frozen_features


def satirlar(n, **kolonlar):
    """n satır üretir; her kolon ya sabit ya da satır başına değişen değer alır."""
    return [{k: (v if not callable(v) else v(i)) for k, v in kolonlar.items()} for i in range(n)]


def test_sabit_girdi_donmus_sayilir():
    rows = satirlar(40, sabit=2.15, degisen=lambda i: i * 0.1)
    assert frozen_features(rows, ["sabit", "degisen"]) == ("sabit",)


def test_esik_kadar_sabitlik_yetmez_bir_fazlasi_gerekir():
    # Tam eşik kadar sabit ama öncesinde farklı: henüz donmuş sayılmaz.
    n = FROZEN_AFTER_ROWS + 1
    rows = [{"x": 1.0}] + [{"x": 2.0}] * n
    assert frozen_features(rows, ["x"]) == ("x",)
    rows2 = [{"x": 1.0}] * 5 + [{"x": 2.0}] * FROZEN_AFTER_ROWS
    assert frozen_features(rows2, ["x"]) == ()


def test_yeterli_satir_yoksa_hicbir_sey_donmus_degil():
    # Az veriyle "değişmiyor" demek yanıltıcı olurdu.
    rows = satirlar(FROZEN_AFTER_ROWS, sabit=2.15)
    assert frozen_features(rows, ["sabit"]) == ()


def test_eksik_deger_karar_disi_birakilir():
    rows = satirlar(40, x=2.0)
    rows[-3]["x"] = ""
    assert frozen_features(rows, ["x"]) == ()


def test_bilinmeyen_kolon_yok_sayilir():
    rows = satirlar(40, x=1.0)
    assert frozen_features(rows, ["yok"]) == ()


def test_esik_cagri_basina_ayarlanabilir():
    rows = satirlar(10, x=1.0)
    assert frozen_features(rows, ["x"], min_rows=5) == ("x",)
    assert frozen_features(rows, ["x"], min_rows=20) == ()


def test_gecersiz_esik_guvenli():
    rows = satirlar(40, x=1.0)
    assert frozen_features(rows, ["x"], min_rows=0) == ()


def test_birden_cok_donmus_girdi_sirayi_korur():
    rows = satirlar(40, a=1.0, b=lambda i: i, c=3.0)
    assert frozen_features(rows, ["a", "b", "c"]) == ("a", "c")
