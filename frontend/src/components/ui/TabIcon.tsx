/**
 * Çalışma alanı sekmelerinin ikonları (mobilde alt gezinme çubuğu). Satır içi
 * SVG: `currentColor` ile sekmenin rengini alır, 24'lük ızgarada 1,75 px çizgi;
 * `aria-hidden`, metin etiketi zaten yanında. Anahtarlar `DashboardPage.VIEWS`
 * ile aynı.
 */
import type { ReactElement } from 'react';

export type TabIconName = 'overview' | 'technical' | 'model' | 'markets' | 'scenarios';

const PATHS: Record<TabIconName, ReactElement> = {
  /* dört pano karosu */
  overview: <><rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/>
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/></>,
  /* üç mum */
  technical: <><path d="M6 3.5v3M6 16.5v4M12 3v2.5M12 15v4M18 6v3M18 17v3.5"/>
    <rect x="4" y="6.5" width="4" height="10" rx="1"/><rect x="10" y="5.5" width="4" height="9.5" rx="1"/><rect x="16" y="9" width="4" height="8" rx="1"/></>,
  /* ağ düğümleri */
  model: <><circle cx="5.5" cy="6" r="2.2"/><circle cx="5.5" cy="18" r="2.2"/><circle cx="18.5" cy="12" r="2.6"/>
    <path d="M7.5 7l8.6 3.7M7.5 17l8.6-3.7"/></>,
  /* iki sikke */
  markets: <><circle cx="9" cy="12" r="6.5"/><path d="M13.6 7.4a6.5 6.5 0 1 1 0 9.2"/><path d="M7 12h4"/></>,
  /* dallanan yol */
  scenarios: <><path d="M6 6v12"/><path d="M6 9c0 4 2.2 5.5 6 5.5h4.5"/><path d="M14 11.5l3 3-3 3"/>
    <circle cx="6" cy="4.5" r="1.8"/><circle cx="6" cy="19.5" r="1.8"/></>,
};

function TabIcon({ name }: { name: TabIconName }) {
  return <svg className="tab-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
    strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{PATHS[name]}</svg>;
}

export default TabIcon;
