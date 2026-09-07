import { Fragment } from 'react';
import type { Ladder } from '../../domain/pivots';
import { money, pct } from '../../lib/format';

export default function PriceLadder({ ladder }: { ladder: Ladder | null }) {
  if (!ladder) return <div className="data-empty">Seviyeler için günlük fiyat verisi bekleniyor.</div>;
  const current = <div className="price-ladder-current"><span>● Şu an</span><strong>{money(ladder.price)}</strong><span>USD</span></div>;
  return <div className="price-ladder" aria-label="Fiyata göre sıralı destek ve direnç seviyeleri">
    <div className="price-ladder-columns"><span>Seviye</span><span>Fiyat</span><span>Uzaklık</span></div>
    {ladder.items.map((item, index) => <Fragment key={item.name}>
      {index === ladder.insertAt && current}
      <div className={`price-ladder-row ${item.above ? 'resistance' : 'support'} ${[ladder.nearestDown, ladder.nearestUp].includes(item.name) ? 'nearest' : ''}`}>
        <span><b>{item.name}</b>{item.name === 'P' && <small>Pivot</small>}</span><strong>{money(item.value)}</strong><span>{item.distance >= 0 ? '+' : ''}{pct(item.distance)}</span>
      </div>
    </Fragment>)}
    {ladder.insertAt === ladder.items.length && current}
  </div>;
}
