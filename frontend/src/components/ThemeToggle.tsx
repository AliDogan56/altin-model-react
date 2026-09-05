import { useCallback, useEffect, useState } from 'react';
import { applyTheme, isTheme, readStoredTheme, storeTheme, type Theme } from '../lib/theme';

/**
 * Aydınlık/koyu tema anahtarı. Damga zaten index.html'deki satır içi betik
 * tarafından ilk boyamadan önce basılıyor; bu bileşen yalnız o değeri okur ve
 * kullanıcı değiştirdiğinde günceller.
 */
function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<Theme>(() =>
    typeof document === 'undefined' ? 'light' : readStoredTheme());

  // Mobil menü ve masaüstü düğmesi aynı tema damgasını izler.
  useEffect(() => {
    const root = document.documentElement;
    const sync = () => { if (isTheme(root.dataset.theme)) setTheme(root.dataset.theme); };
    if (!isTheme(root.dataset.theme)) applyTheme(readStoredTheme());
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  const toggle = useCallback(() => {
    const next: Theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    storeTheme(next);
    applyTheme(next);
    setTheme(next);
  }, []);

  const dark = theme === 'dark';
  const label = dark ? 'Aydınlık temaya geç' : 'Koyu temaya geç';

  return (
    <button type="button" className={`theme-toggle${compact ? ' compact' : ''}`}
      onClick={toggle} title={label} aria-label={label} aria-pressed={dark}>
      <span className="theme-icon" aria-hidden="true">
        {dark
          ? <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
            </svg>
          : <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>
            </svg>}
      </span>
      <span className="theme-text">{dark ? 'Aydınlık' : 'Koyu'}</span>
    </button>
  );
}

export default ThemeToggle;
