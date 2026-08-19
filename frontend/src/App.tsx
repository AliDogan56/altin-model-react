import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { io } from 'socket.io-client';
import model from './data/model.json';
import seoArticles from './data/seo-articles.json';

const SEO_ARTICLES = seoArticles as SeoArticle[];

type SeoSection = { heading: string; paragraphs: string[] };
type SeoFaq = { q: string; a: string };
type SeoArticle = { id: string; keyword: string; title: string; seoTitle?: string; updated: string; summary: string; intro: string; category: string; sections: SeoSection[]; points: string[]; faq: SeoFaq[] };
type ParameterItem = [id: string, label: string, unit: string];
type ParameterGroup = [title: string, items: ParameterItem[]];

const GROUPS: ParameterGroup[] = [
  ['Fiyat ve teknik', [['price','Ons fiyatı','USD'],['gold_rsi14','RSI (14)',''],['gold_atr14_pct','ATR (14)','%'],['gold_return_20d','20 günlük momentum','%'],['gold_volatility_20d','20 günlük oynaklık','%']]],
  ['Faiz ve dolar', [['DGS10','ABD 10Y faiz','%'],['DGS2','ABD 2Y faiz','%'],['DFII10','10Y reel faiz','%'],['DTWEXBGS','Dolar endeksi',''],['FEDFUNDS','Fed fon faizi','%']]],
  ['Risk ve emtia', [['VIXCLS','VIX',''],['DCOILWTICO','WTI petrol','USD']]],
  ['Makroekonomi', [['CPIAUCSL_yoy_pct','TÜFE yıllık','%'],['CPILFESL_yoy_pct','Çekirdek TÜFE','%'],['PCEPI_yoy_pct','PCE yıllık','%'],['UNRATE','İşsizlik','%'],['RSAFS_mom_pct','Perakende satış aylık','%']]],
];
const API_BASE=(import.meta.env.VITE_API_BASE||'http://{host}:8000').replace('{origin}',window.location.origin).replace('{host}',window.location.hostname).replace(/\/$/,'');
const MARKET_API=`${API_BASE}/market-service`;
const MODEL_API=`${API_BASE}/model-service`;
const LABELS = {7:'1 Hafta',30:'1 Ay',90:'3 Ay',180:'6 Ay'};
/** Harem Altın socket kod -> etiket. Kotasyonlar doğrudan piyasadan gelir;
 *  ons üzerinden hesaplanan ham madde değeri işçilik ve marjı içermiyordu. */
const ZIYNET: [string,string][] = [['ALTIN','Gram altın'],['AYAR22','22 ayar gram'],['CEYREK_YENI','Çeyrek (yeni)'],['YARIM_YENI','Yarım (yeni)'],['TEK_YENI','Tam (yeni)'],['ATA_YENI','Yeni Ata']];
const BAND_COVERAGE=70,BAND_SCALE=.81;
const PCT_FIELDS = new Set(['gold_atr14_pct','gold_return_20d','gold_volatility_20d']);
const avg = a => a.reduce((s,v)=>s+v,0)/a.length;
const std = a => { const m=avg(a); return Math.sqrt(avg(a.map(v=>(v-m)**2))); };
const matVec=(x,w)=>w[0].map((_,j)=>x.reduce((s,v,i)=>s+v*w[i][j],0));
const add=(a,b)=>a.map((v,i)=>v+b[i]);
const relu=a=>a.map(v=>Math.max(0,v));
const forward=(x,m)=>{const a1=relu(add(matVec(x,m.w1),m.b1));const a2=relu(add(matVec(a1,m.w2),m.b2));return add(matVec(a2,m.w3),m.b3).map((v,i)=>v*model.yStd[i]+model.yMean[i]);};
const money=v=>new Intl.NumberFormat('tr-TR',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(v);
const money2=v=>new Intl.NumberFormat('tr-TR',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}).format(v);
const tryMoney=v=>new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY',maximumFractionDigits:0}).format(v);
const tryAmount=v=>new Intl.NumberFormat('tr-TR',{maximumFractionDigits:0}).format(Math.max(0,Number(v)||0));
const pct=v=>new Intl.NumberFormat('tr-TR',{style:'percent',minimumFractionDigits:1,maximumFractionDigits:1}).format(v);
/** Hata metrikleri binde mertebesinde; tek ondalık iki farklı sayıyı aynı gösteriyordu. */
const pct2=v=>new Intl.NumberFormat('tr-TR',{style:'percent',minimumFractionDigits:2,maximumFractionDigits:2}).format(v);
const signedPct2=v=>`${v>=0?'+':''}${new Intl.NumberFormat('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v*100)}%`;
const fieldDefaults = () => Object.fromEntries(GROUPS.flatMap(([,items])=>items).map(([id])=>[id,id==='price'?model.latestPrice:model.latest[id]*(PCT_FIELDS.has(id)?100:1)]));
const parseCsv = text => text.trim().split(/\r?\n/).slice(1).map(line=>{const [date,value]=line.split(',');return{date,value:+value};}).filter(x=>Number.isFinite(x.value));
const fetchJson = async url => { const r=await fetch(url); if(!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); };

/* ---- Teknik göstergeler ----
   Hepsi zaten çekilen günlük OHLC mumlarından hesaplanır, yeni veri kaynağı gerekmez.
   Bilinçli olarak "al/sat" kararı üretilmez; yalnız göstergenin bulunduğu durum yazılır. */
const sma=(a,n,i=a.length-1)=>i+1<n?null:a.slice(i+1-n,i+1).reduce((s,v)=>s+v,0)/n;
const emaSeries=(a,n)=>{const k=2/(n+1);const out=[];let prev=null;
  a.forEach((v,i)=>{prev=i===0?v:v*k+prev*(1-k);out.push(i+1<n?null:prev);});return out;};
const wilder=(a,n)=>{const out=new Array(a.length).fill(null);if(a.length<n)return out;
  let acc=a.slice(0,n).reduce((s,v)=>s+v,0);out[n-1]=acc;
  for(let i=n;i<a.length;i++){acc=acc-acc/n+a[i];out[i]=acc;}return out;};

function indicators(candles){
  if(!candles||candles.length<210) return null;
  const c=candles.map(x=>x.c),h=candles.map(x=>x.h),l=candles.map(x=>x.l),last=c.length-1;
  const diff=c.slice(1).map((v,i)=>v-c[i]);
  const rsiN=14, gains=diff.slice(-rsiN).map(v=>Math.max(0,v)), losses=diff.slice(-rsiN).map(v=>Math.max(0,-v));
  const avgG=gains.reduce((s,v)=>s+v,0)/rsiN, avgL=losses.reduce((s,v)=>s+v,0)/rsiN;
  const rsi=100-100/(1+avgG/(avgL||1e-9));

  const e12=emaSeries(c,12), e26=emaSeries(c,26);
  const macdLine=c.map((_,i)=>e12[i]!=null&&e26[i]!=null?e12[i]-e26[i]:null);
  const macdVals=macdLine.filter(v=>v!=null);
  const sig=emaSeries(macdVals,9);
  const macd=macdLine[last], signal=sig[sig.length-1], hist=macd!=null&&signal!=null?macd-signal:null;

  const hh=Math.max(...h.slice(-14)), ll=Math.min(...l.slice(-14));
  const stochK=hh===ll?50:(c[last]-ll)/(hh-ll)*100;
  const kSeries=[];
  for(let i=Math.max(13,last-4);i<=last;i++){
    const H=Math.max(...h.slice(i-13,i+1)),L=Math.min(...l.slice(i-13,i+1));
    kSeries.push(H===L?50:(c[i]-L)/(H-L)*100);}
  const stochD=kSeries.slice(-3).reduce((s,v)=>s+v,0)/Math.min(3,kSeries.length);
  const williams=hh===ll?-50:(hh-c[last])/(hh-ll)*-100;

  const tp=c.map((_,i)=>(h[i]+l[i]+c[i])/3);
  const tpMean=sma(tp,20), dev=tp.slice(-20).reduce((s,v)=>s+Math.abs(v-tpMean),0)/20;
  const cci=dev?(tp[last]-tpMean)/(0.015*dev):0;

  const tr=[],plusDM=[],minusDM=[];
  for(let i=1;i<c.length;i++){
    tr.push(Math.max(h[i]-l[i],Math.abs(h[i]-c[i-1]),Math.abs(l[i]-c[i-1])));
    const up=h[i]-h[i-1], down=l[i-1]-l[i];
    plusDM.push(up>down&&up>0?up:0); minusDM.push(down>up&&down>0?down:0);}
  const n=14, trS=wilder(tr,n), pS=wilder(plusDM,n), mS=wilder(minusDM,n), dx=[];
  for(let i=n-1;i<tr.length;i++){
    if(!trS[i]) continue;
    const pdi=100*pS[i]/trS[i], mdi=100*mS[i]/trS[i], sum=pdi+mdi;
    dx.push(sum?100*Math.abs(pdi-mdi)/sum:0);}
  const adx=dx.length>=n?dx.slice(-n).reduce((s,v)=>s+v,0)/n:null;
  const pdiNow=trS[tr.length-1]?100*pS[tr.length-1]/trS[tr.length-1]:0;
  const mdiNow=trS[tr.length-1]?100*mS[tr.length-1]/trS[tr.length-1]:0;

  const atr=tr.slice(-14).reduce((s,v)=>s+v,0)/14, atrPct=atr/c[last]*100;
  const atrHist=[];
  for(let i=14;i<tr.length;i++) atrHist.push(tr.slice(i-14,i).reduce((s,v)=>s+v,0)/14/c[i]*100);
  const atrMed=[...atrHist].sort((a,b)=>a-b)[Math.floor(atrHist.length/2)]||atrPct;
  const roc=c[last-12]?(c[last]/c[last-12]-1)*100:0;

  const state=(text,tone)=>({text,tone});   // value döndürmüyor: yayılma sırasında gerçek değeri eziyordu
  return {
    rows:[
      {name:'RSI (14)',value:rsi.toFixed(1),
       ...(rsi>=70?state('Aşırı alım','warn'):rsi<=30?state('Aşırı satım','warn'):state('Nötr bölge','flat')),note:''},
      {name:'Stochastic %K (14)',value:stochK.toFixed(1),
       ...(stochK>=80?state('Aşırı alım','warn'):stochK<=20?state('Aşırı satım','warn'):state('Nötr bölge','flat')),
       note:`%D ${stochD.toFixed(1)}`},
      {name:'Williams %R (14)',value:williams.toFixed(1),
       ...(williams>=-20?state('Aşırı alım','warn'):williams<=-80?state('Aşırı satım','warn'):state('Nötr bölge','flat')),note:''},
      {name:'CCI (20)',value:cci.toFixed(0),
       ...(cci>=100?state('Aşırı alım','warn'):cci<=-100?state('Aşırı satım','warn'):state('Nötr bölge','flat')),note:''},
      {name:'MACD (12,26,9)',value:macd!=null?macd.toFixed(1):'—',
       ...(hist==null?state('—','flat'):hist>=0?state('Sinyalin üstünde','up'):state('Sinyalin altında','down')),
       note:signal!=null?`Sinyal ${signal.toFixed(1)}`:''},
      {name:'ADX (14)',value:adx!=null?adx.toFixed(1):'—',
       ...(adx==null?state('—','flat'):adx>=25?state('Güçlü trend','up'):adx>=20?state('Trend güçleniyor','flat'):state('Yönsüz / yatay','flat')),
       note:`+DI ${pdiNow.toFixed(0)} · −DI ${mdiNow.toFixed(0)}`},
      {name:'ATR (14)',value:`%${atrPct.toFixed(2)}`,
       ...(atrPct>=atrMed*1.3?state('Yüksek oynaklık','warn'):atrPct<=atrMed*0.7?state('Düşük oynaklık','flat'):state('Normal oynaklık','flat')),
       note:`Medyan %${atrMed.toFixed(2)}`},
      {name:'ROC (12)',value:`%${roc.toFixed(2)}`,
       ...(roc>=0?state('12 gün önceye göre yukarıda','up'):state('12 gün önceye göre aşağıda','down')),note:''},
    ],
    averages:[5,10,20,50,100,200].map(n=>({n,
      sma:sma(c,n), ema:emaSeries(c,n)[last], price:c[last]})).filter(x=>x.sma!=null),
  };
}

