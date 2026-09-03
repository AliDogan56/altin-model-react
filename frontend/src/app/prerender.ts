/**
 * Ön render edilmiş gövdenin yakalanması.
 *
 * Rotalar tembel yüklenir; ilk parça gelene kadar `Suspense` bir yedek gösterir.
 * Organik inişte o yedek bir spinner olamaz: `#root` içinde arama motoru için
 * basılmış tam metin var ve React render'ı onu siler. Yedek olarak metnin kendisi
 * gösterilir, parça gelince gerçek sayfa yerine oturur — ekranda hiç boşluk olmaz.
 *
 * Modül **render'dan önce** değerlendirilmeli (App bunu içe aktarır, main.tsx
 * App'i render etmeden önce yükler). Yalnız iniş yolunda ve tek sefer kullanılır;
 * uygulama içi gezinmede başka bir sayfanın metni yedek olarak görünmemeli.
 */
const root = typeof document !== 'undefined' ? document.getElementById('root') : null;

export const PRERENDERED_HTML: string = root?.querySelector('.seo-prerender') ? root.innerHTML : '';
export const PRERENDERED_PATH: string = typeof location !== 'undefined' ? location.pathname : '';

let consumed = false;
export const prerenderConsumed = (): void => { consumed = true; };
export const prerenderFor = (pathname: string): string | null =>
  !consumed && PRERENDERED_HTML && pathname === PRERENDERED_PATH ? PRERENDERED_HTML : null;
