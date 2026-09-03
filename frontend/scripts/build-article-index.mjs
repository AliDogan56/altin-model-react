/* Hafif makale indeksi üretir.
 *
 * `seo-articles.json` 313 KB ham / 84 KB gzip ve tamamı ana pakete giriyordu;
 * oysa anasayfa, rehber dizini ve footer yalnız başlık ve özet gösteriyor.
 * Bu betik gövdesiz bir indeks çıkarır (15,8 KB ham / 4,5 KB gzip).
 *
 * Üretilen dosya **depoya işlenir** ki `vite dev` ön adım gerektirmesin;
 * kaynakla uyumu `content/articles.test.ts` doğrular.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Gövde (sections, faq, points, intro) dışında kalan her şey. */
export const SUMMARY_FIELDS = ['id', 'keyword', 'title', 'seoTitle', 'summary',
  'category', 'updated', 'panel'];

export const toIndex = articles => articles.map(article =>
  Object.fromEntries(SUMMARY_FIELDS.filter(f => f in article).map(f => [f, article[f]])));

const source = JSON.parse(await readFile(join(root, 'src/data/seo-articles.json'), 'utf8'));
const index = toIndex(source);
await writeFile(join(root, 'src/data/articles-index.json'),
  JSON.stringify(index, null, 2) + '\n');

const kb = b => (Buffer.byteLength(b) / 1024).toFixed(1);
console.log(`makale indeksi: ${index.length} kayıt · ` +
  `${kb(JSON.stringify(source))} KB → ${kb(JSON.stringify(index))} KB`);
