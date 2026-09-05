import { Link } from 'react-router-dom';
import { openLegal } from '../content/site';

function SiteFooter() {
  return <footer className="site-footer" id="risk-notu">
    <div className="footer-grid">
      <section className="footer-about" aria-labelledby="footer-brand-title"><Link className="footer-brand" to="/"><img src="/favicon.svg" alt=""/><span id="footer-brand-title">Ons Altın Analiz</span></Link><p>Canlı ons altın verilerini, ekonomik göstergeleri ve yapay zekâ destekli fiyat senaryolarını bir araya getiren bağımsız araştırma platformu.</p>
        <div className="footer-creator"><strong>Ali Doğan</strong><span>Projenin yaratıcısı ve geliştiricisi</span><a className="linkedin-link" href="https://www.linkedin.com/in/ali-do%C4%9Fan-86b57721a/" target="_blank" rel="noopener noreferrer me" aria-label="Ali Doğan LinkedIn profilini yeni sekmede aç"><i aria-hidden="true">in</i>LinkedIn</a></div>
      </section>
      <nav aria-label="Footer hızlı bağlantılar"><h2>Platform</h2><a href="/#panel">Canlı ons paneli</a><a href="/#feature-tahmin">Altın tahminleri</a><Link to="/rehber">Tüm altın rehberleri</Link><a href="/sitemap.xml">Site haritası</a></nav>
      {/* Güven sayfaları: YMYL kategorisinde her sayfadan erişilebilir olmalı. */}
      <nav aria-label="Site bilgileri"><h2>Site</h2><a href="/hakkimizda">Hakkımızda</a><a href="/yazar">Yazar ve metodoloji</a><a href="/iletisim">İletişim</a><a href="/gizlilik">Gizlilik</a></nav>
      <nav aria-label="Öne çıkan altın rehberleri"><h2>Araştırma</h2><Link to="/rehber/ons-altin-tahmini">Tahmin nasıl üretilir?</Link><Link to="/rehber/yapay-zeka-altin-tahmini">Model güvenilirliği</Link><Link to="/rehber/altin-fiyatini-etkileyen-faktorler">Piyasa parametreleri</Link><Link to="/rehber/ons-gram-altin-hesaplama">Ons / gram hesabı</Link></nav>
    </div>
    
    <div className="footer-bottom"><p>Bu platform eğitim ve araştırma amaçlıdır; yatırım danışmanlığı kapsamında değildir, getiri veya kâr garantisi sunmaz. <button type="button" className="link-btn" onClick={openLegal}>Yasal uyarının tamamı</button></p><span>© {new Date().getFullYear()} Ons Altın Analiz</span></div>
  </footer>;
}

export default SiteFooter;
