import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { LEGAL_SECTIONS } from '../content/site';

function LegalModal() {
  const [open,setOpen]=useState(false);
  useEffect(()=>{const on=()=>setOpen(true);window.addEventListener('legal:open',on);
    return()=>window.removeEventListener('legal:open',on);},[]);
  useEffect(()=>{
    if(!open) return;
    const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape')setOpen(false);};
    document.addEventListener('keydown',onKey);
    const offset=window.scrollY, {style}=document.body;
    const previous={position:style.position,top:style.top,left:style.left,right:style.right,overflow:style.overflow};
    Object.assign(style,{position:'fixed',top:`-${offset}px`,left:'0',right:'0',overflow:'hidden'});
    return()=>{document.removeEventListener('keydown',onKey);Object.assign(style,previous);window.scrollTo(0,offset);};
  },[open]);
  if(!open) return null;
  return createPortal(
    <div className="legal-modal" role="dialog" aria-modal="true" aria-labelledby="legal-modal-title">
      <div className="legal-backdrop" onClick={()=>setOpen(false)}/>
      <div className="legal-sheet">
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
