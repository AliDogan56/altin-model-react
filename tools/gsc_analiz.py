# -*- coding: utf-8 -*-
"""Search Console sorgu raporunu anahtar kelime planıyla karşılaştırır.

Kullanım:
    python3 gsc_analiz.py <dosya>
    python3 gsc_analiz.py --self-test

<dosya>: Search Console'dan indirilen ZIP ya da doğrudan Queries/Sorgular CSV'si.
Türkçe ve İngilizce sütun başlıklarının ikisini de tanır.

Çıktı üç soruya cevap verir:
  1. Hangi küme gerçekten trafik/gösterim alıyor — plandaki sıralama doğru mu?
  2. Hangi sorgularda gösterim var ama tıklama yok (fırsat)?
  3. Hangi sorgular hiçbir makaleyle eşleşmiyor (boşluk)?
"""
import csv, io, json, sys, zipfile
from pathlib import Path

# Plandaki altı küme; eşleştirme sorgu metnindeki kelimelere bakar.
KUMELER = {
    "1 · Gram ve lira köprüsü": [
        "gram altın tahmin", "gram altın ne kadar olacak", "gram altın 2026",
        "gram altın yüksel", "gram altın düş", "gram altın neden",
        "ons gram", "dolar altın", "kur altın",
    ],
    "2 · Bilezik ve işçilik": [
        "bilezik", "işçilik", "iscilik", "22 ayar", "milyem", "bozdur",
        "kuyumcu", "makas", "çeyrek altın kaç", "ziynet",
    ],
    "3 · Vergi ve mevzuat": [
        "vergi", "kambiyo", "kdv", "e-fatura", "beyan", "stopaj",
    ],
    "4 · Yatırım aracı karşılaştırma": [
        "altın hesab", "altın fonu", "etf", "darphane", "sertifika",
        "banka altın", "fiziki altın", "dijital altın",
    ],
    "5 · Gün içi teknik": [
        "destek direnç", "pivot", "momentum", "rsi", "macd", "atr",
        "kırılım", "gün içi", "teknik analiz", "oynaklık",
    ],
    "6 · Kapalıçarşı ve serbest piyasa": [
        "kapalıçarşı", "kapali carsi", "serbest piyasa", "canlı altın", "anlık altın",
    ],
}

TR_EN = {
    "clicks": ("tıklamalar", "clicks", "tiklamalar"),
    "impressions": ("gösterimler", "impressions", "gosterimler"),
    "ctr": ("to", "ctr"),
    "position": ("ortalama konum", "position", "ortalama pozisyon", "pozisyon", "konum"),
    "query": ("en çok yapılan sorgular", "top queries", "sorgu", "query", "sorgular"),
    "page": ("en popüler sayfalar", "top pages", "sayfa", "page"),
}


