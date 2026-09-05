import { useEffect, useState } from 'react';

export default function DataTimestamp({ time, live = false, updating = false, staleAfterMs = 5 * 60 * 1000, label }: {
  time: Date | string | null; live?: boolean; updating?: boolean; staleAfterMs?: number; label?: string;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);
  const date = time ? new Date(time) : null;
  const valid = date && Number.isFinite(date.getTime());
  const stale = valid && now - date.getTime() > staleAfterMs;
  const state = updating ? 'Güncelleniyor' : !valid ? 'Veri bekleniyor' : stale ? 'Gecikmeli veri' : live ? 'Canlı' : 'Son veri';
  return <span className={`data-timestamp ${stale ? 'is-stale' : live && valid ? 'is-live' : ''}`}>
    <i aria-hidden="true"/>{label || state}
    {valid && <time dateTime={date.toISOString()} title={date.toLocaleString('tr-TR')}>
      {typeof time === 'string' && !time.includes('T')
        ? date.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' })
        : stale ? date.toLocaleString('tr-TR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : date.toLocaleTimeString('tr-TR')}
    </time>}
    {label && stale && <span>· Gecikmeli veri</span>}
  </span>;
}
