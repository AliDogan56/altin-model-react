import { Fragment, useMemo } from 'react';
import DataTimestamp from '../../components/ui/DataTimestamp';
import { FRAME, LEVEL_ROLE, SERVICE_UNREACHABLE, STATUS_TEXT, STRENGTH3, TEST_INTENSITY, type BlockStatus } from '../../content/technical';
import type { Ladder, LadderItem, Zone } from '../../services/api/technical';
import { money, pct } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';
import { sessionStaleAfterMs } from '../dashboard/useTechnical';

/**
 * Sunucu durum anahtarını cümleye çevirir; bilinmeyen anahtar `null` döner ve
 * çağıran kendi genel metnini kullanır. `OK` için de `null` (mesaj yok).
 */
export const statusText = (status: string | null | undefined): string | null =>
  status && status in STATUS_TEXT ? STATUS_TEXT[status as BlockStatus] : null;

const touchDate = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' });
/** `last_touch` sunucudan düz dize gelir; bozuk tarih `RangeError` fırlatıp
 *  tüm rayı hata sınırına düşürüyordu — ham dize yazılır, kart ayakta kalır. */
const formatTouch = (iso: string) => {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isFinite(date.getTime()) ? touchDate.format(date) : iso;
};

/** Seviyenin bölge betimi: temas sayısı, son test tarihi ve yoğunluk sözü. */
function ZoneChip({ zone }: { zone: Zone }) {
  const tone = STRENGTH3[zone.label].tone;
  if (!zone.touches) return <span className={`price-ladder-zone ${tone}`}><span>hiç test edilmedi</span></span>;
  return <span className={`price-ladder-zone ${tone}`}>
    <span>{zone.touches} temas{zone.lastTouch ? ` · son test ${formatTouch(zone.lastTouch)}` : ''}</span>
    <b>{TEST_INTENSITY[zone.label]}</b>
  </span>;
}

function LadderRow({ item, zone }: { item: LadderItem; zone: Zone | null }) {
  const role = item.role === 'TESTING' ? 'testing' : item.role ? 'nearest' : '';
  return <div className={`price-ladder-row ${item.above ? 'resistance' : 'support'} ${role}`}>
    <span><b>{item.name}</b>{item.name === 'P' && <small>Pivot</small>}
      {item.role === 'TESTING' && <em className="price-ladder-pill">{LEVEL_ROLE.TESTING.label}</em>}</span>
    <strong>{money(item.value)}</strong>
    <span>{item.distance >= 0 ? '+' : ''}{pct(item.distance)}</span>
    {zone && <ZoneChip zone={zone}/>}
  </div>;
}

/**
 * Sunucunun başlık merdivenini olduğu gibi çizer. `items` sunucudan **değer
 * azalan** sırada gelir ve `insertAt` o sıraya göre verilir; istemcide yeniden
 * sıralamak fiyat satırını yanlış yere düşürürdü. Roller (`NEAREST_*`,
 * `TESTING`) ve bölge eşlemesi (`zoneId`) de sunucunun kararıdır; burada ne
 * uzaklık ne eşik hesaplanır. Bölgeler ve referans zamanı bağlamdan okunur ki
 * iki çağıran (genel bakış rayı, pivot kartı) aynı betimi göstersin.
 */
export default function PriceLadder({ ladder }: { ladder: Ladder | null }) {
  const { levels, reference, sessionMeta, technical, technicalStatus } = useDashboard();
  const zoneById = useMemo(() => new Map((levels?.zones ?? []).map(zone => [zone.id, zone])), [levels]);
  if (!ladder) {
    const text = statusText(technical?.status.pivots)
      ?? (technicalStatus === 'fallback' ? `${SERVICE_UNREACHABLE}; seviyeler gösterilemiyor.` : 'Seviyeler için fiyat verisi bekleniyor.');
    return <div className="data-empty">{text}</div>;
  }
  /* Gecikme eşiği momentum kartıyla ortak (`sessionStaleAfterMs`): kapalı
     piyasada son seans meşru referanstır, sunucunun `stale`'i her şeyi ezer. */
  const staleAfterMs = sessionStaleAfterMs(sessionMeta);
  const current = <div className="price-ladder-current">
    <span>● Referans</span><strong>{money(ladder.price)}</strong><span>{FRAME[ladder.frame]}</span>
    <div className="price-ladder-frame"><DataTimestamp time={reference?.asOf ?? null} staleAfterMs={staleAfterMs}/></div>
  </div>;
  return <div className="price-ladder" role="group" aria-label="Referans fiyata göre sıralı destek ve direnç seviyeleri">
    <div className="price-ladder-columns"><span>Seviye</span><span>Fiyat</span><span>Uzaklık</span></div>
    {ladder.items.map((item, index) => <Fragment key={item.name}>
      {index === ladder.insertAt && current}
      <LadderRow item={item} zone={item.zoneId ? zoneById.get(item.zoneId) ?? null : null}/>
    </Fragment>)}
    {ladder.insertAt === ladder.items.length && current}
  </div>;
}
