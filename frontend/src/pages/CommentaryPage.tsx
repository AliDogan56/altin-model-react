import { useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useDocumentMeta } from '../app/useDocumentMeta';
import SiteFooter from '../components/SiteFooter';
import SiteNav from '../components/SiteNav';
import Spinner from '../components/Spinner';
import DataTimestamp from '../components/ui/DataTimestamp';
import { COMMENTARY_STALE_MS, COMMENTARY_TEXT as T, liveSourceLabel } from '../content/commentary';
import { openLegal } from '../content/site';
import { COMMENTARY_PAGE_PATH, COMMENTARY_PAGE_TITLE, commentaryFromPage, pageDescription, turkishDateTime } from '../features/commentary/page';
import { speechChunks } from '../features/commentary/speech';
import { SEEN_AFTER_MS } from '../features/commentary/unread';
import { useCommentary } from '../features/commentary/useCommentary';
import { useNarration } from '../features/commentary/useNarration';
import type { SpeechState } from '../features/commentary/useSpeech';
import { useSpeech } from '../features/commentary/useSpeech';
import { money2, pct, shortDate } from '../lib/format';

/**
 * /yorum — günün AI yorumunun dizine açık sayfası. Pencere (`CommentaryDock`) aynı
 * metni panelde gösterir; bu sayfa Google ve paylaşım içindir. Organik inişte
 * sunucu metni HTML'e gömer (`#yorum-verisi`), kanca onunla başlar; uygulama içi
 * gezinmede `/latest` çekilir. Canlı Harem fiyatı burada yok (panel sağlayıcısı
 * dışında), yazıldığı andaki fiyat ve panele bağlantı var.
 */
function CommentaryPage() {
  const { status, data, unread, markSeen } = useCommentary(commentaryFromPage());
  useDocumentMeta(COMMENTARY_PAGE_TITLE, pageDescription(data?.summary), COMMENTARY_PAGE_PATH);
  const chunks = useMemo(() => data ? speechChunks(data) : [], [data]);
  const synth = useSpeech(chunks);
  const narration = useNarration(data?.version ?? null, data?.narration ?? null);
  const useNarrator = narration.available;
  const speech = useNarrator
    ? { supported: true, state: narration.state, current: narration.current, play: narration.play, pause: narration.pause, stop: narration.stop }
    : { supported: synth.supported, state: synth.state as SpeechState | 'loading', current: synth.current, play: synth.play, pause: synth.pause, stop: synth.stop };

  /* Sayfada okumak da okundu sayılır: 5 sn sonra damga yazılır, paneldeki rozet söner. */
  useEffect(() => {
    if (!unread) return;
    const timer = window.setTimeout(markSeen, SEEN_AFTER_MS);
    return () => window.clearTimeout(timer);
  }, [unread, markSeen]);
  // Sayfadan ayrılınca ses susar.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => () => { synth.stop(); narration.stop(); }, []);

  const stamp = data ? turkishDateTime(data.generatedAt) : '';
  return <main className="app article-page"><SiteNav current="yorum"/><article className="standalone-article ai-page">
    <nav className="breadcrumbs" aria-label="İçerik yolu"><Link to="/">Ana Sayfa</Link><span>/</span><b>{COMMENTARY_PAGE_TITLE}</b></nav>
    {status === 'loading' && <header id="icerik"><span className="eyebrow">{T.pageEyebrow}</span><h1>{COMMENTARY_PAGE_TITLE}</h1><p className="ai-state"><Spinner size="sm"/> {T.loading}</p></header>}
    {status === 'pending' && <header id="icerik"><span className="eyebrow">{T.pageEyebrow}</span><h1>{T.pendingTitle}</h1><p>{T.pending}</p></header>}
    {status === 'error' && !data && <header id="icerik"><span className="eyebrow">{T.pageEyebrow}</span><h1>{COMMENTARY_PAGE_TITLE}</h1><p>{T.error}</p></header>}
    {data && <>
      <header id="icerik"><span className="eyebrow">{T.pageEyebrow} · {stamp}</span><h1>{data.headline}</h1>
        <p className={speech.current === 'summary' ? 'is-speaking' : undefined}>{data.summary}</p></header>
      <div className="standalone-body ai-page-body">
        {speech.supported && <div className="ai-page-tools">
          {speech.state === 'loading'
            ? <button type="button" className="ai-listen" disabled aria-label={T.narrationLoading}><span aria-hidden="true">…</span> {T.narrationLoading}</button>
            : speech.state === 'speaking'
            ? <button type="button" className="ai-listen" onClick={speech.pause} aria-label={T.pause}><span aria-hidden="true">❚❚</span> {T.pause}</button>
            : <button type="button" className="ai-listen" onClick={speech.play} aria-label={speech.state === 'paused' ? T.resume : T.listen}><span aria-hidden="true">▶</span> {speech.state === 'paused' ? T.resume : T.listen}</button>}
          {speech.state !== 'idle' && <button type="button" className="ai-listen ai-listen-stop" onClick={speech.stop} aria-label={T.stop}><span aria-hidden="true">■</span></button>}
          {speech.state !== 'idle' && <span className="ai-speech-status" role="status">{speech.state === 'paused' ? T.pausedStatus : useNarrator ? T.narratingStatus : T.speakingStatus}</span>}
        </div>}
        <dl className="ai-facts">
          {data.live && <div><dt>{T.writtenAt}</dt><dd>{money2(data.live.price)}</dd><small>{liveSourceLabel(data.live.source)}{data.live.changeVsFixPct != null && <> · {T.vsFix} {data.live.changeVsFixPct >= 0 ? '+' : ''}{pct(data.live.changeVsFixPct / 100)}</>}</small></div>}
          {data.officialFix && <div><dt>{T.fix}</dt><dd>{money2(data.officialFix.price)}</dd><small>{shortDate(data.officialFix.date)}</small></div>}
          <div><dt>{T.generatedAt}</dt><dd><DataTimestamp time={data.generatedAt} label="Üretildi" staleAfterMs={COMMENTARY_STALE_MS}/></dd><small>{shortDate(data.asOf, true)}</small></div>
        </dl>
        <p className="ai-disclosure">{T.disclosure} <Link to="/">{T.liveOnPanel}</Link></p>
        {data.sections.map(section => <section key={section.id} className={speech.current === section.id ? 'is-speaking' : undefined} aria-current={speech.current === section.id ? 'true' : undefined}>
          <h2>{section.title}</h2><p>{section.text}</p>
        </section>)}
        <p className="ai-disclaimer">{data.disclaimer} <button type="button" className="link-btn" onClick={openLegal}>{T.legal}</button></p>
        <aside className="article-cta">
          <span className="article-cta-eyebrow">{T.guideEyebrow}</span>
          <b>{T.guideTitle}</b>
          <p>{T.guideSummary}</p>
          <Link className="article-cta-link" to="/rehber/ons-altin-yorum">{T.guideLink} <span aria-hidden="true">→</span></Link>
        </aside>
        <p className="article-updated"><small>{T.updatedAt}: {stamp}</small></p>
      </div>
    </>}
  </article><SiteFooter/></main>;
}

export default CommentaryPage;
