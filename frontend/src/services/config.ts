/** `{origin}` prod'da aynı origin (nginx proxy), `{host}` lokalde 8000. */
const API_BASE = (import.meta.env.VITE_API_BASE || 'http://{host}:8000')
  .replace('{origin}', window.location.origin)
  .replace('{host}', window.location.hostname)
  .replace(/\/$/, '');

export const MARKET_API = `${API_BASE}/market-service`;
export const MODEL_API = `${API_BASE}/model-service`;

export const BINANCE_WS = 'wss://stream.binance.com:9443/ws/paxgusdt@ticker';
export const HAREM_WS = 'wss://hrmsocketonly.haremaltin.com';