function computeFeatures(values, live) {
  const f={...model.latest,...live};
  Object.entries(values).forEach(([k,v])=>{if(k!=='price')f[k]=PCT_FIELDS.has(k)?+v/100:+v;});
  f.yield_curve_10y_2y=f.DGS10-f.DGS2;
  f.breakeven_inflation_10y=f.DGS10-f.DFII10;
  return f;
}

function predict(features, price) {
  const x=model.features.map((k,i)=>Math.max(-6,Math.min(6,(features[k]-model.xMean[i])/model.xStd[i])));
  const all=model.models.map(m=>forward(x,m));
  const mean=model.horizons.map((_,j)=>avg(all.map(p=>p[j])));
  const err=model.residual80.map((r,j)=>Math.max(r,std(all.map(p=>p[j]))*1.64)*BAND_SCALE);
  return {features,price:+price,mean,err};
}

/** Tahmin yolu, geçmiş serisinin bittiği günden başlar. Tarihleri `new Date()` ile
 *  üretmek, geçmiş bir sebeple geride kaldığında takvimde boşluk gösteriyordu
 *  (geçmiş 14'te bitip tahmin 19'dan başlaması gibi). */
function buildDailyPath(forecast,horizonDays,startDate=null) {
  const anchors=[{day:0,ret:0,err:0},...model.horizons.map((day,j)=>({day,ret:forecast.mean[j],err:forecast.err[j]}))];
  return Array.from({length:horizonDays+1},(_,day)=>{
    const right=anchors.find(a=>a.day>=day)||anchors.at(-1),ri=anchors.indexOf(right),left=anchors[Math.max(0,ri-1)],t=right.day===left.day?0:(day-left.day)/(right.day-left.day);
    const ret=Math.expm1(Math.log1p(Math.max(-.95,left.ret))*(1-t)+Math.log1p(Math.max(-.95,right.ret))*t);
    const err=left.err*(1-t)+right.err*t;
    const date=startDate?new Date(`${startDate}T00:00:00Z`):new Date();
    if(startDate)date.setUTCDate(date.getUTCDate()+day);else date.setDate(date.getDate()+day);
    return{day,date:date.toISOString().slice(0,10),v:forecast.price*(1+ret),lo:forecast.price*(1+ret-err),hi:forecast.price*(1+ret+err),ret,err,kind:'Günlükleştirilmiş tahmin'};
  });
}

function breakEvenLoanRate(totalReturn,months) {
  if(!Number.isFinite(totalReturn)||totalReturn<=0)return null;
  const target=1+totalReturn,totalRatio=rate=>rate===0?1:months*(rate*(1+rate)**months/((1+rate)**months-1));
  let lo=0,hi=1;
  if(totalRatio(hi)<target)return hi;
  for(let i=0;i<80;i++){const mid=(lo+hi)/2;if(totalRatio(mid)<target)lo=mid;else hi=mid;}
  return (lo+hi)/2;
}

function loanPayment(principal,monthlyRate,months) {
  const rate=Math.max(0,monthlyRate);
  return rate===0?principal/months:principal*(rate*(1+rate)**months/((1+rate)**months-1));
}

