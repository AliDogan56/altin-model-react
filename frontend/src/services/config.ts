/** `{origin}` prod'da aynı origin (nginx proxy), `{host}` lokalde 8000.
 *
 *  Modül yüklenirken doğrudan `window.location` okunuyordu; tarayıcı dışı her
 *  ortamda (test, ön render) import anında ReferenceError veriyordu. Artık
 *  adresler çağrı anında, `window` yoksa göreli olarak çözülür.
 */
const resolveBase = (): string => {
  const template = import.meta.env.VITE_API_BASE || 'http://{host}:8000';
  if (typeof window === 'undefined') return template.replace(/^https?:\/\/\{host\}:\d+/, '').replace(/\/$/, '');
  return template
    .replace('{origin}', window.location.origin)
    .replace('{host}', window.location.hostname)
    .replace(/\/$/, '');
};

export const marketApi = () => `${resolveBase()}/market-service`;
export const modelApi = () => `${resolveBase()}/model-service`;

export const HAREM_WS = 'wss://hrmsocketonly.haremaltin.com';
