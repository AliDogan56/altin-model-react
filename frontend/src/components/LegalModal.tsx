import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { LEGAL_SECTIONS } from '../content/site';

const FOCUSABLE = 'a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])';

function LegalModal() {
  const [open,setOpen]=useState(false);
  const sheetRef=useRef<HTMLDivElement|null>(null);
  const opener=useRef<HTMLElement|null>(null);
  useEffect(()=>{const on=()=>{opener.current=document.activeElement as HTMLElement|null;setOpen(true);};
    window.addEventListener('legal:open',on);
    return()=>window.removeEventListener('legal:open',on);},[]);
  useEffect(()=>{
    if(!open) return;
    /* aria-modal="true" deniyordu ama odak yönetimi yoktu: açılışta odak sayfada
       kalıyor, Tab ile arkadaki içeriğe kaçılabiliyordu. */
    const sheet=sheetRef.current;
    const focusable=()=>Array.from(sheet?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    focusable()[0]?.focus();
    const onKey=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){setOpen(false);return;}
      if(event.key!=='Tab')return;
      const items=focusable();
      if(!items.length)return;
      const first=items[0], last=items[items.length-1];
      const active=document.activeElement;
      if(event.shiftKey&&(active===first||!sheet?.contains(active))){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&active===last){event.preventDefault();first.focus();}
    };
    document.addEventListener('keydown',onKey);
    const offset=window.scrollY, {style}=document.body;
    const previous={position:style.position,top:style.top,left:style.left,right:style.right,overflow:style.overflow};
    Object.assign(style,{position:'fixed',top:`-${offset}px`,left:'0',right:'0',overflow:'hidden'});
    return()=>{document.removeEventListener('keydown',onKey);Object.assign(style,previous);
      window.scrollTo(0,offset);opener.current?.focus();};
  },[open]);
  if(!open) return null;
  return createPortal(
    <div className="legal-modal" role="dialog" aria-modal="true" aria-labelledby="legal-modal-title">
      <div className="legal-backdrop" onClick={()=>setOpen(false)}/>
      <div className="legal-sheet" ref={sheetRef}>
        <header><h2 id="legal-modal-title">Yasal uyarı ve sorumluluk reddi</h2>
          <button type="button" onClick={()=>setOpen(false)} aria-label="Kapat">✕</button></header>
        <div className="legal-body">
          {LEGAL_SECTIONS.map(([title,text])=><section key={title}><h3>{title}</h3><p>{text}</p></section>)}
        </div>
        <footer><button type="button" className="primary" onClick={()=>setOpen(false)}>Okudum, kapat</button></footer>
      </div>
    </div>, document.body);
}

export default LegalModal;
