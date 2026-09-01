import type { PanelFeature } from '../../content/types';

/**
 * Panel sayfasının kendi anlatısı, canlı panonun üstünde.
 *
 * `/panel/<slug>` React'te panonun kendisini render eder; ön render edilen metin
 * hidrasyonda kaybolur. Bu yüzden 11 panel URL'i Google'a birebir aynı sayfa
 * gibi görünüyordu ve hiçbiri dizine girmemişti. Bu blok ön render ile
 * uygulamanın **aynı** şeyi göstermesini sağlar: başlık, özet ve panele özgü
 * bölümler her iki tarafta da durur.
 */
function PanelIntro({ feature }: { feature: PanelFeature }) {
  if (!feature.sections?.length) return null;
  return (
    <section className="panel-intro" aria-labelledby="panel-intro-baslik">
      <header>
        <span className="eyebrow">Panel bölümü</span>
        <h1 id="panel-intro-baslik">{feature.title}</h1>
        <p className="panel-intro-lede">{feature.summary}</p>
      </header>
      {/* Atlama bağlantısı metnin **başında**: bu sayfaya panoyu kullanmaya
          gelen okuyucu 1500 piksel metin kaydırmak zorunda kalmasın. */}
      <p className="panel-intro-jump"><a href="#panel">Canlı hesaba geç ↓</a></p>
      <p>{feature.intro}</p>
      {feature.sections.map(section => (
        <section key={section.heading}>
          <h2>{section.heading}</h2>
          {section.paragraphs.map(text => <p key={text}>{text}</p>)}
          {section.list && (section.list.ordered
            ? <ol className="article-list">{section.list.items.map(i => <li key={i}>{i}</li>)}</ol>
            : <ul className="article-list">{section.list.items.map(i => <li key={i}>{i}</li>)}</ul>)}
          {section.table && <div className="article-table-wrap">
            <table className="article-table">
              <caption>{section.table.caption}</caption>
              <thead><tr>{section.table.columns.map(c => <th key={c} scope="col">{c}</th>)}</tr></thead>
              <tbody>{section.table.rows.map((row, i) => <tr key={i}>{row.map((cell, j) =>
                j === 0 ? <th key={j} scope="row">{cell}</th> : <td key={j}>{cell}</td>)}</tr>)}</tbody>
            </table></div>}
        </section>
      ))}
    </section>
  );
}

export default PanelIntro;
