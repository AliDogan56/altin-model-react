# Ons Altın Analiz — UI sistemi

Bu belge, mevcut frontend'de uygulanmış yerleşimi ve ortak arayüz kurallarını tanımlar. Tasarım katmanı mevcut veri akışlarını ve hesaplama çıktılarının anlamını kullanır.

## Görsel temel ve stil katmanları

Kaynak [src/styles/_tokens.scss](../src/styles/_tokens.scss) dosyasıdır. Açık tema sıcak nötr ve kırık beyaz; koyu tema graphite yüzeylerden oluşur. Tema `:root[data-theme="dark"]` ile değişir. Kontrollü altın vurgu seçili durumları ve önemli model verilerini, yeşil/kırmızı ise anlamı metin veya yön işaretiyle de belirtilen değişimleri gösterir.

- Yüzeyler: `--bg`, `--surface`, `--surface-2`, `--surface-3`.
- Metin ve sınırlar: `--text`, `--text-strong`, `--muted`, `--line`.
- Anlamsal renkler: `--gold`, `--teal`, `--red`.
- Spacing: 4, 8, 12, 16, 24, 32, 48 ve 64 px tokenları; köşeler 4, 6 ve 8 px.
- Sistem sans-serif yazı tipi, sayısal alanlarda tabular rakamlar; sayfa üst genişliği 1440 px.

[src/styles/index.scss](../src/styles/index.scss) eski özellik stillerinden sonra aşağıdaki katmanları yükler. Yeni düzenlemeler ilgili sorumluluk alanına eklenmelidir; aynı component için yeni ve bağımsız bir override dosyası açılmamalıdır.

| Dosya | Sorumluluk |
| --- | --- |
| `_terminal.scss` | Ortak kontroller, sayfa kabuğu, piyasa özeti, sekmeler, model yüzeyi ve yerleşim |
| `_terminal-tables.scss` | Ziynet listesi/tablosu ve teknik göstergeler |
| `_terminal-analysis.scss` | Model katkıları, değerlendirme, momentum ve senaryolar |
| `_terminal-charts.scss` | Fiyat/trend grafikleri, araç çubukları ve katman kontrolleri |
| `_terminal-editorial.scss` | Navigasyon, rehberler, okuma sayfaları ve footer |

## Bilgi mimarisi

[DashboardPage](../src/pages/DashboardPage.tsx), kompakt piyasa özetinin altında beş analiz sekmesi sunar. Seçim `?view=` parametresiyle URL'ye yansır; mevcut özellik rotaları ve `#feature-*` bağlantıları ilgili sekmeyi açar. Ziyaret edilmiş sekmelerin içerikleri bağlı kalır ve görünürlükleri değişir.

| Sekme | İçerik |
| --- | --- |
| Genel bakış | Ortak model/tahmin yüzeyi, fiyat grafiği, destek–direnç, momentum özeti ve ana parametreler |
| Teknik analiz | Trend, pivot seviyeleri, momentum, teknik göstergeler ve hareketli ortalamalar |
| Model | Parametre katkıları ve vade bazında geçmiş model performansı |
| Piyasalar | Ziynet kotasyonları, haberler ve makro bağlam |
| Senaryolar | Kur/finansman varsayımları ve model referans bölgeleri |

Sayfa sonunda üç seçili araştırma rehberi bulunur; tüm rehber bağlantıları native `details` dizininden ve rehber merkezinden erişilebilir. Makale gövdesi en fazla 72ch genişliğindedir.

## Mobile-first davranış

Temel yerleşim, 320 px gibi dar ekranlarda tek akış ve daralabilen grid kolonları kullanır. Beş sekme görünür kalır; kontroller gerektiğinde satır değiştirir. Mobil navigasyon bir dialog olarak açılır: ilk odak kapat düğmesine gider, Tab/Shift+Tab içeride dolaşır, kapatma ve Escape odağı tetikleyiciye döndürür. Navigasyon ve ana kontrol hedefleri en az 44 px'dir.

Alan yeterli olduğunda düzen kademeli genişler: 640 px'de özet grupları, 760 px'de masaüstü navigasyonu, 900 px'de ziynet tablosu ve 1024 px'de ana grafik ile 288 px genişliğinde seviye/momentum sütunu. Ziynet mobilde yatay kaydırılan tablo yerine açılabilir ürün listesidir. Masaüstü tablo alış, satış, makas, günlük değişim, saf altın değeri ve prim/işçilik verilerini birlikte gösterir.

Görünür odak sınırları ortak stillerden gelir. Sekmeler ve seçim kontrolleri ok tuşları ile Home/End desteğine sahiptir. `prefers-reduced-motion` hareket sürelerini azaltır.

## Ortak component'ler

| Component | Kullanım |
| --- | --- |
| [SegmentedControl](../src/components/ui/SegmentedControl.tsx) | Tek seçimli `radiogroup`; vade ve diğer seçenek gruplarında ortak klavye davranışı |
| [DataTimestamp](../src/components/ui/DataTimestamp.tsx) | Gerçek veri zamanı, bekleniyor/güncelleniyor/canlı/gecikmeli durumları; gecikme eşiği çağıran tarafından ayarlanabilir |
| [InfoTooltip](../src/components/ui/InfoTooltip.tsx) | Dokunma ve klavyeyle açılan bilgi açıklaması; dışarı tıklama ve Escape ile kapanma |
| [PriceLadder](../src/features/pivots/PriceLadder.tsx) | Mevcut `Ladder` verisinden fiyat sırası, güncel fiyat, yakın seviyeler ve yüzde uzaklık |

## Veri ve güven anlamı

7/14/30 günlük seçim aynı dashboard bağlamındaki mevcut model vadesini günceller. Sunum, veri yokken veya servis erişilemiyorken bekleme/erişilememe durumunu gösterir; gösterilemeyen değerler sıfır olarak sunulmaz.

Olasılık bandının nominal kapsamı, güncel tahminin yön doğruluğu değildir. Geçmiş yön isabeti, eğitim dışı test sonucudur ve bugünkü tahmine ait güven yüzdesi olarak adlandırılmaz. Karne MAE değeri servis tarafından sağlanan getiri oranı biriminde kalır; dolar hatasına dönüştürülmez. Momentum skoru kırılım olasılığı olarak sunulmaz. Destek/direnç ve senaryo alanları referans değerlerdir; yeni kesinlik veya yatırım garantisi üretmez.

Yeni component'ler aynı veri yokluğu, zaman, birim ve açıklama ayrımlarını korumalıdır. Görsel gösterim için veri kaynağında bulunmayan başarı, nedensellik veya olasılık değerleri eklenmemelidir.
