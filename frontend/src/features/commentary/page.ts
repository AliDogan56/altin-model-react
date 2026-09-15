import { parseCommentary, type Commentary } from '../../services/api/commentary';
import { PAGE_META } from '../../content/site';

/**
 * /yorum sayfasının saf yardımcıları. Sunucu parçası (`commentary_page.py`) ile aynı
 * kuralları uygular: başlık sabit, tarih Türkiye saatinde "15 Eylül 2026, 15:54",
 * açıklama kelime sınırında 155 karakter. İkisi ayrışırsa organik inişte basılan
 * meta ile React'in sonradan yazdığı meta farklı olur.
 */
export const COMMENTARY_PAGE_PATH = PAGE_META.commentary.path;
export const COMMENTARY_PAGE_TITLE = PAGE_META.commentary.title;
export const DESCRIPTION_MAX = 155;
export const EMBED_ID = 'yorum-verisi';

const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const ISTANBUL_OFFSET_MS = 3 * 60 * 60 * 1000;   // Türkiye kalıcı UTC+3, yaz saati yok

/** '2026-09-15T12:54:39+00:00' → '15 Eylül 2026, 15:54'; bozuk girdi boş dize. */
export const turkishDateTime = (iso: string | null | undefined): string => {
  if (!iso) return '';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return '';
  const t = new Date(ms + ISTANBUL_OFFSET_MS);
  const hh = String(t.getUTCHours()).padStart(2, '0'), mm = String(t.getUTCMinutes()).padStart(2, '0');
  return `${t.getUTCDate()} ${AYLAR[t.getUTCMonth()]} ${t.getUTCFullYear()}, ${hh}:${mm}`;
};

/** Özetten arama sonucu açıklaması: kelime sınırında kesilir, sonuna üç nokta. */
export const pageDescription = (summary: string | null | undefined): string => {
  const text = (summary ?? '').split(/\s+/).filter(Boolean).join(' ');
  if (!text) return PAGE_META.commentary.description;
  if (text.length <= DESCRIPTION_MAX) return text;
  let cut = text.slice(0, DESCRIPTION_MAX - 1);
  const space = cut.lastIndexOf(' ');
  if (space > 0) cut = cut.slice(0, space);
  return `${cut.replace(/[,.;:]+$/, '')}…`;
};

/** Sunucunun HTML'e gömdüğü yorum; hidrasyonda eşzamanlı okunur ki metin bir an kaybolmasın. */
export const commentaryFromPage = (): Commentary | null => {
  if (typeof document === 'undefined') return null;
  const node = document.getElementById(EMBED_ID);
  if (!node?.textContent) return null;
  try { return parseCommentary(JSON.parse(node.textContent)); } catch { return null; }
};
