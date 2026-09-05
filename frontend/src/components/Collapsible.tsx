import { createContext, useContext, useEffect, useState } from 'react';
import type React from 'react';

export const AnalysisPresentation = createContext<'collapsible' | 'section'>('collapsible');

/** Yan özellik kabı. Kapalıyken bile "özet" alanında tek bir canlı değer gösterir;
 *  böylece bilgi gizlenmiş olmaz, yalnız yer kaplamaz. */
function Collapsible({title,hint,summary,children,id,anchor,openByDefault}:{title:string;hint?:string;summary?:React.ReactNode;children:React.ReactNode;id:string;anchor?:string;openByDefault?:boolean}) {
  const [open,setOpen]=useState(!!openByDefault);
  const presentation = useContext(AnalysisPresentation);
  useEffect(()=>{if(openByDefault)setOpen(true);},[openByDefault]);
  if (presentation === 'section') return <section id={anchor} className="panel analysis-section" aria-labelledby={`${id}-heading`}>
    <div className="analysis-section-head"><div><h2 id={`${id}-heading`}>{title}</h2>{hint && <p>{hint}</p>}</div>
      {summary != null && <span className="analysis-section-summary">{summary}</span>}</div>
    <div className="analysis-section-body">{children}</div>
  </section>;
  return <section id={anchor} className={`panel block collapsible ${open?'is-open':''}`}>
    <button type="button" className="collapsible-head" aria-expanded={open} aria-controls={`${id}-body`}
            onClick={()=>setOpen(value=>!value)}>
      <span className="collapsible-title"><b>{title}</b>{hint&&<small>{hint}</small>}</span>
      {summary!=null&&<span className="collapsible-summary">{summary}</span>}
      <span className="collapsible-chevron" aria-hidden="true">⌄</span>
    </button>
    {open&&<div className="collapsible-body reveal" id={`${id}-body`}>{children}</div>}
  </section>;
}

export default Collapsible;