def _sayi(s):
    if s is None:
        return 0.0
    s = str(s).strip().replace("%", "").replace("\xa0", "")
    if not s:
        return 0.0
    # TR biçimi: 1.234,5  ·  EN biçimi: 1,234.5
    # Tek ayraç varsa binlik mi ondalık mı olduğu grup uzunluğundan anlaşılır:
    # "1.240" binliktir (son grup 3 hane), "8,4" ondalıktır.
    def _tek_ayrac(metin, ayrac):
        gruplar = metin.split(ayrac)
        binlik = len(gruplar) > 1 and all(len(g) == 3 for g in gruplar[1:]) and 1 <= len(gruplar[0]) <= 3
        return metin.replace(ayrac, "") if binlik else metin.replace(ayrac, ".")

    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = _tek_ayrac(s, ",")
    elif "." in s:
        s = _tek_ayrac(s, ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _sutun(basliklar, tur):
    for i, b in enumerate(basliklar):
        if b.strip().lower() in TR_EN[tur]:
            return i
    return None


def satirlari_oku(metin):
    okuyucu = list(csv.reader(io.StringIO(metin)))
    if not okuyucu:
        return []
    bas = okuyucu[0]
    iq, ic, ii = _sutun(bas, "query"), _sutun(bas, "clicks"), _sutun(bas, "impressions")
    ip = _sutun(bas, "position")
    if iq is None:
        iq = 0
    out = []
    for r in okuyucu[1:]:
        if not r or len(r) <= iq:
            continue
        out.append({
            "sorgu": r[iq].strip(),
            "tik": _sayi(r[ic]) if ic is not None and len(r) > ic else 0.0,
            "gos": _sayi(r[ii]) if ii is not None and len(r) > ii else 0.0,
            "konum": _sayi(r[ip]) if ip is not None and len(r) > ip else 0.0,
        })
    return out


def yukle(yol):
    p = Path(yol)
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            adlar = [n for n in z.namelist() if n.lower().endswith(".csv")]
            tercih = [n for n in adlar if any(k in n.lower() for k in ("quer", "sorgu"))]
            hedef = (tercih or adlar)[0]
            print(f"ZIP içinden okunan: {hedef}\n")
            return satirlari_oku(z.read(hedef).decode("utf-8-sig"))
    return satirlari_oku(p.read_text(encoding="utf-8-sig"))


def kume_bul(sorgu):
    s = sorgu.lower()
    for ad, anahtarlar in KUMELER.items():
        if any(a in s for a in anahtarlar):
            return ad
    return "eşleşmeyen"


def _self_test():
    """Sayı ayrıştırma sınaması: `python3 gsc_analiz.py --self-test`.

    GSC dışa aktarımı yerel ayara göre iki farklı sayı biçimi kullanır ve
    ikisi birbirine benzer. `1.240` binlik ayraçtır, `8,4` ondalıktır; ilk
    sürüm `1.240`'ı 1,24 okuyordu ve 1.240 gösterimlik bir sorgu 1 gösterim
    görünüyordu. Bu yüzden ayrı bir sınama var.
    """
    testler = [("1.240", 1240), ("2.100", 2100), ("8,4", 8.4), ("0,97%", 0.97),
               ("1.234,5", 1234.5), ("1,234.5", 1234.5), ("410", 410), ("", 0),
               ("12", 12), ("24,3", 24.3), ("14.16%", 14.16), ("10.81", 10.81)]
    hata = 0
    for giren, beklenen in testler:
        cikan = _sayi(giren)
        if abs(cikan - beklenen) > 1e-9:
            print(f"  HATA {giren!r} -> {cikan}, beklenen {beklenen}")
            hata += 1
    # Sütun eşleme: GSC Türkçe dışa aktarımı "Pozisyon" başlığını kullanıyor.
    for baslik, tur, bekleni in [
            (["En çok yapılan sorgular", "Tıklamalar", "Gösterimler", "TO", "Pozisyon"], "position", 4),
            (["Top queries", "Clicks", "Impressions", "CTR", "Position"], "position", 4),
            (["En çok yapılan sorgular", "Tıklamalar", "Gösterimler", "TO", "Pozisyon"], "query", 0)]:
        if _sutun(baslik, tur) != bekleni:
            print(f"  HATA sütun {tur}: {_sutun(baslik, tur)}, beklenen {bekleni}")
            hata += 1
    print(f"{len(testler) + 3} sınama, {hata} hata")
    return 1 if hata else 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        raise SystemExit(_self_test())
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    satirlar = yukle(sys.argv[1])
    if not satirlar:
        raise SystemExit("Dosyada satır bulunamadı; doğru CSV mi?")

    top_tik = sum(r["tik"] for r in satirlar)
    top_gos = sum(r["gos"] for r in satirlar)
    print(f"{len(satirlar)} sorgu · {top_tik:,.0f} tıklama · {top_gos:,.0f} gösterim\n")

    # 1) küme bazında toplam
    ozet = {}
    for r in satirlar:
        k = kume_bul(r["sorgu"])
        o = ozet.setdefault(k, {"tik": 0.0, "gos": 0.0, "n": 0, "konum": []})
        o["tik"] += r["tik"]; o["gos"] += r["gos"]; o["n"] += 1
        if r["konum"]:
            o["konum"].append(r["konum"])

    print("=== KÜME BAZINDA (gösterime göre sıralı) ===")
    print(f"{'küme':<34} {'sorgu':>6} {'tıklama':>9} {'gösterim':>10} {'TO':>7} {'ort.konum':>10}")
    for ad, o in sorted(ozet.items(), key=lambda kv: -kv[1]["gos"]):
        to = (o["tik"] / o["gos"] * 100) if o["gos"] else 0
        kon = sum(o["konum"]) / len(o["konum"]) if o["konum"] else 0
        print(f"{ad:<34} {o['n']:>6} {o['tik']:>9,.0f} {o['gos']:>10,.0f} {to:>6.1f}% {kon:>10.1f}")

    # 2) fırsat: gösterim var, tıklama düşük, konum ilk sayfanın dibinde ya da 2. sayfada
    print("\n=== FIRSAT: gösterim yüksek, konum 5-20, TO düşük ===")
    firsat = [r for r in satirlar if r["gos"] >= 20 and 5 <= r["konum"] <= 20
              and (r["tik"] / r["gos"] if r["gos"] else 0) < 0.02]
    for r in sorted(firsat, key=lambda x: -x["gos"])[:25]:
        print(f"  {r['gos']:>7,.0f} gös · konum {r['konum']:>5.1f} · {r['tik']:>4,.0f} tık  "
              f"[{kume_bul(r['sorgu'])}]  {r['sorgu']}")
    if not firsat:
        print("  (bu eşiklerde sorgu yok)")

    # 3) plana girmeyen talep
    print("\n=== EŞLEŞMEYEN: hiçbir kümeye girmeyen, gösterimi yüksek sorgular ===")
    esz = [r for r in satirlar if kume_bul(r["sorgu"]) == "eşleşmeyen"]
    for r in sorted(esz, key=lambda x: -x["gos"])[:25]:
        print(f"  {r['gos']:>7,.0f} gös · {r['tik']:>4,.0f} tık · konum {r['konum']:>5.1f}  {r['sorgu']}")
    if not esz:
        print("  (hepsi bir kümeye giriyor)")

    Path("gsc_ozet.json").write_text(json.dumps(
        {"kumeler": {k: {kk: (vv if kk != "konum" else round(sum(vv)/len(vv), 1) if vv else 0)
                         for kk, vv in v.items()} for k, v in ozet.items()},
         "toplam": {"tik": top_tik, "gos": top_gos, "sorgu": len(satirlar)}},
        ensure_ascii=False, indent=1))
    print("\nÖzet gsc_ozet.json dosyasına yazıldı.")


if __name__ == "__main__":
    main()
