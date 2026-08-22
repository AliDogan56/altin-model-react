import { Link } from 'react-router-dom';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { GUIDES_BY_CATEGORY } from '../content/articles';
import type { SeoArticle } from '../content/types';
import { PANEL_FEATURES } from '../content/panel';
import { NAV_SECTIONS, fold } from '../content/site';
import ThemeToggle from './ThemeToggle';

function SiteNav({current}:{current?:string}) {
  const [menu,setMenu]=useState<null|'guides'|'panel'|'mobile'>(null);
  const [query,setQuery]=useState('');
  const navRef=useRef<HTMLElement>(null);
  const sheetRef=useRef<HTMLDivElement>(null);
  const searchRef=useRef<HTMLInputElement>(null);
  const close=useCallback(()=>{setMenu(null);setQuery('');},[]);

  // Açık menü dışına tıklama ve Escape ile kapanma. <details> bunu yapamadığı için
  // menü mobilde açık kalıyor, kullanıcı sayfaya dönmek için tekrar butona basmak zorundaydı.
  useEffect(()=>{
    if(!menu) return;
    const onPointer=(event:PointerEvent)=>{const target=event.target as Node;
      if(navRef.current?.contains(target)||sheetRef.current?.contains(target))return;
      close();};
    const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape')close();};
    document.addEventListener('pointerdown',onPointer);
    document.addEventListener('keydown',onKey);
    return()=>{document.removeEventListener('pointerdown',onPointer);document.removeEventListener('keydown',onKey);};
  },[menu,close]);
  // iOS Safari'de body'ye overflow:hidden vermek kaydırmayı durdurmaz; arka plan
  // sayfa panelin altında kaymaya devam eder. Konumu sabitleyip geri yüklüyoruz.
  useEffect(()=>{
    if(menu!=='mobile') return;
    const offset=window.scrollY;
    const {style}=document.body;
    const previous={position:style.position,top:style.top,left:style.left,right:style.right,overflow:style.overflow};
    Object.assign(style,{position:'fixed',top:`-${offset}px`,left:'0',right:'0',overflow:'hidden'});
    document.body.classList.add('nav-locked');
    return()=>{
      Object.assign(style,previous);
      document.body.classList.remove('nav-locked');
      window.scrollTo(0,offset);
    };
  },[menu]);
  useEffect(()=>{
    if(menu!=='guides') return;
    searchRef.current?.focus();
    // Açık rehber listenin altında kalabiliyor; kullanıcı nerede olduğunu görebilsin.
    document.querySelector('#guide-panel a.active')?.scrollIntoView({block:'center'});
  },[menu]);

  const groups=useMemo(()=>{
    const needle=fold(query.trim());
    if(!needle) return GUIDES_BY_CATEGORY;
    return GUIDES_BY_CATEGORY
      .map(([category,items])=>[category,items.filter(article=>fold(`${article.title} ${article.keyword}`).includes(needle))] as [string,SeoArticle[]])
      .filter(([,items])=>items.length>0);
  },[query]);
  const hitCount=groups.reduce((total,[,items])=>total+items.length,0);

  const guideLink=(article:SeoArticle)=>
    <Link key={article.id} to={`/rehber/${article.id}`} onClick={close}
       aria-current={current===article.id?'page':undefined}
       className={current===article.id?'active':undefined}>{article.title}</Link>;

  return <nav className="site-nav" aria-label="Ana menü" ref={navRef}>
    <a className="skip-link" href="#icerik">İçeriğe geç</a>
    <Link className="brand" to="/" aria-label="Ons Altın Analiz ana sayfa"><img src="/favicon.svg" alt=""/><span>Ons Altın Analiz</span></Link>

    <div className="desktop-links">
      {NAV_SECTIONS.map(([href,label])=><Link key={href} to={href}>{label}</Link>)}
      <div className="guide-menu">
        <button type="button" aria-expanded={menu==='panel'} aria-haspopup="true" aria-controls="panel-menu"
                className={menu==='panel'?'open':undefined}
                onClick={()=>setMenu(value=>value==='panel'?null:'panel')}>
          Panel <span aria-hidden="true">⌄</span>
        </button>
        {menu==='panel'&&<div className="guide-panel narrow" id="panel-menu">
          <div className="guide-groups single">
            <section>{PANEL_FEATURES.map(feature=>
              <Link key={feature.slug} to={`/panel/${feature.slug}`} onClick={close}
                 aria-current={current===feature.slug?'page':undefined}
                 className={current===feature.slug?'active':undefined}>{feature.title}</Link>)}</section>
          </div>
        </div>}
      </div>
      <div className="guide-menu">
        <button type="button" aria-expanded={menu==='guides'} aria-haspopup="true" aria-controls="guide-panel"
                className={menu==='guides'||current?'open':undefined}
                onClick={()=>setMenu(value=>value==='guides'?null:'guides')}>
          Altın Rehberi <span aria-hidden="true">⌄</span>
        </button>
        {menu==='guides'&&<div className="guide-panel" id="guide-panel">
          <div className="guide-search">
            <input ref={searchRef} type="search" value={query} placeholder="Rehberlerde ara…"
                   aria-label="Rehberlerde ara" onChange={event=>setQuery(event.target.value)}/>
            <small>{hitCount} rehber</small>
          </div>
          <div className="guide-groups">
            {groups.map(([category,items])=><section key={category}><h3>{category}</h3>{items.map(guideLink)}</section>)}
            {groups.length===0&&<p className="guide-empty">Eşleşen rehber yok.</p>}
          </div>
          <Link className="guide-all" to="/rehber" onClick={close}>Tüm rehberleri gör <span aria-hidden="true">→</span></Link>
        </div>}
      </div>
      <ThemeToggle/>
    </div>

    <button type="button" className="mobile-toggle" aria-expanded={menu==='mobile'} aria-controls="mobile-panel"
            aria-label={menu==='mobile'?'Menüyü kapat':'Menüyü aç'}
            onClick={()=>setMenu(value=>value==='mobile'?null:'mobile')}>
      <span/><span/><span/>
    </button>
    {menu==='mobile'&&createPortal(
      /* Portal şart: .site-nav üzerindeki backdrop-filter, position:fixed alt öğeler için
         içeren blok yaratıyor ve panel navbar'ın içine hapsolup 1 piksele çöküyordu. */
      <div className="mobile-sheet" ref={sheetRef}>
        <div className="mobile-backdrop" onClick={close} aria-hidden="true"/>
        <div className="mobile-panel" id="mobile-panel" role="dialog" aria-modal="true" aria-label="Menü">
          <div className="mobile-head">
            <input type="search" value={query} placeholder="Rehberlerde ara…" aria-label="Rehberlerde ara"
                   onChange={event=>setQuery(event.target.value)}/>
            <ThemeToggle compact/>
            <button type="button" onClick={close} aria-label="Menüyü kapat">✕</button>
          </div>
          <div className="mobile-scroll">
            {!query&&<section className="mobile-sections">{NAV_SECTIONS.map(([href,label])=>
              <Link key={href} to={href} onClick={close}>{label}</Link>)}
              <Link to="/rehber" onClick={close}>Tüm rehberler</Link>
        </section>}
        {!query&&<section className="mobile-sections"><h3>Panel bölümleri</h3>
          {PANEL_FEATURES.map(feature=><Link key={feature.slug} to={`/panel/${feature.slug}`} onClick={close}>{feature.title}</Link>)}
            </section>}
            {groups.map(([category,items])=><section key={category}><h3>{category}</h3>{items.map(guideLink)}</section>)}
            {groups.length===0&&<p className="guide-empty">Eşleşen rehber yok.</p>}
          </div>
        </div>
      </div>, document.body)}
  </nav>;
}

export default SiteNav;
