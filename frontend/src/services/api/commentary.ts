import { commentaryApi } from '../config';

/**
 * Yorum servisi (`/commentary-service/v1/commentary/latest`): masanın son Türkçe
 * yorumu. Uç üretim tetiklemez, diskten okur; ilk üretimden önce **404** döner ve
 * bu bir arıza değil "hazırlanıyor" durumudur. Sayılar ve model adları (`usage`)
 * arayüze taşınmaz; üçüncü taraf adları `content/commentary.ts` sözlüğüyle çevrilir.
 */
export type CommentarySection = { id: string; title: string; text: string };
export type CommentaryLive = {
  price: number; source: string; timeUtc: string | null;
  changeVsFixPct: number | null; changeVsFixUsd: number | null; changeVsPrevClosePct: number | null;
};
export type Commentary = {
  version: string; asOf: string; generatedAt: string; ageSeconds: number | null; runMode: string; triggerReason: string | null;
  live: CommentaryLive | null; officialFix: { date: string; price: number } | null;
  title: string; headline: string; summary: string; sections: CommentarySection[]; disclaimer: string;
  narration: Narration | null;
};
/** Sunucuda üretilmiş anlatıcı sesi; bölüm zamanları karakter oranıyla tahmin (`estimated`). */
export type NarrationSegment = { id: string; start: number; end: number };
export type Narration = { voice: string; durationSeconds: number; segments: NarrationSegment[]; estimated: boolean };

export type CommentaryResult = { kind: 'ready'; data: Commentary } | { kind: 'pending' };

const str = (v: unknown): string | null => typeof v === 'string' ? v : null;
const num = (v: unknown): number | null => typeof v === 'number' && Number.isFinite(v) ? v : null;
const obj = (v: unknown): Record<string, unknown> | null => v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;

/** Bozuk şema `null`: yarım bir yorum basmaktansa düğme "hazırlanıyor" der. */
export const parseCommentary = (raw: unknown): Commentary | null => {
  const d = obj(raw); if (!d) return null;
  const version = str(d.version), title = str(d.title), headline = str(d.headline), summary = str(d.summary), disclaimer = str(d.disclaimer);
  if (!version || !title || !headline || !summary || !disclaimer || !Array.isArray(d.sections)) return null;
  const sections: CommentarySection[] = [];
  for (const item of d.sections) {
    const s = obj(item); const id = s && str(s.id), t = s && str(s.title), text = s && str(s.text);
    if (id && t && text) sections.push({ id, title: t, text });
  }
  if (!sections.length) return null;
  const l = obj(d.live); const price = l && num(l.price);
  const fix = obj(d.official_fix); const fixDate = fix && str(fix.date), fixPrice = fix && num(fix.price);
  const trigger = obj(d.trigger);
  const n = obj(d.narration); const duration = n && num(n.duration_seconds);
  const segments: NarrationSegment[] = [];
  if (n && Array.isArray(n.segments)) for (const raw of n.segments) {
    const s = obj(raw); const id = s && str(s.id), start = s && num(s.start), end = s && num(s.end);
    if (id && start != null && end != null) segments.push({ id, start, end });
  }
  const narration: Narration | null = n && duration != null && duration > 0
    ? { voice: str(n.voice) ?? '', durationSeconds: duration, segments, estimated: n.estimated !== false } : null;
  return {
    version, asOf: str(d.as_of) ?? '', generatedAt: str(d.generated_at) ?? '', ageSeconds: num(d.age_seconds), runMode: str(d.run_mode) ?? '',
    triggerReason: trigger ? str(trigger.reason) : null,
    live: l && price != null ? { price, source: str(l.source) ?? '', timeUtc: str(l.time_utc), changeVsFixPct: num(l.change_vs_fix_pct),
      changeVsFixUsd: num(l.change_vs_fix_usd), changeVsPrevClosePct: num(l.change_vs_prev_close_pct) } : null,
    officialFix: fixDate && fixPrice != null ? { date: fixDate, price: fixPrice } : null,
    title, headline, summary, sections, disclaimer, narration,
  };
};

/** Sürüm sorguda: aynı adres yeni yorumda değişsin, tarayıcı eskisini önbellekten çalmasın. */
export const commentaryAudioUrl = (version: string): string =>
  `${commentaryApi()}/v1/commentary/latest/audio?v=${encodeURIComponent(version)}`;

export const fetchCommentary = async (signal?: AbortSignal): Promise<CommentaryResult> => {
  const r = await fetch(`${commentaryApi()}/v1/commentary/latest`, { signal });
  if (r.status === 404) return { kind: 'pending' };
  if (!r.ok) throw new Error(`commentary: ${r.status}`);
  const data = parseCommentary(await r.json());
  return data ? { kind: 'ready', data } : { kind: 'pending' };
};
