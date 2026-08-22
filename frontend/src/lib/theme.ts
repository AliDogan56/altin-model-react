/**
 * Tema seçimi. Varsayılan **aydınlık**; sistem tercihine göre otomatik geçiş
 * bilinçli olarak yok — ürün kararı budur. Seçim localStorage'da saklanır.
 *
 * Uygulama, kök öğeye `data-theme` damgalar; palet `styles/_tokens.scss`
 * içinde bu damgaya göre değişir. İlk boyamadan önce damganın basılması için
 * `index.html` içinde küçük bir satır içi betik aynı anahtarı okur; buradaki
 * sabitler onunla birebir aynı kalmalıdır.
 */

export type Theme = 'light' | 'dark';

export const THEME_KEY = 'oaa-theme';
export const DEFAULT_THEME: Theme = 'light';

/** Tarayıcı adres çubuğu rengi; damgayla birlikte güncellenir. */
const THEME_COLOR: Record<Theme, string> = { light: '#eef2f7', dark: '#07111f' };

export const isTheme = (value: unknown): value is Theme =>
  value === 'light' || value === 'dark';

export const readStoredTheme = (): Theme => {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    return isTheme(stored) ? stored : DEFAULT_THEME;
  } catch {
    // Gizli sekmede veya depolama kapalıyken okuma patlar; varsayılan yeter.
    return DEFAULT_THEME;
  }
};

/**
 * Tema damgasını basar.
 *
 * Damgadan önce geçişler kısa süreliğine kapatılır: `transition:color` tanımlı
 * bir öğede özel değişken değişince Chrome hesaplanan rengi **eski değerinde
 * donduruyor** (ölçüldü: ziynet fiyatı koyu temada aydınlık temanın rengiyle
 * kalıyordu). Sınıf bir kare sonra kaldırılır.
 */
export const applyTheme = (theme: Theme): void => {
  const root = document.documentElement;
  if (root.dataset.theme && root.dataset.theme !== theme) {
    root.classList.add('theme-switching');
    // Zorunlu yeniden akış: sınıfın damgadan önce uygulanmasını garanti eder.
    void root.offsetHeight;
    const release = () => root.classList.remove('theme-switching');
    requestAnimationFrame(() => requestAnimationFrame(release));
    // rAF gizli sekmede hiç çalışmaz; yedek olmazsa geçişler kalıcı kapanıyor.
    window.setTimeout(release, 120);
  }
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[theme]);
};

export const storeTheme = (theme: Theme): void => {
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Yazamıyorsak seçim yalnız bu oturumda geçerli olur; hata göstermeye değmez.
  }
};
