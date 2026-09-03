import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const cache = new Map();
const cached = async (key, ttl, factory) => {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.time < ttl) return hit.value;
  const value = await factory();
  cache.set(key, { time: Date.now(), value });
  return value;
};
const send = (res, status, type, body) => {
  res.statusCode = status;
  res.setHeader('Content-Type', type);
  res.setHeader('Cache-Control', 'no-store');
  res.end(body);
};
const fetchText = async url => {
  const r = await fetch(url, { headers: { 'User-Agent': 'GoldModelDashboard/1.0' } });
  if (!r.ok) throw new Error(`Kaynak hatası: ${r.status}`);
  return r.text();
};
const decodeXml = value => value.replace(/<!\[CDATA\[|\]\]>/g, '').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const tag = (xml, name) => decodeXml((xml.match(new RegExp(`<${name}>([\\s\\S]*?)<\\/${name}>`)) || [,''])[1].trim());

function liveDataApi() {
  return {
    name: 'live-data-api',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        try {
          const url = new URL(req.url, 'http://localhost');
          if (url.pathname === '/api/fred') {
            const id = (url.searchParams.get('id') || '').replace(/[^A-Z0-9_]/g, '');
            if (!id) return send(res, 400, 'application/json', '{"error":"series id gerekli"}');
            const start = new Date(Date.now() - 800 * 86400000).toISOString().slice(0, 10);
            const body = await cached(`fred:${id}`, 900_000, () => fetchText(`https://fred.stlouisfed.org/graph/fredgraph.csv?id=${id}&cosd=${start}`));
            return send(res, 200, 'text/csv; charset=utf-8', body);
          }
          if (url.pathname === '/api/news') {
            const rssUrl = 'https://news.google.com/rss/search?q=gold+Federal+Reserve+inflation+Treasury+yield&hl=en-US&gl=US&ceid=US:en';
            const xml = await cached('news', 600_000, () => fetchText(rssUrl));
            const articles = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].slice(0, 10).map(m => ({ title: tag(m[1], 'title'), url: tag(m[1], 'link'), source: tag(m[1], 'source'), published: tag(m[1], 'pubDate') }));
            return send(res, 200, 'application/json; charset=utf-8', JSON.stringify({ articles }));
          }
          next();
        } catch (error) {
          send(res, 502, 'application/json; charset=utf-8', JSON.stringify({ error: error.message }));
        }
      });
    }
  };
}

export default defineConfig(({mode})=>{
  const env=loadEnv(mode,'.','');
  return {
    plugins: [react(), liveDataApi()],
    // Manifest: ön render betiği rota parçalarını `modulepreload` ile bağlamak için okur.
    build: { manifest: true },
    // Yalnız domain katmanı test edilir: saf fonksiyonlar, React ve DOM gerektirmez.
    test: { environment: 'node', include: ['src/domain/**/*.test.ts', 'src/lib/**/*.test.ts', 'src/app/**/*.test.ts', 'src/services/**/*.test.ts', 'src/content/**/*.test.ts'] },
    server: { host: '0.0.0.0', port: 5173, strictPort: true, proxy: {'/backend':{target:env.VITE_BACKEND_PROXY||'http://127.0.0.1:8000',changeOrigin:true,rewrite:path=>path.replace(/^\/backend/,'')}} },
    preview: { host: '0.0.0.0', port: 4173, strictPort: true }
  };
});
