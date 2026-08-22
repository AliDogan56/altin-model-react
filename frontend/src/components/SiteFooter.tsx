import { Link } from 'react-router-dom';
import { SEO_ARTICLES } from '../content/articles';
import { openLegal } from '../content/site';

function SiteFooter() {
  const featured=SEO_ARTICLES.slice(0,8);
  return <footer className="site-footer" id="risk-notu">
    <div className="footer-grid">
      <section className="footer-about" aria-labelledby="footer-brand-title"><Link className="footer-brand" to="/"><img src="/favicon.svg" alt=""/><span id="footer-brand-title">Ons Altın Analiz</span></Link><p>Canlı ons altın verilerini, ekonomik göstergeleri ve yapay zekâ destekli fiyat senaryolarını bir araya getiren bağımsız araştırma platformu.</p></section>
      <nav aria-label="Footer hızlı bağlantılar"><h2>Hızlı erişim</h2><a href="/#panel">Canlı ons paneli</a><a href="/#tahmin">Altın tahminleri</a><a href="/rehber">Altın rehberleri</a><a href="/sitemap.xml">Sitemap</a></nav>
      {/* Güven sayfaları: YMYL kategorisinde her sayfadan erişilebilir olmalı. */}
      <nav aria-label="Site bilgileri"><h2>Site</h2><a href="/hakkimizda">Hakkımızda</a><a href="/yazar">Yazar ve metodoloji</a><a href="/iletisim">İletişim</a><a href="/gizlilik">Gizlilik</a></nav>
      <nav aria-label="Öne çıkan altın rehberleri"><h2>Öne çıkan rehberler</h2>{featured.map(article=><Link to={`/rehber/${article.id}`} key={article.id}>{article.title}</Link>)}</nav>
      <section className="footer-creator" aria-labelledby="creator-title"><h2 id="creator-title">Projenin yaratıcısı</h2><strong>Ali Doğan</strong><span>Yaratıcı ve geliştirici</span><a className="linkedin-link" href="https://www.linkedin.com/in/ali-do%C4%9Fan-86b57721a/" target="_blank" rel="noopener noreferrer me" aria-label="Ali Doğan LinkedIn profilini yeni sekmede aç"><i aria-hidden="true">in</i>LinkedIn profilini görüntüle</a></section>
    </div>
    
    <div className="footer-bottom"><p>Bu platform eğitim ve araştırma amaçlıdır; yatırım danışmanlığı kapsamında değildir, getiri veya kâr garantisi sunmaz. <button type="button" className="link-btn" onClick={openLegal}>Yasal uyarının tamamı</button></p><span>© {new Date().getFullYear()} Ons Altın Analiz</span></div>
  </footer>;
}

export default SiteFooter;