function tryRate(value) {
  return new Intl.NumberFormat('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:4}).format(Number(value)||0);
}

function loanProjection(forecast,months) {
  const days=months*30,path=buildDailyPath(forecast,Math.min(days,180)),last=path.at(-1);
  let mean=last.ret,err=last.err,derived=false;
  if(days>180){const scale=days/180;mean=Math.expm1(Math.log1p(Math.max(-.95,mean))*scale);err*=Math.sqrt(scale);derived=true;}
  const scenarios=[{label:'Alt bant',ret:mean-err,tone:'low'},{label:'Model tahmini',ret:mean,tone:'base'},{label:'Üst bant',ret:mean+err,tone:'high'}].map(s=>({...s,monthly:breakEvenLoanRate(s.ret,months)}));
  return{months,derived,scenarios};
}

function ForecastChart({forecast,history,rangeDays,horizonDays,showBand,showLevels,showOrigin,showSR,originForecast,onToggle,levels,spot,tokenSpot,mobile}) {
  const W=mobile?420:1600,H=mobile?620:650,m={l:mobile?34:58,r:mobile?96:104,t:mobile?16:20,b:mobile?40:48};
  const [hover,setHover]=useState(null), svgRef=useRef(null);
  const [zoom,setZoom]=useState(1),[panDays,setPanDays]=useState(0);
  const shown=history.slice(-rangeDays), hist=shown.map((d,i)=>({i:i-(shown.length-1),v:d[1],date:d[0],kind:'Geçmiş'}));
  const lastHistoryDate=hist.length?hist[hist.length-1].date:undefined;
  /* Vadesi gelmiş tahmin günleri için gerçekleşen kapanış; ipucu kutusunda gösterilir. */
  const actualByDate=new Map<string,number>(history.map(([date,value])=>[String(date),Number(value)]));
  const daily=buildDailyPath(forecast,horizonDays,lastHistoryDate),future=daily.map(d=>({...d,i:d.day,label:d.day===0?'Bugün':`${d.day}. gün`}));
  const anchorDays=[0,30,90,180].filter(d=>d<=horizonDays),futureAnchors=anchorDays.map(day=>future[day]);
  /* Modelin ilk yayınladığı tahmin (model.latestDate), o günkü girdilerle hesaplanıp
     geçmişe oturtulur. Canlı tahmin çizgisine dokunmaz; amacı vadesi gelmiş günlerde
     tahminin gerçekleşenle karşılaştırılabilmesidir. */
  /* Destek/direnç: görünen geçmişteki dönüş noktaları (pivot) bulunur, birbirine yakın
     olanlar tek seviyede kümelenir ve en çok dokunulan dördü çizilir. Fiyatın üstünde
     kalanlar direnç, altında kalanlar destektir. */
  const srLevels=useMemo(()=>{
    const k=3;                                   // gercek veriyle ayarlandi: k=5 tek dokunusluk pivot uretiyordu
    if(hist.length<2*k+4) return [];
    const values=hist.map(d=>d.v), span=Math.max(...values)-Math.min(...values);
    const tolerance=(span||1)*.055, pivots=[];   // gorunen araligin %5,5'i ~ fiyatin %1,3'u
    for(let i=k;i<hist.length-k;i++){
      const window=values.slice(i-k,i+k+1);
      if(values[i]===Math.max(...window)||values[i]===Math.min(...window)) pivots.push(values[i]);
    }
    const clusters=[];
    pivots.sort((a,b)=>a-b).forEach(value=>{
      const last=clusters[clusters.length-1];
      if(last&&value-last.price<=tolerance){last.hits.push(value);last.price=last.hits.reduce((s,v)=>s+v,0)/last.hits.length;}
      else clusters.push({price:value,hits:[value]});
    });
    return clusters.filter(c=>c.hits.length>=2).sort((a,b)=>b.hits.length-a.hits.length).slice(0,4)
      .map(c=>({price:c.price,touches:c.hits.length}));
  },[hist]);
  const originAt=hist.find(d=>d.date===model.latestDate);
  const originPath=showOrigin&&originAt?buildDailyPath({...originForecast,price:model.latestPrice},horizonDays,model.latestDate)
    .map(d=>({...d,i:originAt.i+d.day,kind:`${model.latestDate} tahmini`})):null;
  const originPast=originPath?originPath.filter(d=>d.i<0):[];
  const resistance=Math.max(model.resistance.r20,model.resistance.r60)*(forecast.price/model.latestPrice)*(1+model.resistance.momentumJumpPct);
  const startI=-(shown.length-1),endI=horizonDays,totalSpan=endI-startI,visibleSpan=totalSpan/zoom,baseCenter=(startI+endI)/2;
  const center=Math.max(startI+visibleSpan/2,Math.min(endI-visibleSpan/2,baseCenter+panDays)),visibleStart=center-visibleSpan/2,visibleEnd=center+visibleSpan/2;
  const levelVals=showLevels?[...levels.buy,...levels.sell,levels.stop]:[];
  const vals=[...hist.map(d=>d.v),...future.flatMap(d=>showBand?[d.lo,d.hi]:[d.v]),...(originPath?originPath.flatMap(d=>[d.lo,d.hi]):[]),...(showSR?srLevels.map(l=>l.price):[]),resistance,spot.price,tokenSpot.price,...levelVals];let ymin=Math.min(...vals),ymax=Math.max(...vals);const pad=(ymax-ymin)*.08;ymin-=pad;ymax+=pad;
  const x=i=>m.l+(i-visibleStart)/(visibleEnd-visibleStart)*(W-m.l-m.r), y=v=>m.t+(ymax-v)/(ymax-ymin)*(H-m.t-m.b), points=a=>a.map(d=>`${x(d.i)},${y(d.v)}`).join(' ');
  const upper=future.map(d=>`${x(d.i)},${y(d.hi)}`).join(' '),lower=[...future].reverse().map(d=>`${x(d.i)},${y(d.lo)}`).join(' ');
  const allPoints=[...originPast,...hist,...future];
  const onMove=e=>{const rect=svgRef.current.getBoundingClientRect(),px=(e.clientX-rect.left)/rect.width*W,day=visibleStart+(px-m.l)/(W-m.l-m.r)*(visibleEnd-visibleStart);setHover(allPoints.reduce((a,b)=>Math.abs(b.i-day)<Math.abs(a.i-day)?b:a));};
  const zone=(a,b,cls)=><rect className={cls} x={m.l} y={y(Math.max(a,b))} width={W-m.l-m.r} height={Math.max(2,Math.abs(y(a)-y(b)))}/>;
  const changeZoom=next=>{const z=Math.max(1,Math.min(6,next));setZoom(z);if(z===1)setPanDays(0);};
  return <div className="chart-wrap"><div className="zoom-controls"><span>Yakınlaştırma {zoom.toFixed(1)}×</span><button onClick={()=>setPanDays(v=>v-visibleSpan*.22)} disabled={zoom===1}>←</button><button onClick={()=>changeZoom(zoom/1.5)} disabled={zoom===1}>−</button><button onClick={()=>changeZoom(zoom*1.5)} disabled={zoom>=6}>+</button><button onClick={()=>setPanDays(v=>v+visibleSpan*.22)} disabled={zoom===1}>→</button><button onClick={()=>{setZoom(1);setPanDays(0)}} disabled={zoom===1}>Sıfırla</button></div><svg ref={svgRef} className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Altın fiyat tahmin grafiği" onPointerMove={onMove} onPointerLeave={()=>setHover(null)} onPointerCancel={()=>setHover(null)} onPointerUp={e=>{if(e.pointerType!=='mouse')setHover(null);}} onWheel={e=>{if(!e.ctrlKey&&!e.metaKey)return;e.preventDefault();changeZoom(zoom*(e.deltaY<0?1.2:1/1.2));}}>
    {[0,1,2,3,4].map(k=>{const v=ymin+(ymax-ymin)*k/4;return <g key={k}><line className="gridline" x1={m.l} y1={y(v)} x2={W-m.r} y2={y(v)}/><text className="axis" x={m.l-8} y={y(v)+3} textAnchor="end">{Math.round(v).toLocaleString('tr-TR')}</text></g>})}
    {showSR&&srLevels.map(level=><g key={level.price} className={`sr ${level.price>=spot.price?'res':'sup'}`}><line x1={m.l} y1={y(level.price)} x2={x(0)} y2={y(level.price)}/><text x={x(0)-4} y={y(level.price)-4} textAnchor="end">{money(level.price)}{!mobile&&` · ${level.touches} dokunuş`}</text></g>)}
    <rect className="future-zone" x={Math.max(m.l,x(0))} y={m.t} width={Math.max(0,W-m.r-Math.max(m.l,x(0)))} height={H-m.t-m.b}/>
    <line className="today-divider" x1={x(0)} y1={m.t} x2={x(0)} y2={H-m.b}/>
    {!mobile&&<><text className="zone-caption" x={x(0)-8} y={m.t+13} textAnchor="end">gerçekleşen</text>
    <text className="zone-caption" x={x(0)+8} y={m.t+13}>tahmin</text></>}
    {showLevels&&<>{zone(levels.buy[0],levels.buy[1],'buy-zone')}{zone(levels.sell[0],levels.sell[1],'sell-zone')}<line className="stop-line" x1={m.l} y1={y(levels.stop)} x2={W-m.r} y2={y(levels.stop)}/><text className="stop-label" x={m.l+5} y={y(levels.stop)-5}>Risk kesme {money(levels.stop)}</text></>}
    {originPath&&<><polyline className="origin-forecast" points={points(originPath)}/><line className="origin-marker" x1={x(originAt.i)} y1={m.t} x2={x(originAt.i)} y2={H-m.b}/><text className="origin-label" x={x(originAt.i)+5} y={m.t+13}>{mobile?model.latestDate:`Model başlangıcı ${model.latestDate}`}</text></>}
    {showBand&&<polygon className="band" points={`${upper} ${lower}`}/>}<polyline className="history" points={points(hist)}/><polyline className="forecast" points={points(future)}/>
    <g className="price-now">
      <line className="now-line" x1={m.l} y1={y(spot.price)} x2={W-m.r} y2={y(spot.price)}/>
      <circle className="now-dot-ons" cx={x(0)} cy={y(spot.price)} r="6"/>
      <circle className="now-dot-token" cx={x(0)} cy={y(tokenSpot.price)} r="4"/>
      <g transform={`translate(${W-m.r+5} ${Math.min(H-m.b-44,Math.max(m.t,y(spot.price)-22))})`}>
        <rect className="now-card" width={mobile?86:96} height="44" rx="9"/>
        <text className="now-tag" x="7" y="13">ONS</text><text className="now-value" x={(mobile?86:96)-7} y="13" textAnchor="end">{money(spot.price)}</text>
        <text className="now-tag alt" x="7" y="33">PAXG</text><text className="now-value alt" x={(mobile?86:96)-7} y="33" textAnchor="end">{money(tokenSpot.price)}</text>
      </g>
    </g>
    {showLevels&&<><line className="resistance" x1={W-m.r-70} y1={y(resistance)} x2={W-m.r} y2={y(resistance)}/><text className="guide" x={W-m.r-74} y={y(resistance)+3} textAnchor="end">Momentum eşiği {money(resistance)}</text></>}
    {futureAnchors.map((d,i)=><g key={d.i}><circle cx={x(d.i)} cy={y(d.v)} r={i?5:4} className={i?'future-dot':'today-dot'}/><text className="axis" x={x(d.i)} y={H-15} textAnchor="middle">{d.i===0?'Bugün':LABELS[d.i]}</text></g>)}
    <text className="axis" x={m.l} y={H-15}>−{rangeDays} gün</text>{!mobile&&<text className="axis-title" transform={`translate(16 ${H/2}) rotate(-90)`} textAnchor="middle">USD / ons</text>}
    {hover&&(()=>{const isForecast=Number.isFinite(hover.lo)&&Number.isFinite(hover.hi),real=isForecast?actualByDate.get(hover.date):undefined,settled=real!=null,errorPct=settled?(hover.v-real)/real:null,boxW=isForecast?(mobile?186:232):(mobile?132:166),boxH=isForecast?(settled?134:92):48,boxX=Math.min(W-m.r-boxW-6,Math.max(m.l+5,x(hover.i)+12)),boxY=Math.min(H-m.b-boxH-6,Math.max(10,y(hover.v)-boxH/2));return <g className="crosshair"><line x1={x(hover.i)} y1={m.t} x2={x(hover.i)} y2={H-m.b}/>{isForecast&&showBand&&<><line className="band-range" x1={x(hover.i)} y1={y(hover.hi)} x2={x(hover.i)} y2={y(hover.lo)}/><circle className="band-max-dot" cx={x(hover.i)} cy={y(hover.hi)} r="4"/><circle className="band-min-dot" cx={x(hover.i)} cy={y(hover.lo)} r="4"/></>}<circle cx={x(hover.i)} cy={y(hover.v)} r="6"/><g className="hover-card" transform={`translate(${boxX} ${boxY})`}><rect width={boxW} height={boxH} rx="8"/><text x="11" y="19">{hover.date}</text>{isForecast?<><text x="11" y="40" className="tip-min">Olası minimum (%{BAND_COVERAGE})</text><text x={boxW-11} y="40" textAnchor="end" className="tip-value tip-min">{money(hover.lo)}</text><text x="11" y="61" className="tip-price">Sinir ağı tahmini</text><text x={boxW-11} y="61" textAnchor="end" className="tip-value tip-price">{money(hover.v)}</text><text x="11" y="82" className="tip-max">Olası maksimum (%{BAND_COVERAGE})</text><text x={boxW-11} y="82" textAnchor="end" className="tip-value tip-max">{money(hover.hi)}</text>{settled&&<><line className="tip-divider" x1="11" y1="95" x2={boxW-11} y2="95"/><text x="11" y="113" className="tip-real">Gerçekleşen</text><text x={boxW-11} y="113" textAnchor="end" className="tip-value tip-real">{money(real)}</text><text x="11" y="128" className="tip-error">Hata</text><text x={boxW-11} y="128" textAnchor="end" className={`tip-value ${Math.abs(errorPct)<=.01?'tip-error-ok':'tip-error-bad'}`}>{errorPct>=0?'+':''}{(errorPct*100).toFixed(2)}%</text></>}</>:<text x="10" y="37" className="tip-price">{hover.kind}: {money(hover.v)}</text>}</g></g>})()}
  </svg><div className="chart-legend"><span><i className="history-key"/>Gerçekleşen</span><span><i className="forecast-key"/>Model tahmini</span><button type="button" className={showBand?'on':'off'} aria-pressed={showBand} onClick={()=>onToggle('band')}><i className="band-key"/>%{BAND_COVERAGE} bant</button><button type="button" className={showOrigin?'on':'off'} aria-pressed={showOrigin} onClick={()=>onToggle('origin')}><i className="origin-key"/>{model.latestDate} tahmini</button><button type="button" className={showSR?'on':'off'} aria-pressed={showSR} onClick={()=>onToggle('sr')}><i className="sr-key"/>Destek / direnç</button><button type="button" className={showLevels?'on':'off'} aria-pressed={showLevels} onClick={()=>onToggle('levels')}><i className="buy-key"/>İşlem bölgeleri</button></div></div>;
}

function TickSparkline({ticks}) {
  if(ticks.length<2)return <div className="tick-empty">Saniyelik akış hazırlanıyor…</div>;
  const W=190,H=34,min=Math.min(...ticks.map(t=>t.price)),max=Math.max(...ticks.map(t=>t.price)),span=max-min||1;
  const pts=ticks.map((t,i)=>`${i/(ticks.length-1)*W},${H-3-(t.price-min)/span*(H-6)}`).join(' '),up=ticks.at(-1).price>=ticks[0].price;
  return <svg className={`tick-spark ${up?'up':'down'}`} viewBox={`0 0 ${W} ${H}`} aria-label="Son saniyelerde ons fiyat hareketi"><polyline points={pts}/></svg>;
}

const NAV_SECTIONS = [['/#panel','Canlı Panel'],['/#tahmin','Tahmin']] as [string,string][];
const CATEGORY_ORDER = [...new Set(SEO_ARTICLES.map(article=>article.category))];
const GUIDES_BY_CATEGORY = CATEGORY_ORDER.map(category=>[category,SEO_ARTICLES.filter(article=>article.category===category)] as [string,SeoArticle[]]);
const fold = (value:string)=>value.toLocaleLowerCase('tr').replace(/[\u0300-\u036f]/g,'');

const LEGAL_SECTIONS: [string,string][] = [
  ['Yatırım danışmanlığı değildir','Bu sitede yer alan bilgi, yorum, tahmin ve tavsiyeler yatırım danışmanlığı kapsamında değildir. Yatırım danışmanlığı hizmeti; yetkili kuruluşlar tarafından, kişilerin risk ve getiri tercihleri dikkate alınarak kişiye özel sunulur. Burada yer alan içerik ise geneldir ve mali durumunuz ile risk-getiri tercihlerinize uygun olmayabilir. Yalnızca buradaki bilgilere dayanılarak verilen yatırım kararları beklentilerinize uygun sonuçlar doğurmayabilir.'],
  ['Tahminler garanti değildir','Panelde gösterilen fiyat tahminleri, geçmiş verilerden türetilmiş istatistiksel kestirimlerdir; kesinlik, isabet ya da kâr garantisi taşımaz. Her tahmin bir belirsizlik bandıyla birlikte sunulur ve gerçekleşen fiyat bu bandın dışına çıkabilir. Modelin geçmiş isabet oranı gelecekteki başarısının göstergesi değildir.'],
  ['Veri doğruluğu','Fiyat ve makroekonomik veriler üçüncü taraf veri sağlayıcılardan alınır. Bu verilerin doğruluğu, güncelliği ve kesintisizliği garanti edilmez; gecikmeli, eksik veya hatalı olabilir. Gösterilen fiyatlar gösterge niteliğindedir ve işlem yapılabilir kotasyon değildir.'],
  ['Sorumluluğun sınırı','Bu platform hiçbir menkul kıymet, emtia veya finansal ürün için alım-satım teklifi ya da çağrısı değildir. Sitedeki içeriğe dayanarak alınan kararlardan ve bunların doğuracağı doğrudan veya dolaylı zararlardan site sahibi hiçbir şekilde sorumlu tutulamaz. Yatırım kararlarınızın sorumluluğu tamamen size aittir; karar öncesinde yetkili bir kuruluştan profesyonel destek almanız önerilir.'],
];
/** Uyarı üç ayrı bileşenden açılabildiği için prop yerine olay kullanılıyor. */
const openLegal=()=>window.dispatchEvent(new Event('legal:open'));

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

function SiteNav({current}:{current?:string}) {
  const [menu,setMenu]=useState<null|'guides'|'mobile'>(null);
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
    <a key={article.id} href={`/rehber/${article.id}`} onClick={close}
       aria-current={current===article.id?'page':undefined}
       className={current===article.id?'active':undefined}>{article.title}</a>;

  return <nav className="site-nav" aria-label="Ana menü" ref={navRef}>
    <a className="skip-link" href="#icerik">İçeriğe geç</a>
    <a className="brand" href="/" aria-label="Ons Altın Analiz ana sayfa"><img src="/favicon.svg" alt=""/><span>Ons Altın Analiz</span></a>

    <div className="desktop-links">
      {NAV_SECTIONS.map(([href,label])=><a key={href} href={href}>{label}</a>)}
      <button type="button" className="nav-legal" onClick={openLegal}>Yasal Uyarı</button>
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
          <a className="guide-all" href="/rehber" onClick={close}>Tüm rehberleri gör <span aria-hidden="true">→</span></a>
        </div>}
      </div>
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
            <button type="button" onClick={close} aria-label="Menüyü kapat">✕</button>
          </div>
          <div className="mobile-scroll">
            {!query&&<section className="mobile-sections">{NAV_SECTIONS.map(([href,label])=>
              <a key={href} href={href} onClick={close}>{label}</a>)}
              <a href="/rehber" onClick={close}>Tüm rehberler</a>
            </section>}
            {groups.map(([category,items])=><section key={category}><h3>{category}</h3>{items.map(guideLink)}</section>)}
            {groups.length===0&&<p className="guide-empty">Eşleşen rehber yok.</p>}
          </div>
        </div>
      </div>, document.body)}
  </nav>;
}

