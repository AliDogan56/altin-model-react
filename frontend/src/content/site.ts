export const SITE_NAME = 'Ons Altın Analiz';
export const SITE_URL = 'https://onsaltinanaliz.com';
export const LINKEDIN_URL = 'https://www.linkedin.com/in/ali-do%C4%9Fan-86b57721a/';

export const HORIZON_LABELS: Record<number, string> = { 7: '1 Hafta', 30: '1 Ay', 90: '3 Ay', 180: '6 Ay' };

export const LEGAL_SECTIONS: [string, string][] = [
  ['Yatırım danışmanlığı değildir', 'Bu sitede yer alan bilgi, yorum, tahmin ve tavsiyeler yatırım danışmanlığı kapsamında değildir. Yatırım danışmanlığı hizmeti, yetkili kuruluşlar tarafından kişilerin risk ve getiri tercihleri dikkate alınarak kişiye özel sunulur. Buradaki içerik geneldir; mali durumunuza ve risk-getiri tercihlerinize uygun olmayabilir.'],
  ['Tahminler garanti değildir', 'Fiyat tahminleri geçmiş verilerden türetilmiş istatistiksel kestirimlerdir; kesinlik, isabet ya da kâr garantisi taşımaz. Model çıktıları hata payı ile birlikte sunulur ve gerçekleşen fiyatlar bandın dışına çıkabilir.'],
  ['Veri doğruluğu', 'Veriler üçüncü taraf kaynaklardan alınır; doğruluğu, güncelliği ve kesintisizliği garanti edilmez. Gecikme, hata veya eksiklik olabilir; gösterge niteliğindedir.'],
  ['Sorumluluk reddi', 'Bu platform hiçbir finansal ürün için alım-satım teklifi ya da çağrısı değildir. İçeriğe dayanarak alınan kararlardan ve doğabilecek doğrudan veya dolaylı zararlardan site sahibi sorumlu tutulamaz. Yatırım kararlarınızın sorumluluğu size aittir.'],
];

export const openLegal = () => window.dispatchEvent(new Event('legal:open'));

/* Bölümler artık Panel açılır menüsünde; ayrı '#tahmin' bağlantısı hem gereksizdi
   hem de kartların id'si feature-tahmin olduğu için çalışmıyordu. */
export const NAV_SECTIONS: [string, string][] = [['/', 'Canlı Panel']];

/** Türkçe arama için harf katlama: 'İ' ve aksanlar eşleşmeyi bozuyordu. */
export const fold = (value: string) => value.toLocaleLowerCase('tr').replace(/[\u0300-\u036f]/g, '');

export const PAGE_META = {
  home: {
    title: 'Canlı Ons Altın Tahmini ve Analiz Paneli',
    description: 'Canlı ons altın fiyatını izleyin; yapay zekâ destekli 1, 3 ve 6 aylık tahminleri, piyasa parametrelerini ve altın analiz rehberlerini inceleyin.',
    path: '/',
  },
  guides: {
    title: 'Ons Altın Rehberi',
    description: 'Ons, gram ve ziynet altın hakkında 31 rehber: fiyat oluşumu, tahmin okuma, alım satım pratiği ve vergi.',
    path: '/rehber',
  },
  panel: {
    title: 'Canlı Altın Paneli Özellikleri',
    description: 'Canlı altın panelindeki tahmin, grafik, ziynet fiyatları, teknik gösterge ve pivot bölümleri.',
    path: '/panel',
  },
} as const;
