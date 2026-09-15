import { useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import DataTimestamp from '../../components/ui/DataTimestamp';
import Spinner from '../../components/Spinner';
import { COMMENTARY_STALE_MS, COMMENTARY_TEXT as T, liveSourceLabel } from '../../content/commentary';
import { openLegal } from '../../content/site';
import { money2, pct, shortDate } from '../../lib/format';
import { useDashboard } from '../dashboard/DashboardContext';
import type { SpeechState } from './useSpeech';
import { driftSinceGeneration } from './drift';
import { useCommentary } from './useCommentary';
import { speechChunks } from './speech';
import { useNarration } from './useNarration';
import { useSpeech } from './useSpeech';

const FOCUSABLE = 'button, a[href], [tabindex]:not([tabindex="-1"])';
const PARAM = 'yorum';

/** Yapay zekâ ikonu: dört kollu kıvılcım + iki küçük yıldız; `currentColor`, ışıltı CSS'te. */
export function SparkIcon() {
  return <svg className="ai-spark" viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true" focusable="false">
    <path d="M12 2.5c.5 4.6 2.9 7 7.5 7.5-4.6.5-7 2.9-7.5 7.5-.5-4.6-2.9-7-7.5-7.5 4.6-.5 7-2.9 7.5-7.5z"/>
    <path className="ai-spark-minor" d="M19 15.5c.2 1.8 1.2 2.8 3 3-1.8.2-2.8 1.2-3 3-.2-1.8-1.2-2.8-3-3 1.8-.2 2.8-1.2 3-3zM5 15c.15 1.3.85 2 2.2 2.2-1.35.15-2.05.85-2.2 2.2-.15-1.35-.85-2.05-2.2-2.2 1.35-.2 2.05-.9 2.2-2.2z"/>
  </svg>;
}

/**
 * Sağ altta sabit "AI yorumu" düğmesi ve dokununca animasyonla açılan pencere.
 * Açık/kapalı durumu `?yorum=1` sorgusunda: paylaşılabilir, geri tuşu kapatır.
 * Odak yönetimi `LegalModal` ile aynı: açılışta ilk odaklanabilir öğe, Tab tuzağı,
 * Esc ve arka plana dokunma kapatır, kapanınca odak düğmeye döner.
 */
export default function CommentaryDock() {
  const { status, data, unread, refresh, markSeen } = useCommentary();
  const { harem } = useDashboard();
  const livePrice = harem.satis ?? null;
  const drift = data ? driftSinceGeneration(livePrice, data.live?.price) : null;
  const [params, setParams] = useSearchParams();
  const open = params.get(PARAM) === '1';
  const sheet = useRef<HTMLDivElement>(null);
  const chunks = useMemo(() => data ? speechChunks(data) : [], [data]);
  const synth = useSpeech(chunks);
  const narration = useNarration(data?.version ?? null, data?.narration ?? null);
  /* Anlatıcı sesi varsa o, yoksa ya da yüklenemezse cihazın sentezleyicisi; düğme ve durum makinesi aynı. */
  const useNarrator = narration.available;
  const speech = useNarrator
    ? { supported: true, state: narration.state, current: narration.current, play: narration.play, pause: narration.pause, stop: narration.stop }
    : { supported: synth.supported, state: synth.state as SpeechState | 'loading', current: synth.current, play: synth.play, pause: synth.pause, stop: synth.stop };
  const opener = useRef<HTMLButtonElement>(null);

  const setOpen = (next: boolean) => {
    const copy = new URLSearchParams(params);
    if (next) copy.set(PARAM, '1'); else copy.delete(PARAM);
    setParams(copy, { replace: !next });
  };

  useEffect(() => {
    if (!open) return;
    void refresh(); markSeen();
    const node = sheet.current;
    const focusable = () => Array.from(node?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    const frame = requestAnimationFrame(() => focusable()[0]?.focus());
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setOpen(false); return; }
      if (event.key !== 'Tab') return;
      const items = focusable(); if (!items.length) return;
      const first = items[0], last = items[items.length - 1], active = document.activeElement;
      if (event.shiftKey && (active === first || !node?.contains(active))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && active === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    const previous = document.body.style.overflow; document.body.style.overflow = 'hidden';
    return () => { cancelAnimationFrame(frame); document.removeEventListener('keydown', onKey); document.body.style.overflow = previous; synth.stop(); narration.stop(); opener.current?.focus(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  useEffect(() => { if (open) markSeen(); }, [open, markSeen]);

  return <>
    <button ref={opener} type="button" className={`ai-fab${unread ? ' has-new' : ''}`} onClick={() => setOpen(true)}
      aria-haspopup="dialog" aria-expanded={open} aria-label={unread ? `${T.button} · ${T.newBadge}` : T.button}>
      <span className="ai-fab-glow" aria-hidden="true"/><SparkIcon/><span className="ai-fab-label">{T.button}</span>
      {unread && <span className="ai-fab-badge" aria-hidden="true"/>}
    </button>
    {open && <div className="ai-modal" role="dialog" aria-modal="true" aria-labelledby="ai-modal-title">
      <div className="ai-backdrop" onClick={() => setOpen(false)}/>
      <div className="ai-sheet" ref={sheet}>
        <header className="ai-head">
          <div className="ai-head-title"><SparkIcon/><div><span className="ai-kicker">{T.kicker}</span><h2 id="ai-modal-title">{T.title}</h2></div></div>
          <div className="ai-head-actions">
            {speech.supported && data && <>
              {speech.state === 'loading'
                ? <button type="button" className="ai-listen" disabled aria-label={T.narrationLoading}><span aria-hidden="true">…</span> {T.narrationLoading}</button>
                : speech.state === 'speaking'
                ? <button type="button" className="ai-listen" onClick={speech.pause} aria-label={T.pause}><span aria-hidden="true">❚❚</span> {T.pause}</button>
                : <button type="button" className="ai-listen" onClick={speech.play} aria-label={speech.state === 'paused' ? T.resume : T.listen}><span aria-hidden="true">▶</span> {speech.state === 'paused' ? T.resume : T.listen}</button>}
              {speech.state !== 'idle' && <button type="button" className="ai-listen ai-listen-stop" onClick={speech.stop} aria-label={T.stop}><span aria-hidden="true">■</span></button>}
            </>}
            <button type="button" className="ai-close" onClick={() => setOpen(false)} aria-label={T.close}>×</button>
          </div>
        </header>
        {speech.state !== 'idle' && <p className="ai-speech-status" role="status">{speech.state === 'paused' ? T.pausedStatus : useNarrator ? T.narratingStatus : T.speakingStatus}</p>}
        <div className="ai-body">
          {status === 'loading' && <p className="ai-state"><Spinner size="sm"/> {T.loading}</p>}
          {status === 'pending' && <p className="ai-state">{T.pending}</p>}
          {status === 'error' && <p className="ai-state">{T.error}</p>}
          {data && <article className="ai-article">
            <p className={`ai-headline${speech.current === 'headline' ? ' is-speaking' : ''}`} style={{ '--i': 0 } as React.CSSProperties}>{data.headline}</p>
            <dl className="ai-facts" style={{ '--i': 1 } as React.CSSProperties}>
              <div><dt>{T.live}</dt><dd>{livePrice ? money2(livePrice) : '—'}</dd><small><DataTimestamp time={harem.time} live={harem.live}/></small></div>
              {data.live && <div><dt>{T.writtenAt}</dt><dd>{money2(data.live.price)}{drift && <small className={drift.usd >= 0 ? 'positive' : 'negative'}> {drift.usd >= 0 ? '+' : ''}{pct(drift.pct / 100)} {T.sinceThen}</small>}</dd><small>{liveSourceLabel(data.live.source)}{data.live.changeVsFixPct != null && <> · {T.vsFix} {data.live.changeVsFixPct >= 0 ? '+' : ''}{pct(data.live.changeVsFixPct / 100)}</>}</small></div>}
              {data.officialFix && <div><dt>{T.fix}</dt><dd>{money2(data.officialFix.price)}</dd><small>{shortDate(data.officialFix.date)}</small></div>}
              <div><dt>{T.generatedAt}</dt><dd><DataTimestamp time={data.generatedAt} label="Üretildi" staleAfterMs={COMMENTARY_STALE_MS}/></dd><small>{shortDate(data.asOf, true)}</small></div>
            </dl>
            {drift?.beyondTrigger && <p className="ai-drift-note" style={{ '--i': 2 } as React.CSSProperties}>{T.driftNote}</p>}
            <p className={`ai-summary${speech.current === 'summary' ? ' is-speaking' : ''}`} style={{ '--i': 2 } as React.CSSProperties}>{data.summary}</p>
            {data.sections.map((section, index) => <section key={section.id} className={`ai-section${speech.current === section.id ? ' is-speaking' : ''}`} aria-current={speech.current === section.id ? 'true' : undefined} style={{ '--i': index + 3 } as React.CSSProperties}>
              <h3>{section.title}</h3><p>{section.text}</p>
            </section>)}
            <p className="ai-disclaimer" style={{ '--i': data.sections.length + 3 } as React.CSSProperties}>{data.disclaimer} <button type="button" className="link-btn" onClick={openLegal}>{T.legal}</button></p>
          </article>}
        </div>
      </div>
    </div>}
  </>;
}