function SeoContent() {
  return <section className="seo-hub" id="rehberler" aria-labelledby="rehberler-baslik">
    <div className="seo-intro"><span className="eyebrow">Altın Bilgi Merkezi</span><h2 id="rehberler-baslik">Ons Altın Analizi ve Tahmin Rehberleri</h2><p>Canlı fiyatı doğru okumak, modeli değerlendirmek ve altını etkileyen ekonomik göstergeleri anlamak için hazırlanan özgün rehberler.</p></div>
    <nav className="topic-pills" aria-label="Rehber konuları">{SEO_ARTICLES.map(article=><a key={article.id} href={`/rehber/${article.id}`}>{article.keyword}</a>)}</nav>
    <div className="seo-articles">{SEO_ARTICLES.map((article,index)=><article id={article.id} key={article.id} className="seo-article seo-card">
      <header><span>{String(index+1).padStart(2,'0')}</span><div><small>Odak konu: {article.keyword}</small><h2>{article.title}</h2><p>{article.summary}</p></div></header>
      <a className="seo-read-more" href={`/rehber/${article.id}`} aria-label={`${article.title} rehberini oku`}>Rehberi oku <span aria-hidden="true">→</span></a>
    </article>)}</div>
  </section>;
}

function SiteFooter() {
  const featured=SEO_ARTICLES.slice(0,8);
  return <footer className="site-footer" id="risk-notu">
    <div className="footer-grid">
      <section className="footer-about" aria-labelledby="footer-brand-title"><a className="footer-brand" href="/"><img src="/favicon.svg" alt=""/><span id="footer-brand-title">Ons Altın Analiz</span></a><p>Canlı ons altın verilerini, ekonomik göstergeleri ve yapay zekâ destekli fiyat senaryolarını bir araya getiren bağımsız araştırma platformu.</p></section>
      <nav aria-label="Footer hızlı bağlantılar"><h2>Hızlı erişim</h2><a href="/#panel">Canlı ons paneli</a><a href="/#tahmin">Altın tahminleri</a><a href="/#rehberler">Altın rehberleri</a><a href="/sitemap.xml">Sitemap</a></nav>
      <nav aria-label="Öne çıkan altın rehberleri"><h2>Öne çıkan rehberler</h2>{featured.map(article=><a href={`/rehber/${article.id}`} key={article.id}>{article.title}</a>)}</nav>
      <section className="footer-creator" aria-labelledby="creator-title"><h2 id="creator-title">Projenin yaratıcısı</h2><strong>Ali Doğan</strong><span>Yaratıcı ve geliştirici</span><a className="linkedin-link" href="https://www.linkedin.com/in/ali-do%C4%9Fan-86b57721a/" target="_blank" rel="noopener noreferrer me" aria-label="Ali Doğan LinkedIn profilini yeni sekmede aç"><i aria-hidden="true">in</i>LinkedIn profilini görüntüle</a></section>
    </div>
    
    <div className="footer-bottom"><p>Bu platform eğitim ve araştırma amaçlıdır; yatırım danışmanlığı kapsamında değildir, getiri veya kâr garantisi sunmaz. <button type="button" className="link-btn" onClick={openLegal}>Yasal uyarının tamamı</button></p><span>© {new Date().getFullYear()} Ons Altın Analiz</span></div>
  </footer>;
}

function ArticlePage({article}) {
  useEffect(()=>{
    const url=`${window.location.origin}/rehber/${article.id}`;
    const title=`${article.seoTitle||article.title} | Ons Altın Analiz`;
    document.title=title;
    const set=(selector,value,attribute='content')=>{const node=document.querySelector(selector);if(node)node.setAttribute(attribute,value);};
    set('meta[name="description"]',article.summary);
    set('link[rel="canonical"]',url,'href');
    set('meta[property="og:title"]',title);
    set('meta[property="og:description"]',article.summary);
    set('meta[property="og:url"]',url);
    set('meta[name="twitter:title"]',title);
    set('meta[name="twitter:description"]',article.summary);
  },[article]);
  return <main className="app article-page"><SiteNav current={article.id}/><article className="standalone-article">
    <nav className="breadcrumbs" aria-label="İçerik yolu"><a href="/">Ana Sayfa</a><span>/</span><a href="/#rehberler">Altın Rehberi</a><span>/</span><b>{article.title}</b></nav>
    <header id="icerik"><span className="eyebrow">{article.keyword}</span><h1>{article.title}</h1><p>{article.summary}</p></header>
    <div className="standalone-body">
      <p className="article-intro">{article.intro}</p>
      {article.sections.map(section=><section key={section.heading}><h2>{section.heading}</h2>{section.paragraphs.map((paragraph,i)=><p key={i}>{paragraph}</p>)}</section>)}
      <section className="article-summary"><h2>Özet: {article.keyword}</h2><ul>{article.points.map(point=><li key={point}>{point}</li>)}</ul></section>
      <section className="article-faq"><h2>Sık sorulan sorular</h2>{article.faq.map(item=><div key={item.q}><h3>{item.q}</h3><p>{item.a}</p></div>)}</section>
      <p className="article-updated"><small>Son güncelleme: {article.updated}</small></p>
    </div>
    <nav className="related-guides" aria-label="Diğer altın rehberleri"><h2>Diğer rehberler</h2><div>{SEO_ARTICLES.filter(item=>item.id!==article.id).slice(0,4).map(item=><a href={`/rehber/${item.id}`} key={item.id}><small>{item.keyword}</small><b>{item.title}</b><span aria-hidden="true">→</span></a>)}</div></nav>
  </article><SiteFooter/></main>;
}

