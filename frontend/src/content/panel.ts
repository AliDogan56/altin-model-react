import panelFeatures from '../data/panel-features.json';
import type { PanelFeature } from './types';

export const PANEL_FEATURES = panelFeatures as PanelFeature[];

/** Panel başlıkları özellik sayfalarıyla aynı metinden gelir: hem tutarlılık için
 *  hem de anahtar kelimelerin anasayfada da geçmesi için. */
export const featureBy = (anchor: string): PanelFeature => PANEL_FEATURES.find(f => f.anchor === anchor)!;

export const featureBySlug = (slug: string): PanelFeature | undefined =>
  PANEL_FEATURES.find(f => f.slug === slug);