function DashboardApp() {
  const [mobile,setMobile]=useState(()=>typeof window!=='undefined'&&window.matchMedia('(max-width: 720px)').matches);
  const [values,setValues]=useState(fieldDefaults);
  const [live,setLive]=useState<Record<string,number>>({});
  const [history,setHistory]=useState(model.history);
  const [candles,setCandles]=useState<{date:string;h:number;l:number;c:number}[]>([]);
  const [pivotPeriod,setPivotPeriod]=useState<'weekly'|'monthly'>('weekly');
  const [pivotMethod,setPivotMethod]=useState<'classic'|'fib'>('classic');
  const [news,setNews]=useState([]);
  const [status,setStatus]=useState({type:'warn',text:'Canlı veriler bekleniyor'});
  const [spot,setSpot]=useState({price:model.latestPrice,change:0,secondChange:0,time:null,live:false});
  const [harem,setHarem]=useState({alis:null,satis:null,time:null,live:false});
  const [usdTry,setUsdTry]=useState({alis:null,satis:null,time:null,live:false});
  type Quote={alis:number;satis:number;dir:string;low:number;high:number;prev:number;time:string};
  const [ziynet,setZiynet]=useState<Record<string,Quote>>({});
  const [haremTicks,setHaremTicks]=useState([]),[wideChart,setWideChart]=useState(true);
  const [capital,setCapital]=useState(10000),[riskPct,setRiskPct]=useState(1);
  const [loanTerm,setLoanTerm]=useState(6),[loanAmount,setLoanAmount]=useState(100000),[loanRate,setLoanRate]=useState(4.25),[futureUsdTry,setFutureUsdTry]=useState(0);
  const [rangeDays,setRangeDays]=useState(90),[horizonDays,setHorizonDays]=useState(90),[showBand,setShowBand]=useState(true),[showLevels,setShowLevels]=useState(false),[showOrigin,setShowOrigin]=useState(true),[showSR,setShowSR]=useState(true);
  const snapshotDayRef=useRef('');
  const features=useMemo(()=>computeFeatures(values,live),[values,live]);
  const featureSignature=useMemo(()=>model.features.map(name=>Number(features[name]).toPrecision(10)).join('|'),[features]);
  const fallbackForecast=useMemo(()=>predict(features,values.price),[features,values.price]);
  const [apiForecast,setApiForecast]=useState(null);
  const forecast=useMemo(()=>apiForecast?{...apiForecast,features,price:+values.price}:fallbackForecast,[apiForecast,fallbackForecast,features,values.price]);
  const setField=(id,value)=>setValues(v=>({...v,[id]:value}));
  useEffect(()=>{const media=window.matchMedia('(max-width: 720px)'),update=()=>setMobile(media.matches);
    media.addEventListener('change',update);window.addEventListener('resize',update);update();
    return()=>{media.removeEventListener('change',update);window.removeEventListener('resize',update);};},[]);
  useEffect(()=>{const timer=setTimeout(async()=>{try{const response=await fetch(`${MODEL_API}/v1/predict`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({price:+values.price,features})});if(!response.ok)return;const data=await response.json();setApiForecast({mean:data.mean,err:data.error,version:data.version});}catch{}},700);return()=>clearTimeout(timer);},[featureSignature]);

  const refresh=useCallback(async()=>{
    setStatus({type:'warn',text:'Canlı veriler alınıyor…'});
    const next: Record<string,number>={}; let nextHistory=history;
    const tasks=[];
    tasks.push((async()=>{const k=await fetchJson(`${MARKET_API}/v1/market/binance`),c=k.map(v=>+v[4]),hi=k.map(v=>+v[2]),lo=k.map(v=>+v[3]),vol=k.map(v=>Math.log1p(+v[5])),last=c.length-1,ret=n=>c[last]/c[last-n]-1,ma=n=>avg(c.slice(-n));Object.assign(next,{gold_return_1d:ret(1),gold_return_5d:ret(5),gold_return_20d:ret(20),gold_return_60d:ret(60),gold_ma_ratio_20d:c[last]/ma(20)-1,gold_ma_ratio_50d:c[last]/ma(50)-1,gold_ma_ratio_200d:c[last]/ma(200)-1});const dif=c.slice(1).map((v,i)=>v-c[i]),g=dif.slice(-14).map(v=>Math.max(0,v)),l=dif.slice(-14).map(v=>Math.max(0,-v)),rs=avg(g)/(avg(l)||1e-9);next.gold_rsi14=100-100/(1+rs);const tr=c.slice(1).map((_,i)=>Math.max(hi[i+1]-lo[i+1],Math.abs(hi[i+1]-c[i]),Math.abs(lo[i+1]-c[i])));next.gold_atr14_pct=avg(tr.slice(-14))/c[last];const lr=c.slice(1).map((v,i)=>Math.log(v/c[i]));next.gold_volatility_20d=std(lr.slice(-20))*Math.sqrt(365);next.gold_volume_z20=(vol[last]-avg(vol.slice(-20)))/(std(vol.slice(-20))||1);nextHistory=k.map(v=>[new Date(v[0]).toISOString().slice(0,10),+v[4]]);setCandles(k.map(v=>({date:new Date(v[0]).toISOString().slice(0,10),h:+v[2],l:+v[3],c:+v[4]})));setField('price',c[last]);setField('gold_rsi14',next.gold_rsi14);setField('gold_atr14_pct',next.gold_atr14_pct*100);setField('gold_return_20d',next.gold_return_20d*100);setField('gold_volatility_20d',next.gold_volatility_20d*100);})());
    tasks.push((async()=>{const ids=['DGS10','DGS2','DFII10','DTWEXBGS','DCOILWTICO','VIXCLS','FEDFUNDS','CPIAUCSL','CPILFESL','PPIACO','PCEPI','UNRATE','PAYEMS','RSAFS'];const entries=await Promise.all(ids.map(async id=>[id,parseCsv(await (await fetch(`${MARKET_API}/v1/market/fred?id=${id}`)).text())]));const s=Object.fromEntries(entries),last=id=>s[id].at(-1).value,chg=(id,n,ratio=false)=>ratio?last(id)/s[id].at(-1-n).value-1:last(id)-s[id].at(-1-n).value,yoy=id=>(last(id)/s[id].at(-13).value-1)*100;['DGS10','DGS2','DFII10','DTWEXBGS','DCOILWTICO','VIXCLS','FEDFUNDS','UNRATE'].forEach(id=>next[id]=last(id));Object.assign(next,{CPIAUCSL_yoy_pct:yoy('CPIAUCSL'),CPILFESL_yoy_pct:yoy('CPILFESL'),PPIACO_yoy_pct:yoy('PPIACO'),PCEPI_yoy_pct:yoy('PCEPI'),PAYEMS_change_k:chg('PAYEMS',1),RSAFS_mom_pct:chg('RSAFS',1,true)*100,real_yield_change_5d:chg('DFII10',5),dollar_return_5d:chg('DTWEXBGS',5,true),oil_return_5d:chg('DCOILWTICO',5,true),vix_change_5d:chg('VIXCLS',5)});GROUPS.flatMap(([,x])=>x).forEach(([id])=>{if(next[id]!=null)setField(id,next[id]*(PCT_FIELDS.has(id)?100:1));});})());
    tasks.push(fetchJson(`${MARKET_API}/v1/market/news`).then(d=>setNews(d.articles||[])));
    const result=await Promise.allSettled(tasks);setLive(v=>({...v,...next}));setHistory(nextHistory);const ok=result.filter(x=>x.status==='fulfilled').length;setStatus(ok===3?{type:'ok',text:`Canlı · ${new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'})}`}:{type:'warn',text:`Kısmi canlı · ${ok}/3 kaynak`});
  },[]);
  useEffect(()=>{refresh();},[refresh]);
  useEffect(()=>{let active=true;const bootstrap=async()=>{try{const d=await fetchJson(`${MARKET_API}/v1/market/spot`);if(active)setSpot(s=>({...s,price:+d.lastPrice,change:+d.priceChangePercent,time:new Date(),live:true}));}catch{}};bootstrap();return()=>{active=false};},[]);
  useEffect(()=>{const stream=new WebSocket('wss://stream.binance.com:9443/ws/paxgusdt@ticker');stream.onmessage=event=>{const tick=JSON.parse(event.data),price=+tick.c;if(!Number.isFinite(price))return;setSpot({price,change:+tick.P,secondChange:0,time:new Date(),live:true});setValues(v=>({...v,price}));};stream.onerror=()=>setSpot(s=>({...s,live:false}));stream.onclose=()=>setSpot(s=>({...s,live:false}));return()=>stream.close();},[]);
  useEffect(()=>{const socket=io('wss://hrmsocketonly.haremaltin.com',{transports:['websocket'],reconnection:true,reconnectionDelay:1000});socket.on('price_changed',payload=>{const data=payload?.data||{},ons=data.ONS,usd=data.USDTRY||data.USD;setZiynet(prev=>{let next=prev;ZIYNET.forEach(([code])=>{const row=data[code];const alis=+(row?.alis),satis=+(row?.satis);if(Number.isFinite(alis)&&Number.isFinite(satis)&&satis>0){if(next===prev)next={...prev};next[code]={alis,satis,dir:row?.dir?.satis_dir||'',low:+(row?.dusuk)||0,high:+(row?.yuksek)||0,prev:+(row?.kapanis)||0,time:(row?.tarih||'').slice(-8)};}});return next;});if(ons){const alis=+ons.alis,satis=+ons.satis;if(Number.isFinite(alis)&&Number.isFinite(satis)){setHarem({alis,satis,time:new Date(),live:true});setHaremTicks(t=>[...t.slice(-89),{time:Date.now(),price:satis}]);}}if(usd){const alis=+usd.alis,satis=+usd.satis;if(Number.isFinite(alis)&&Number.isFinite(satis))setUsdTry({alis,satis,time:new Date(),live:true});}});socket.on('disconnect',()=>{setHarem(h=>({...h,live:false}));setUsdTry(rate=>({...rate,live:false}));});socket.on('connect_error',()=>{setHarem(h=>({...h,live:false}));setUsdTry(rate=>({...rate,live:false}));});return()=>{socket.disconnect();};},[]);
  useEffect(()=>{if(!spot.live||!harem.live||!harem.satis)return;const day=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Istanbul'});if(snapshotDayRef.current===day||snapshotDayRef.current===`pending:${day}`)return;snapshotDayRef.current=`pending:${day}`;(async()=>{try{const response=await fetch(`${MODEL_API}/v1/snapshots`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model_price:spot.price,display_price:harem.satis,features,observed_at:new Date().toISOString(),source:'PAXG/USDT',display_source:'ONS/XAUUSD'})});snapshotDayRef.current=response.ok?day:'';}catch{snapshotDayRef.current='';}})();},[spot.live,spot.price,harem.live,harem.satis,features]);

  const impacts=useMemo(()=>{
    const names={DFII10:'10Y reel faiz',DTWEXBGS:'Dolar endeksi',DGS10:'10Y tahvil faizi',VIXCLS:'VIX (risk iştahı)',
      CPIAUCSL_yoy_pct:'TÜFE (yıllık)',CPILFESL_yoy_pct:'Çekirdek TÜFE',UNRATE:'İşsizlik',gold_return_20d:'20 günlük momentum'};
    /* Karşılaştırmanın iki ucu da aynı modelden gelmeli. Önceden taban sunucu
       tahminiydi, fark ise tarayıcı modeliyle hesaplanıyordu; aradaki model farkı
       da katkı gibi görünüyordu. */
    const here=predict(features,values.price).mean[1];
    const atMean={...features};
    model.features.forEach((k,i)=>{atMean[k]=model.xMean[i];});
    const constant=predict(atMean,values.price).mean[1];
    const rows=Object.entries(names).map(([key,name])=>{
      const index=model.features.indexOf(key);
      const changed={...features,[key]:model.xMean[index]};
      changed.yield_curve_10y_2y=changed.DGS10-changed.DGS2;
      changed.breakeven_inflation_10y=changed.DGS10-changed.DFII10;
      return {name,key,value:here-predict(changed,values.price).mean[1],
        z:model.xStd[index]?(features[key]-model.xMean[index])/model.xStd[index]:0};
    }).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
    const peak=Math.max(...rows.map(r=>Math.abs(r.value)),1e-9);
    return {rows:rows.map(r=>({...r,share:Math.abs(r.value)/peak})),here,constant,total:here-constant};
  },[features,values.price]);
  const near=values.price*(1+forecast.mean[1]),band=values.price*forecast.err[1],atr=features.gold_atr14_pct*values.price,buy=[near-band*.72,near-band*.38],sell=[near+band*.35,near+band*.72],stop=buy[0]-Math.max(atr*1.5,band*.18),entry=avg(buy),units=(capital*riskPct/100)/Math.max(1,entry-stop);
  const historyEnd=history.length?history[history.length-1][0]:undefined;
  /* Pivot seviyeleri: önceki tam dönemin yüksek/düşük/kapanışından türetilir.
     Kendi bulduğumuz destek/direnç kümelerinden farklı olarak deterministik ve
     herkesin aynı şekilde hesapladığı standart bir yöntemdir; ikisi çakışırsa
     seviye güçlü demektir. Günlük pivot 90-180 günlük grafikte çok dar kaldığı
     için haftalık ve aylık dönem kullanılır. */
  const pivots=useMemo(()=>{
    if(candles.length<40) return null;
    const isoWeek=(date:string)=>{const d=new Date(`${date}T00:00:00Z`);
      const day=(d.getUTCDay()+6)%7; d.setUTCDate(d.getUTCDate()-day); return d.toISOString().slice(0,10);};
    const period=(key:(date:string)=>string)=>{
      const groups=new Map<string,{h:number;l:number;c:number}>();
      candles.forEach(candle=>{const id=key(candle.date); const g=groups.get(id);
        if(!g) groups.set(id,{h:candle.h,l:candle.l,c:candle.c});
        else {g.h=Math.max(g.h,candle.h);g.l=Math.min(g.l,candle.l);g.c=candle.c;}});
      const ids=[...groups.keys()].sort();
      return ids.length<2?null:{id:ids[ids.length-2],...groups.get(ids[ids.length-2])!};  // son tamamlanan dönem
    };
    const levels=(bar:{h:number;l:number;c:number})=>{
      const p=(bar.h+bar.l+bar.c)/3, range=bar.h-bar.l;
      return {
        pivot:p,
        classic:{r3:bar.h+2*(p-bar.l),r2:p+range,r1:2*p-bar.l,s1:2*p-bar.h,s2:p-range,s3:bar.l-2*(bar.h-p)},
        fib:{r3:p+range,r2:p+.618*range,r1:p+.382*range,s1:p-.382*range,s2:p-.618*range,s3:p-range},
      };
    };
    const weekly=period(isoWeek), monthly=period(date=>date.slice(0,7));
    return {weekly:weekly&&{...levels(weekly),id:weekly.id},monthly:monthly&&{...levels(monthly),id:monthly.id}};
  },[candles]);
  const tech=useMemo(()=>indicators(candles),[candles]);
  const pivotLadder=useMemo(()=>{
    const set=pivots?.[pivotPeriod]; if(!set) return null;
    const rows=pivotMethod==='classic'?set.classic:set.fib;
    const price=+harem.satis||+spot.price||0;
    const items=[['R3',rows.r3],['R2',rows.r2],['R1',rows.r1],['P',set.pivot],['S1',rows.s1],['S2',rows.s2],['S3',rows.s3]]
      .map(([name,value])=>({name:name as string,value:value as number,
        distance:price?((value as number)/price-1):0,above:(value as number)>=price}))
      .sort((a,b)=>b.value-a.value);
    const below=items.findIndex(i=>!i.above);
    return {id:set.id,price,items,
      insertAt:below<0?items.length:below,        // fiyat hepsinin üstündeyse en başa, altındaysa en sona
      nearestUp:items.filter(i=>i.above).at(-1)?.name,
      nearestDown:items.find(i=>!i.above)?.name};
  },[pivots,pivotPeriod,pivotMethod,harem.satis,spot.price]);
  const dailyForecast=useMemo(()=>buildDailyPath(forecast,horizonDays,historyEnd),[forecast,horizonDays,historyEnd]);
  /* Tablo, modelin yayınladığı ilk tahmine (model.latestDate) çapalıdır; o günkü girdilerle
     hesaplanır. Böylece geçmişte kalan günler için gerçekleşen fiyat ve hata gösterilebilir.
     Canlı girdilerle yeniden hesaplamak, geçmişi bugünün bilgisiyle tahmin etmek olurdu. */
  const originForecast=useMemo(()=>predict(model.latest,model.latestPrice),[]);
  const forecastTable=useMemo(()=>{
    const actual=new Map<string,number>(history.map(([date,value])=>[String(date),Number(value)]));
    return buildDailyPath({...originForecast,price:model.latestPrice},horizonDays,model.latestDate).slice(1).map(point=>{
      const real=actual.get(point.date);
      return {...point,real,errorPct:real==null?null:(point.v-real)/real};
    });
  },[originForecast,history,horizonDays]);
  /* İsabet karnesi: modelin 14 Ağustos'ta ilan ettiği tahmin ile gerçekleşen kapanışlar.
     Naif referans, "fiyat başladığı yerde kalır" kuralıdır (rastgele yürüyüş); bir modelin
     değeri ancak bu referanstan iyi olmasıyla ölçülür. */
  const scorecard=useMemo(()=>{
    const settled=forecastTable.filter(row=>row.real!=null);
    if(!settled.length) return null;
    const base=model.latestPrice;
    const err=settled.map(row=>Math.abs(row.v/row.real-1));
    const naive=settled.map(row=>Math.abs(base/row.real-1));
    const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
    const mae=mean(err), naiveMae=mean(naive);
    return {
      days:settled.length, mae, naiveMae,
      skill:naiveMae>0?1-mae/naiveMae:0,
      inBand:settled.filter(row=>row.real>=row.lo&&row.real<=row.hi).length,
      rightWay:settled.filter(row=>(row.v>=base)===(row.real>=base)).length,
      worst:settled.reduce((a,b)=>Math.abs(a.errorPct)>=Math.abs(b.errorPct)?a:b),
    };
  },[forecastTable]);
  const loan=useMemo(()=>loanProjection(forecast,loanTerm),[forecast,loanTerm]);
  const loanCosts=useMemo(()=>{const amount=Math.max(0,+loanAmount||0),monthly=loanPayment(amount,Math.max(0,+loanRate||0)/100,loanTerm),total=monthly*loanTerm,currentFx=+usdTry.satis||0,targetFx=+futureUsdTry||currentFx,fxReturn=currentFx>0?targetFx/currentFx-1:0,results=loan.scenarios.map(s=>{const onsReturn=s.ret,tlReturn=(1+onsReturn)*(1+fxReturn)-1;return{...s,onsReturn,tlReturn,monthly:breakEvenLoanRate(tlReturn,loanTerm),endValue:amount*(1+tlReturn),net:amount*(1+tlReturn)-total};});return{monthly,total,currentFx,targetFx,fxReturn,results};},[loan,loanAmount,loanRate,loanTerm,usdTry.satis,futureUsdTry]);

  return <main className="app">
    <SiteNav/>
    <header id="panel"><div id="icerik"><span className="eyebrow">Özgün Altın Tahmin Modeli</span><h1>Canlı Ons Altın Tahmin ve Senaryo Analiz Paneli</h1><p>Tahmin ve eğitim referansı PAXG/USDT; ONS/XAUUSD yalnızca canlı piyasa karşılaştırmasıdır.</p></div><div className="header-market"><div className="live-price token-price"><span><i className={spot.live?'ok':'warn'}/>PAXG / USDT</span><strong>{money2(spot.price)}</strong><b className={spot.change>=0?'positive':'negative'}>{spot.change>=0?'▲':'▼'} %{Math.abs(spot.change).toFixed(2)}</b><small>{spot.time?`Son fiyat ${spot.time.toLocaleTimeString('tr-TR')}`:'Canlı akış bekleniyor'}</small></div><div className="live-price ons-price"><span><i className={harem.live?'ok':'warn'}/>ONS / XAUUSD</span><strong>{harem.satis?money2(harem.satis):'Bağlanıyor…'}</strong><div className="bid-ask"><b>Alış {harem.alis?money2(harem.alis):'—'}</b><b>Satış {harem.satis?money2(harem.satis):'—'}</b></div><TickSparkline ticks={haremTicks}/><small>{harem.satis?`PAXG farkı ${(harem.satis-spot.price)>=0?'+':''}${money2(harem.satis-spot.price)}`:'Canlı ons akışı bekleniyor'}</small></div><div className="live-price fx-price"><span><i className={usdTry.live?'ok':'warn'}/>USD / TL</span><strong>{usdTry.satis?`₺${tryRate(usdTry.satis)}`:'Bağlanıyor…'}</strong><div className="bid-ask"><b>Alış {usdTry.alis?`₺${tryRate(usdTry.alis)}`:'—'}</b><b>Satış {usdTry.satis?`₺${tryRate(usdTry.satis)}`:'—'}</b></div><small>{usdTry.time?`Son kur ${usdTry.time.toLocaleTimeString('tr-TR')}`:'Canlı kur bekleniyor'}</small></div><div className="status"><b>Model {model.latestDate}</b><span>{model.rows.toLocaleString('tr-TR')} gözlem</span><button onClick={refresh}><i className={status.type}/>{status.text}</button></div></div></header>
    <div className="parameter-toggle-bar"><button onClick={()=>setWideChart(v=>!v)} aria-expanded={!wideChart}><span>⚙</span>{wideChart?'Parametreleri göster':'Parametreleri gizle'}</button></div>
    <div className={`layout ${wideChart?'wide-chart':''}`}><aside className="panel controls"><h2>Güncel parametreler</h2>{GROUPS.map(([title,items])=><section className="group" key={title}><h3>{title}</h3>{items.map(([id,label,unit])=><label key={id}><span>{label}{unit&&` (${unit})`}</span><input type="number" step="any" value={Number(values[id]).toFixed(id==='price'?2:3)} onChange={e=>setField(id,e.target.value)}/></label>)}</section>)}<button className="primary" onClick={()=>setValues(fieldDefaults())}>Eğitim değerlerine dön</button></aside>
      <section className="content"><div className="cards three" id="tahmin">{model.horizons.map((h,j)=>({h,j})).filter(x=>x.h!==7).map(({h,j})=><article className="panel card" key={h}><span>{LABELS[h]}</span><strong>{money(values.price*(1+forecast.mean[j]))}</strong><b className={forecast.mean[j]>=0?'positive':'negative'}>{forecast.mean[j]>=0?'▲':'▼'} {pct(forecast.mean[j])}</b><small>%{BAND_COVERAGE} bant<br/>{money(values.price*(1+forecast.mean[j]-forecast.err[j]))} – {money(values.price*(1+forecast.mean[j]+forecast.err[j]))}</small></article>)}</div>
        <section className="panel block loan-break-even" aria-labelledby="finance-comparison-title"><div className="loan-head"><div><span className="eyebrow">Varsayımsal karşılaştırma</span><h2 id="finance-comparison-title">Altının TL getirisi ve finansman maliyeti</h2><p>Ons senaryosu, canlı USD/TL kuru ve vade sonu kur varsayımıyla TL getirisine çevrilir.</p></div><div className="segmented">{[3,6,9].map(n=><button key={n} className={loanTerm===n?'active':''} onClick={()=>setLoanTerm(n)}>{n} Ay</button>)}</div></div><div className="loan-inputs"><label>Karşılaştırma tutarı (TL)<input type="text" inputMode="numeric" autoComplete="off" value={tryAmount(loanAmount)} onChange={e=>setLoanAmount(Number(e.target.value.replace(/\D/g,""))||0)}/></label><label>Aylık finansman maliyeti (%)<input type="number" min="0" step="0.01" value={loanRate} onChange={e=>setLoanRate(+e.target.value)}/></label><div><span>Canlı USD/TL</span><b>{loanCosts.currentFx?`₺${tryRate(loanCosts.currentFx)}`:'Bekleniyor'}</b></div><label>Vade sonu USD/TL varsayımı<input type="number" min="0" step="0.01" placeholder={loanCosts.currentFx?String(loanCosts.currentFx):''} value={futureUsdTry||''} onChange={e=>setFutureUsdTry(+e.target.value)}/></label><div><span>Toplam finansman maliyeti</span><b>{tryMoney(loanCosts.total)}</b></div></div><div className="loan-results">{loanCosts.results.map(s=><article className={`loan-result ${s.tone}`} key={s.label}><span>{s.label} · Ons {pct(s.onsReturn)} · TL {pct(s.tlReturn)}</span><strong className={s.net>=0?'positive':'negative'}>{s.net>=0?'+':''}{tryMoney(s.net)}</strong><small>{loanTerm} ay sonunda TL getirisi–maliyet farkı</small></article>)}</div><details className="break-even-details"><summary>Teorik başa baş oranlarını göster</summary><div className="loan-scenarios">{loanCosts.results.map(s=><article className={`loan-scenario ${s.tone}`} key={s.label}><span>{s.label}</span><strong>{s.monthly==null?'%0,00':`%${(s.monthly*100).toFixed(2).replace('.',',')}`}</strong><small>TL getirisine göre aylık teorik başa baş maliyeti</small></article>)}</div></details><div className="loan-note">Başlangıçta canlı USD/TL satış kuru kullanılır. Vade sonu kur alanı boşsa kurun değişmediği varsayılır; makas, vergi, sigorta ve diğer masraflar dahil değildir.{loan.derived&&<em> 9 aylık sonuç, modelin 6 aylık eğiliminden türetilmiştir.</em>}</div></section>
        <p className="inline-legal">Gösterilen tahminler istatistiksel kestirimdir; yatırım danışmanlığı kapsamında değildir ve kâr garantisi sunmaz. <button type="button" className="link-btn" onClick={openLegal}>Yasal uyarının tamamı</button></p>
        {scorecard&&<section className="panel block score-block" aria-labelledby="score-title">
          <div className="score-head">
            <div><span className="eyebrow">Modelin kendi karnesi</span>
              <h2 id="score-title">Tahminler ne kadar tuttu?</h2>
              <p>{model.latestDate} tarihinde ilan edilen tahmin, o günden bu yana gerçekleşen kapanışlarla karşılaştırılıyor. Her yeni günle bir ölçüm daha ekleniyor.</p></div>
            <div className="score-days"><b>{scorecard.days}</b><span>gün<br/>gerçekleşti</span></div>
          </div>
          <div className="score-grid">
            <div><span>Ortalama mutlak hata</span><b>{pct2(scorecard.mae)}</b>
              <small>Tahmin ile gerçekleşen arasındaki ortalama sapma</small></div>
            <div><span>Naif kural ("fiyat değişmez")</span><b>{pct2(scorecard.naiveMae)}</b>
              <small>Hiçbir bilgi kullanmayan referans</small></div>
            <div className={scorecard.skill>0?'good':'bad'}>
              <span>Modelin katkısı</span>
              <b>{scorecard.skill>=0?'+':''}{new Intl.NumberFormat('tr-TR',{maximumFractionDigits:0}).format(scorecard.skill*100)}%</b>
              <small>{scorecard.skill>0?'naif kuraldan bu kadar daha isabetli':'naif kural bu kadar daha isabetli — model henüz değer katmıyor'}</small></div>
            <div><span>Bant isabeti</span><b>{scorecard.inBand}/{scorecard.days}</b>
              <small>İlan edilen %{BAND_COVERAGE} bandın içinde kalan gün sayısı</small></div>
            <div><span>Yön isabeti</span><b>{scorecard.rightWay}/{scorecard.days}</b>
              <small>Yükselir/düşer yönünü doğru bilen gün sayısı</small></div>
            <div><span>En büyük sapma</span><b>{signedPct2(scorecard.worst.errorPct)}</b>
              <small>{new Date(`${scorecard.worst.date}T00:00:00`).toLocaleDateString('tr-TR')} · tahmin {money(scorecard.worst.v)} · gerçek {money(scorecard.worst.real)}</small></div>
          </div>
          <p className="score-note">{scorecard.days<20
            ? `Uyarı: ${scorecard.days} günlük ölçüm istatistiksel bir sonuç için çok azdır; bu rakamlar şimdilik yalnız şeffaflık amacıyla gösterilir. Anlamlı bir yargı için en az birkaç ay gerekir.`
            : 'Ölçüm penceresi genişledikçe bu rakamlar daha güvenilir hâle gelir.'}</p>
        </section>}
        {ZIYNET.some(([code])=>ziynet[code])&&<section className="panel block gram-block" aria-labelledby="gram-title">
          <div className="gram-head"><h2 id="gram-title">Canlı ziynet altın fiyatları</h2>
            <small>Harem Altın canlı kotasyonu; işçilik ve satıcı marjı fiyatın içindedir. Yüzde, önceki kapanışa göre satış fiyatındaki değişimdir.</small></div>
          <div className="gram-grid">
            {ZIYNET.filter(([code])=>ziynet[code]).map(([code,label])=>{
              const q=ziynet[code];
              /* Harem'in kapanis alanı bazı üründe bozuk geliyor: Yeni Ata gün
                 zirvesindeyken önceki kapanışı aralığın %65 üstünde bildiriyor ve
                 -%2,1 çıkıyor; neredeyse aynı ürün olan Tam altın ise +%2,3.
                 Aşağı boşlukla açılış normaldir (kapanış aralığın altında kalır),
                 kapanışın aralığın belirgin üstünde olması ise tutarsızlık işaretidir. */
              const band=q.high-q.low;
              const trusted=q.prev>0&&band>0&&q.prev>=q.low-1.5*band&&q.prev<=q.high+0.25*band;
              const change=trusted?q.satis/q.prev-1:0;
              const range=q.high-q.low;
              const at=range>0?Math.min(100,Math.max(0,(q.satis-q.low)/range*100)):50;
              return <article className={`quote ${trusted?(change>=0?'up':'down'):'flat'}`} key={code}>
                <header><span>{label}</span>
                  {trusted&&<b className={change>=0?'positive':'negative'}>{change>=0?'▲':'▼'} {pct(Math.abs(change))}</b>}
                </header>
                <strong key={q.satis} className={`tick-${q.dir||'flat'}`}>{tryMoney(q.satis)}</strong>
                <small>Alış {tryMoney(q.alis)} · Makas {tryMoney(q.satis-q.alis)}</small>
                {range>0&&<div className="quote-range" title={`Gün aralığı ${tryMoney(q.low)} – ${tryMoney(q.high)}`}>
                  <i style={{left:`${at}%`}}/>
                  <u>{tryMoney(q.low)}</u><em>{tryMoney(q.high)}</em>
                </div>}
              </article>;
            })}
          </div>
          <p className="gram-note">Bu fiyatlar ons ve kurdan nasıl türer: <a href="/rehber/gram-altin-fiyati-nasil-belirlenir">Gram altın fiyatı nasıl belirlenir?</a> · <a href="/rehber/ceyrek-altin-kac-gram">Çeyrek altın kaç gram?</a> · <a href="/rehber/altin-makasi-nedir">Alış-satış makası nedir?</a></p>
        </section>}
        <section className="panel block impact-block" aria-labelledby="impact-title"><div className="impact-head"><h2 id="impact-title">1 aylık tahmine parametre katkısı</h2><p>Her satır şunu ölçer: <b>o gösterge bugünkü değerinden uzun dönem ortalamasına çekilseydi, 1 aylık tahmin kaç puan değişirdi.</b> Pozitif değer, göstergenin bugünkü seviyesinin tahmini yukarı çektiği anlamına gelir. Yanındaki <em>sd</em> rozeti göstergenin ortalamadan kaç standart sapma uzakta olduğunu söyler.</p><p className="impact-caveat">Satırların toplamı alttaki parametre katkısına eşit çıkmaz: burada modelin 31 girdisinden yalnız en çok konuşulan 8'i listeleniyor ve model doğrusal olmadığı için etkiler birbirinden bağımsız değil.</p></div><div className="impact-grid">{impacts.rows.map(x=><div className="impact" key={x.key}><span>{x.name}<em className={Math.abs(x.z)>=1?'far':undefined}>{x.z>=0?'+':''}{x.z.toFixed(1)} sd</em></span><div><i className={x.value>=0?'pos':'neg'} style={{width:`${Math.max(3,x.share*100)}%`}}/></div><b className={x.value>=0?'positive':'negative'}>{x.value>=0?'+':''}{(x.value*100).toFixed(2)} p</b></div>)}</div><div className="impact-sum"><div><span>Sabit taban</span><b>{pct(impacts.constant)}</b><small>tüm göstergeler ortalamadayken modelin verdiği tahmin</small></div><div><span>Parametre katkısı</span><b className={impacts.total>=0?'positive':'negative'}>{impacts.total>=0?'+':''}{(impacts.total*100).toFixed(2)} p</b><small>bugünkü sapmaların toplam etkisi</small></div><div className="total"><span>1 aylık tahmin</span><b>{pct(impacts.here)}</b><small>sabit taban + parametre katkısı</small></div></div></section>
        <section className="panel block chart-block"><div className="chart-head"><div><h2>Gün gün fiyat yolu</h2><p>Solda gerçekleşen, sağda tahmin. Kesikli çizgi modelin {model.latestDate} tahmini; üzerine gelince o günün gerçekleşen değerini ve hatasını gösterir.</p></div><div className="chart-tools"><button className="wide-toggle" onClick={()=>setWideChart(v=>!v)}>{wideChart?'Parametreleri göster':'Grafiği genişlet'}</button><div className="tool-group"><span>Tahmin</span><div className="segmented">{([[30,'1 Ay'],[90,'3 Ay'],[180,'6 Ay']] as [number,string][]).map(([n,label])=><button key={n} className={horizonDays===n?'active':''} onClick={()=>setHorizonDays(n)}>{label}</button>)}</div></div><div className="tool-group"><span>Geçmiş</span><div className="segmented">{[30,90,180,260].map(n=><button key={n} className={rangeDays===n?'active':''} onClick={()=>setRangeDays(n)}>{n===260?'1Y':`${n}G`}</button>)}</div></div></div></div><ForecastChart forecast={forecast} history={history} rangeDays={rangeDays} horizonDays={horizonDays} showBand={showBand} showLevels={showLevels} showOrigin={showOrigin} showSR={showSR} originForecast={originForecast} onToggle={key=>{if(key==='band')setShowBand(v=>!v);else if(key==='origin')setShowOrigin(v=>!v);else if(key==='sr')setShowSR(v=>!v);else setShowLevels(v=>!v);}} levels={{buy,sell,stop}} spot={{...spot,price:harem.satis||spot.price}} tokenSpot={spot} mobile={mobile}/><details className="daily-table" open><summary>{model.latestDate} tahmini · {horizonDays} günlük değerler ({forecastTable.filter(r=>r.real!=null).length} gün gerçekleşti)</summary><div><table><thead><tr><th>Tarih</th><th>Olası min</th><th>Sinir ağı tahmini</th><th>Olası maks</th><th>Gerçekleşen</th><th>Hata</th></tr></thead><tbody>{forecastTable.map(row=><tr key={row.day} className={row.real==null?undefined:'settled-row'}><td>{new Date(`${row.date}T00:00:00`).toLocaleDateString('tr-TR')}</td><td>{money(row.lo)}</td><td>{money(row.v)}</td><td>{money(row.hi)}</td><td>{row.real==null?<span className="pending">—</span>:<b>{money(row.real)}</b>}</td><td>{row.errorPct==null?<span className="pending">—</span>:<b className={Math.abs(row.errorPct)<=0.01?'positive':'negative'}>{row.errorPct>=0?'+':''}{(row.errorPct*100).toFixed(2)}%</b>}</td></tr>)}</tbody></table></div></details></section>
        {tech&&<section className="panel block tech-block" aria-labelledby="tech-title">
          <div className="pivot-head"><div><h2 id="tech-title">Teknik göstergeler</h2>
            <small>Günlük PAXG/USDT mumlarından hesaplanır. Göstergenin bulunduğu durum yazılır; bilinçli olarak alım-satım kararı üretilmez — aşırı alım bölgesi yükselişin biteceği anlamına gelmez, güçlü trendlerde gösterge uzun süre orada kalabilir.</small></div></div>
          <div className="tech-grid">
            {tech.rows.map(row=><div className="tech-row" key={row.name}>
              <span>{row.name}{row.note&&<em>{row.note}</em>}</span>
              <b>{row.value}</b>
              <i className={`tech-state ${row.tone}`}>{row.text}</i>
            </div>)}
          </div>
          <h3 className="tech-sub">Hareketli ortalamalar</h3>
          <div className="tech-grid ma">
            {tech.averages.map(a=><div className="tech-row" key={a.n}>
              <span>MA{a.n}<em>EMA {money(a.ema)}</em></span>
              <b>{money(a.sma)}</b>
              <i className={`tech-state ${a.price>=a.sma?'up':'down'}`}>{a.price>=a.sma?'Fiyat üstünde':'Fiyat altında'}</i>
            </div>)}
          </div>
        </section>}
        {pivotLadder&&<section className="panel block pivot-block" aria-labelledby="pivot-title">
          <div className="pivot-head">
            <div><h2 id="pivot-title">Pivot seviyeleri</h2>
              <small>Önceki {pivotPeriod==='monthly'?'ayın':'haftanın'} yüksek/düşük/kapanışından hesaplanır ({pivotLadder.id}). Grafikteki destek-direnç kendi bulduğu bölgeleri gösterir; bu ise standart formülle herkesin aynı bulduğu seviyelerdir.</small></div>
            <div className="pivot-tools">
              <div className="segmented">{([['weekly','Haftalık'],['monthly','Aylık']] as const).map(([k,l])=>
                <button key={k} className={pivotPeriod===k?'active':''} onClick={()=>setPivotPeriod(k)}>{l}</button>)}</div>
              <div className="segmented">{([['classic','Klasik'],['fib','Fibonacci']] as const).map(([k,l])=>
                <button key={k} className={pivotMethod===k?'active':''} onClick={()=>setPivotMethod(k)}>{l}</button>)}</div>
            </div>
          </div>
          <div className="pivot-ladder">
            {pivotLadder.items.map((item,index)=><div key={item.name}>
              {index===pivotLadder.insertAt&&
                <div className="pivot-now"><span>şu an</span><b>{money(pivotLadder.price)}</b></div>}
              <div className={`pivot-row ${item.above?'up':'down'} ${item.name===pivotLadder.nearestUp||item.name===pivotLadder.nearestDown?'nearest':''}`}>
                <span className="pivot-name">{item.name}</span>
                <b>{money(item.value)}</b>
                <em>{item.distance>=0?'+':''}{(item.distance*100).toFixed(2)}%</em>
              </div>
            </div>)}
            {pivotLadder.insertAt===pivotLadder.items.length&&
              <div className="pivot-now"><span>şu an</span><b>{money(pivotLadder.price)}</b></div>}
          </div>
          <p className="pivot-note">Fiyatın hemen üstündeki seviye ilk direnç, hemen altındaki ilk destek olarak okunur. Bu bir işlem önerisi değildir. <a href="/rehber/altin-destek-direnc">Destek ve direnç nasıl okunur?</a></p>
        </section>}
        <div className="bottom"><section className="panel block"><h2>Altın etki bülteni</h2><div className="bulletins"><div><h3>Parametre özeti</h3><p><b>Reel faiz:</b> 5 günlük {features.real_yield_change_5d>=0?'+':''}{features.real_yield_change_5d.toFixed(2)} puan.</p><p><b>Dolar:</b> 5 günlük {pct(features.dollar_return_5d)}.</p><p><b>VIX:</b> 5 günlük {features.vix_change_5d>=0?'+':''}{features.vix_change_5d.toFixed(2)}.</p></div><div><h3>Canlı haberler</h3>{news.slice(0,5).map((n,i)=><a key={i} href={n.url} target="_blank" rel="noreferrer">{n.title}<small>{n.source}</small></a>)}</div></div></section>
          <section className="panel block"><h2>İşlem bölgeleri</h2><div className="level"><span>Kademeli alım</span><b>{money(buy[0])} – {money(buy[1])}</b></div><div className="level"><span>Kâr alma</span><b>{money(sell[0])} – {money(sell[1])}</b></div><div className="level danger"><span>Risk kesme</span><b>{money(stop)}</b></div><label className="risk">Portföy (USD)<input value={capital} onChange={e=>setCapital(+e.target.value)} type="number"/></label><label className="risk">Risk (%)<input value={riskPct} onChange={e=>setRiskPct(+e.target.value)} type="number" step=".1"/></label><div className="position">Örnek azami pozisyon <b>{units.toFixed(3)} PAXG · {money(units*entry)}</b></div></section></div>
        <SeoContent/>
        <SiteFooter/>
      </section></div>
  </main>;
}

function GuideHub() {
  useEffect(()=>{document.title='Ons Altın Rehberi | Ons Altın Analiz';},[]);
  return <main className="app article-page"><SiteNav/>
    <article className="standalone-article guide-hub">
      <nav className="breadcrumbs" aria-label="İçerik yolu"><a href="/">Ana Sayfa</a><span>/</span><b>Altın Rehberi</b></nav>
      <header id="icerik"><span className="eyebrow">Altın Bilgi Merkezi</span><h1>Ons Altın Rehberi</h1>
        <p>Canlı fiyatı okumaktan model tahminlerini değerlendirmeye, gram ve ziynet altın hesabından alım satım pratiğine kadar {SEO_ARTICLES.length} rehber; beş başlık altında toplandı.</p></header>
      <div className="standalone-body">{GUIDES_BY_CATEGORY.map(([category,items])=><section key={category}>
        <h2>{category}</h2>
        <div className="hub-cards">{items.map(article=><a className="hub-card" key={article.id} href={`/rehber/${article.id}`}>
          <small>{article.keyword}</small><b>{article.title}</b><span>{article.summary}</span></a>)}</div>
      </section>)}</div>
    </article><SiteFooter/></main>;
}

function App() {
  const path=window.location.pathname.replace(/\/+$/,'')||'/';
  if(path==='/rehber') return <><GuideHub/><LegalModal/></>;
  const match=path.match(/^\/rehber\/([a-z0-9-]+)$/);
  const article=match?SEO_ARTICLES.find(item=>item.id===match[1]):null;
  return <>{article?<ArticlePage article={article}/>:<DashboardApp/>}<LegalModal/></>;
}

export default App;
