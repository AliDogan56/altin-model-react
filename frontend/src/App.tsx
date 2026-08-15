import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { io } from 'socket.io-client';
import model from './data/model.json';

type ParameterItem = [id: string, label: string, unit: string];
type ParameterGroup = [title: string, items: ParameterItem[]];

const GROUPS: ParameterGroup[] = [
  ['Fiyat ve teknik', [['price','Ons fiyatı','USD'],['gold_rsi14','RSI (14)',''],['gold_atr14_pct','ATR (14)','%'],['gold_return_20d','20 günlük momentum','%'],['gold_volatility_20d','20 günlük oynaklık','%']]],
  ['Faiz ve dolar', [['DGS10','ABD 10Y faiz','%'],['DGS2','ABD 2Y faiz','%'],['DFII10','10Y reel faiz','%'],['DTWEXBGS','Dolar endeksi',''],['FEDFUNDS','Fed fon faizi','%']]],
  ['Risk ve emtia', [['VIXCLS','VIX',''],['DCOILWTICO','WTI petrol','USD']]],
  ['Makroekonomi', [['CPIAUCSL_yoy_pct','TÜFE yıllık','%'],['CPILFESL_yoy_pct','Çekirdek TÜFE','%'],['PCEPI_yoy_pct','PCE yıllık','%'],['UNRATE','İşsizlik','%'],['RSAFS_mom_pct','Perakende satış aylık','%']]],
];
const API_BASE=(import.meta.env.VITE_API_BASE||'http://{host}:8000').replace('{host}',window.location.hostname).replace(/\/$/,'');
const MARKET_API=`${API_BASE}/market-service`;
const MODEL_API=`${API_BASE}/model-service`;
const LABELS = {7:'1 Hafta',30:'1 Ay',90:'3 Ay',180:'6 Ay'};
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
const pct=v=>new Intl.NumberFormat('tr-TR',{style:'percent',minimumFractionDigits:1,maximumFractionDigits:1}).format(v);
const fieldDefaults = () => Object.fromEntries(GROUPS.flatMap(([,items])=>items).map(([id])=>[id,id==='price'?model.latestPrice:model.latest[id]*(PCT_FIELDS.has(id)?100:1)]));
const parseCsv = text => text.trim().split(/\r?\n/).slice(1).map(line=>{const [date,value]=line.split(',');return{date,value:+value};}).filter(x=>Number.isFinite(x.value));
const fetchJson = async url => { const r=await fetch(url); if(!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); };

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

function buildDailyPath(forecast,horizonDays) {
  const anchors=[{day:0,ret:0,err:0},...model.horizons.map((day,j)=>({day,ret:forecast.mean[j],err:forecast.err[j]}))];
  return Array.from({length:horizonDays+1},(_,day)=>{
    const right=anchors.find(a=>a.day>=day)||anchors.at(-1),ri=anchors.indexOf(right),left=anchors[Math.max(0,ri-1)],t=right.day===left.day?0:(day-left.day)/(right.day-left.day);
    const ret=Math.expm1(Math.log1p(Math.max(-.95,left.ret))*(1-t)+Math.log1p(Math.max(-.95,right.ret))*t);
    const err=left.err*(1-t)+right.err*t,date=new Date();date.setDate(date.getDate()+day);
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

function loanProjection(forecast,months) {
  const days=months*30,path=buildDailyPath(forecast,Math.min(days,180)),last=path.at(-1);
  let mean=last.ret,err=last.err,derived=false;
  if(days>180){const scale=days/180;mean=Math.expm1(Math.log1p(Math.max(-.95,mean))*scale);err*=Math.sqrt(scale);derived=true;}
  const scenarios=[{label:'Alt bant',ret:mean-err,tone:'low'},{label:'Model tahmini',ret:mean,tone:'base'},{label:'Üst bant',ret:mean+err,tone:'high'}].map(s=>({...s,monthly:breakEvenLoanRate(s.ret,months)}));
  return{months,derived,scenarios};
}

function ForecastChart({forecast,history,rangeDays,horizonDays,showBand,showLevels,levels,spot,binanceSpot,mobile}) {
  const W=mobile?600:1600,H=mobile?760:650,m={l:mobile?48:58,r:mobile?100:104,t:20,b:48};
  const [hover,setHover]=useState(null), svgRef=useRef(null);
  const [zoom,setZoom]=useState(1),[panDays,setPanDays]=useState(0);
  const shown=history.slice(-rangeDays), hist=shown.map((d,i)=>({i:i-(shown.length-1),v:d[1],date:d[0],kind:'Geçmiş'}));
  const daily=buildDailyPath(forecast,horizonDays),future=daily.map(d=>({...d,i:d.day,label:d.day===0?'Bugün':`${d.day}. gün`}));
  const anchorDays=[0,30,90,180].filter(d=>d<=horizonDays),futureAnchors=anchorDays.map(day=>future[day]);
  const resistance=Math.max(model.resistance.r20,model.resistance.r60)*(forecast.price/model.latestPrice)*(1+model.resistance.momentumJumpPct);
  const startI=-(shown.length-1),endI=horizonDays,totalSpan=endI-startI,visibleSpan=totalSpan/zoom,baseCenter=(startI+endI)/2;
  const center=Math.max(startI+visibleSpan/2,Math.min(endI-visibleSpan/2,baseCenter+panDays)),visibleStart=center-visibleSpan/2,visibleEnd=center+visibleSpan/2;
  const levelVals=showLevels?[...levels.buy,...levels.sell,levels.stop]:[];
  const vals=[...hist.map(d=>d.v),...future.flatMap(d=>showBand?[d.lo,d.hi]:[d.v]),resistance,spot.price,binanceSpot.price,...levelVals];let ymin=Math.min(...vals),ymax=Math.max(...vals);const pad=(ymax-ymin)*.08;ymin-=pad;ymax+=pad;
  const x=i=>m.l+(i-visibleStart)/(visibleEnd-visibleStart)*(W-m.l-m.r), y=v=>m.t+(ymax-v)/(ymax-ymin)*(H-m.t-m.b), points=a=>a.map(d=>`${x(d.i)},${y(d.v)}`).join(' ');
  const upper=future.map(d=>`${x(d.i)},${y(d.hi)}`).join(' '),lower=[...future].reverse().map(d=>`${x(d.i)},${y(d.lo)}`).join(' ');
  const allPoints=[...hist,...future];
  const onMove=e=>{const rect=svgRef.current.getBoundingClientRect(),px=(e.clientX-rect.left)/rect.width*W,day=visibleStart+(px-m.l)/(W-m.l-m.r)*(visibleEnd-visibleStart);setHover(allPoints.reduce((a,b)=>Math.abs(b.i-day)<Math.abs(a.i-day)?b:a));};
  const zone=(a,b,cls)=><rect className={cls} x={m.l} y={y(Math.max(a,b))} width={W-m.l-m.r} height={Math.max(2,Math.abs(y(a)-y(b)))}/>;
  const changeZoom=next=>{const z=Math.max(1,Math.min(6,next));setZoom(z);if(z===1)setPanDays(0);};
  return <div className="chart-wrap"><div className="zoom-controls"><span>Yakınlaştırma {zoom.toFixed(1)}×</span><button onClick={()=>setPanDays(v=>v-visibleSpan*.22)} disabled={zoom===1}>←</button><button onClick={()=>changeZoom(zoom/1.5)} disabled={zoom===1}>−</button><button onClick={()=>changeZoom(zoom*1.5)} disabled={zoom>=6}>+</button><button onClick={()=>setPanDays(v=>v+visibleSpan*.22)} disabled={zoom===1}>→</button><button onClick={()=>{setZoom(1);setPanDays(0)}} disabled={zoom===1}>Sıfırla</button></div><svg ref={svgRef} className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Altın fiyat tahmin grafiği" onPointerMove={onMove} onPointerLeave={()=>setHover(null)} onWheel={e=>{e.preventDefault();changeZoom(zoom*(e.deltaY<0?1.2:1/1.2));}}>
    {[0,1,2,3,4].map(k=>{const v=ymin+(ymax-ymin)*k/4;return <g key={k}><line className="gridline" x1={m.l} y1={y(v)} x2={W-m.r} y2={y(v)}/><text className="axis" x={m.l-8} y={y(v)+3} textAnchor="end">{Math.round(v).toLocaleString('tr-TR')}</text></g>})}
    {showLevels&&<>{zone(levels.buy[0],levels.buy[1],'buy-zone')}{zone(levels.sell[0],levels.sell[1],'sell-zone')}<line className="stop-line" x1={m.l} y1={y(levels.stop)} x2={W-m.r} y2={y(levels.stop)}/><text className="stop-label" x={m.l+5} y={y(levels.stop)-5}>Risk kesme {money(levels.stop)}</text></>}
    {showBand&&<polygon className="band" points={`${upper} ${lower}`}/>}<polyline className="history" points={points(hist)}/><polyline className="forecast" points={points(future)}/>
    <g className="live-chart-price"><line x1={m.l} y1={y(spot.price)} x2={W-m.r} y2={y(spot.price)}/><circle cx={x(0)} cy={y(spot.price)} r="7"/><rect x={W-m.r+6} y={y(spot.price)-19} width="94" height="38" rx="8"/><text x={W-m.r+53} y={y(spot.price)+5} textAnchor="middle">{money2(spot.price)}</text><text className="harem-line-label" x={m.l+7} y={y(spot.price)-8}>Harem ONS</text></g>
    <g className="binance-chart-price"><line x1={m.l} y1={y(binanceSpot.price)} x2={W-m.r} y2={y(binanceSpot.price)}/><circle cx={x(0)} cy={y(binanceSpot.price)} r="5"/><text x={m.l+7} y={y(binanceSpot.price)+14}>Binance PAXG {money2(binanceSpot.price)}</text></g>
    <line className="resistance" x1={m.l} y1={y(resistance)} x2={W-m.r} y2={y(resistance)}/><text className="guide" x={W-m.r-3} y={y(resistance)-6} textAnchor="end">Momentum eşiği {money(resistance)}</text>
    {futureAnchors.map((d,i)=><g key={d.i}><circle cx={x(d.i)} cy={y(d.v)} r={i?5:4} className={i?'future-dot':'today-dot'}/><text className="axis" x={x(d.i)} y={H-15} textAnchor="middle">{d.i===0?'Bugün':LABELS[d.i]}</text></g>)}
    <text className="axis" x={m.l} y={H-15}>−{rangeDays} gün</text><text className="axis-title" transform={`translate(16 ${H/2}) rotate(-90)`} textAnchor="middle">USD / ons</text>
    {hover&&(()=>{const isForecast=Number.isFinite(hover.lo)&&Number.isFinite(hover.hi),boxW=isForecast?218:166,boxH=isForecast?92:48,boxX=Math.min(W-m.r-boxW-6,Math.max(m.l+5,x(hover.i)+12)),boxY=Math.min(H-m.b-boxH-6,Math.max(10,y(hover.v)-boxH/2));return <g className="crosshair"><line x1={x(hover.i)} y1={m.t} x2={x(hover.i)} y2={H-m.b}/>{isForecast&&showBand&&<><line className="band-range" x1={x(hover.i)} y1={y(hover.hi)} x2={x(hover.i)} y2={y(hover.lo)}/><circle className="band-max-dot" cx={x(hover.i)} cy={y(hover.hi)} r="4"/><circle className="band-min-dot" cx={x(hover.i)} cy={y(hover.lo)} r="4"/></>}<circle cx={x(hover.i)} cy={y(hover.v)} r="6"/><g className="hover-card" transform={`translate(${boxX} ${boxY})`}><rect width={boxW} height={boxH} rx="8"/><text x="11" y="19">{hover.date}</text>{isForecast?<><text x="11" y="40" className="tip-min">Olası minimum (%{BAND_COVERAGE})</text><text x={boxW-11} y="40" textAnchor="end" className="tip-value tip-min">{money(hover.lo)}</text><text x="11" y="61" className="tip-price">Sinir ağı tahmini</text><text x={boxW-11} y="61" textAnchor="end" className="tip-value tip-price">{money(hover.v)}</text><text x="11" y="82" className="tip-max">Olası maksimum (%{BAND_COVERAGE})</text><text x={boxW-11} y="82" textAnchor="end" className="tip-value tip-max">{money(hover.hi)}</text></>:<text x="10" y="37" className="tip-price">{hover.kind}: {money(hover.v)}</text>}</g></g>})()}
  </svg><div className="chart-legend"><span><i className="binance-key"/>Binance canlı</span><span><i className="harem-key"/>Harem canlı</span><span><i className="history-key"/>Binance geçmiş</span><span><i className="forecast-key"/>Sinir ağı tahmini</span>{showBand&&<span><i className="band-key"/>%{BAND_COVERAGE} tahmin bandı</span>}{showLevels&&<><span><i className="buy-key"/>Alım bölgesi</span><span><i className="sell-key"/>Kâr alma</span></>}</div></div>;
}

function TickSparkline({ticks}) {
  if(ticks.length<2)return <div className="tick-empty">Saniyelik akış hazırlanıyor…</div>;
  const W=190,H=34,min=Math.min(...ticks.map(t=>t.price)),max=Math.max(...ticks.map(t=>t.price)),span=max-min||1;
  const pts=ticks.map((t,i)=>`${i/(ticks.length-1)*W},${H-3-(t.price-min)/span*(H-6)}`).join(' '),up=ticks.at(-1).price>=ticks[0].price;
  return <svg className={`tick-spark ${up?'up':'down'}`} viewBox={`0 0 ${W} ${H}`} aria-label="Son saniyelerde ons fiyat hareketi"><polyline points={pts}/></svg>;
}

function App() {
  const [mobile,setMobile]=useState(()=>typeof window!=='undefined'&&window.matchMedia('(max-width: 720px)').matches);
  const [values,setValues]=useState(fieldDefaults);
  const [live,setLive]=useState<Record<string,number>>({});
  const [history,setHistory]=useState(model.history);
  const [news,setNews]=useState([]);
  const [status,setStatus]=useState({type:'warn',text:'Canlı veriler bekleniyor'});
  const [spot,setSpot]=useState({price:model.latestPrice,change:0,secondChange:0,time:null,live:false});
  const [harem,setHarem]=useState({alis:null,satis:null,time:null,live:false});
  const [haremTicks,setHaremTicks]=useState([]),[wideChart,setWideChart]=useState(true);
  const [capital,setCapital]=useState(10000),[riskPct,setRiskPct]=useState(1);
  const [loanTerm,setLoanTerm]=useState(6),[loanAmount,setLoanAmount]=useState(100000),[loanRate,setLoanRate]=useState(4.25);
  const [rangeDays,setRangeDays]=useState(90),[horizonDays,setHorizonDays]=useState(90),[showBand,setShowBand]=useState(true),[showLevels,setShowLevels]=useState(true);
  const snapshotDayRef=useRef('');
  const features=useMemo(()=>computeFeatures(values,live),[values,live]);
  const featureSignature=useMemo(()=>model.features.map(name=>Number(features[name]).toPrecision(10)).join('|'),[features]);
  const fallbackForecast=useMemo(()=>predict(features,values.price),[features,values.price]);
  const [apiForecast,setApiForecast]=useState(null);
  const forecast=useMemo(()=>apiForecast?{...apiForecast,features,price:+values.price}:fallbackForecast,[apiForecast,fallbackForecast,features,values.price]);
  const setField=(id,value)=>setValues(v=>({...v,[id]:value}));
  useEffect(()=>{const media=window.matchMedia('(max-width: 720px)'),update=()=>setMobile(media.matches);media.addEventListener('change',update);return()=>media.removeEventListener('change',update);},[]);
  useEffect(()=>{const timer=setTimeout(async()=>{try{const response=await fetch(`${MODEL_API}/v1/predict`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({price:+values.price,features})});if(!response.ok)return;const data=await response.json();setApiForecast({mean:data.mean,err:data.error,version:data.version});}catch{}},700);return()=>clearTimeout(timer);},[featureSignature]);

  const refresh=useCallback(async()=>{
    setStatus({type:'warn',text:'Canlı veriler alınıyor…'});
    const next: Record<string,number>={}; let nextHistory=history;
    const tasks=[];
    tasks.push((async()=>{const k=await fetchJson(`${MARKET_API}/v1/market/binance`),c=k.map(v=>+v[4]),hi=k.map(v=>+v[2]),lo=k.map(v=>+v[3]),vol=k.map(v=>Math.log1p(+v[5])),last=c.length-1,ret=n=>c[last]/c[last-n]-1,ma=n=>avg(c.slice(-n));Object.assign(next,{gold_return_1d:ret(1),gold_return_5d:ret(5),gold_return_20d:ret(20),gold_return_60d:ret(60),gold_ma_ratio_20d:c[last]/ma(20)-1,gold_ma_ratio_50d:c[last]/ma(50)-1,gold_ma_ratio_200d:c[last]/ma(200)-1});const dif=c.slice(1).map((v,i)=>v-c[i]),g=dif.slice(-14).map(v=>Math.max(0,v)),l=dif.slice(-14).map(v=>Math.max(0,-v)),rs=avg(g)/(avg(l)||1e-9);next.gold_rsi14=100-100/(1+rs);const tr=c.slice(1).map((_,i)=>Math.max(hi[i+1]-lo[i+1],Math.abs(hi[i+1]-c[i]),Math.abs(lo[i+1]-c[i])));next.gold_atr14_pct=avg(tr.slice(-14))/c[last];const lr=c.slice(1).map((v,i)=>Math.log(v/c[i]));next.gold_volatility_20d=std(lr.slice(-20))*Math.sqrt(365);next.gold_volume_z20=(vol[last]-avg(vol.slice(-20)))/(std(vol.slice(-20))||1);nextHistory=k.map(v=>[new Date(v[0]).toISOString().slice(0,10),+v[4]]);setField('price',c[last]);setField('gold_rsi14',next.gold_rsi14);setField('gold_atr14_pct',next.gold_atr14_pct*100);setField('gold_return_20d',next.gold_return_20d*100);setField('gold_volatility_20d',next.gold_volatility_20d*100);})());
    tasks.push((async()=>{const ids=['DGS10','DGS2','DFII10','DTWEXBGS','DCOILWTICO','VIXCLS','FEDFUNDS','CPIAUCSL','CPILFESL','PPIACO','PCEPI','UNRATE','PAYEMS','RSAFS'];const entries=await Promise.all(ids.map(async id=>[id,parseCsv(await (await fetch(`${MARKET_API}/v1/market/fred?id=${id}`)).text())]));const s=Object.fromEntries(entries),last=id=>s[id].at(-1).value,chg=(id,n,ratio=false)=>ratio?last(id)/s[id].at(-1-n).value-1:last(id)-s[id].at(-1-n).value,yoy=id=>(last(id)/s[id].at(-13).value-1)*100;['DGS10','DGS2','DFII10','DTWEXBGS','DCOILWTICO','VIXCLS','FEDFUNDS','UNRATE'].forEach(id=>next[id]=last(id));Object.assign(next,{CPIAUCSL_yoy_pct:yoy('CPIAUCSL'),CPILFESL_yoy_pct:yoy('CPILFESL'),PPIACO_yoy_pct:yoy('PPIACO'),PCEPI_yoy_pct:yoy('PCEPI'),PAYEMS_change_k:chg('PAYEMS',1),RSAFS_mom_pct:chg('RSAFS',1,true)*100,real_yield_change_5d:chg('DFII10',5),dollar_return_5d:chg('DTWEXBGS',5,true),oil_return_5d:chg('DCOILWTICO',5,true),vix_change_5d:chg('VIXCLS',5)});GROUPS.flatMap(([,x])=>x).forEach(([id])=>{if(next[id]!=null)setField(id,next[id]*(PCT_FIELDS.has(id)?100:1));});})());
    tasks.push(fetchJson(`${MARKET_API}/v1/market/news`).then(d=>setNews(d.articles||[])));
    const result=await Promise.allSettled(tasks);setLive(v=>({...v,...next}));setHistory(nextHistory);const ok=result.filter(x=>x.status==='fulfilled').length;setStatus(ok===3?{type:'ok',text:`Canlı · ${new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'})}`}:{type:'warn',text:`Kısmi canlı · ${ok}/3 kaynak`});
  },[]);
  useEffect(()=>{refresh();},[refresh]);
  useEffect(()=>{let active=true;const bootstrap=async()=>{try{const d=await fetchJson(`${MARKET_API}/v1/market/spot`);if(active)setSpot(s=>({...s,price:+d.lastPrice,change:+d.priceChangePercent,time:new Date(),live:true}));}catch{}};bootstrap();return()=>{active=false};},[]);
  useEffect(()=>{const stream=new WebSocket('wss://stream.binance.com:9443/ws/paxgusdt@ticker');stream.onmessage=event=>{const tick=JSON.parse(event.data),price=+tick.c;if(!Number.isFinite(price))return;setSpot({price,change:+tick.P,secondChange:0,time:new Date(),live:true});setValues(v=>({...v,price}));};stream.onerror=()=>setSpot(s=>({...s,live:false}));stream.onclose=()=>setSpot(s=>({...s,live:false}));return()=>stream.close();},[]);
  useEffect(()=>{const socket=io('wss://hrmsocketonly.haremaltin.com',{transports:['websocket'],reconnection:true,reconnectionDelay:1000});socket.on('price_changed',payload=>{const ons=payload?.data?.ONS;if(!ons)return;const alis=+ons.alis,satis=+ons.satis;if(!Number.isFinite(alis)||!Number.isFinite(satis))return;setHarem({alis,satis,time:new Date(),live:true});setHaremTicks(t=>[...t.slice(-89),{time:Date.now(),price:satis}]);});socket.on('disconnect',()=>setHarem(h=>({...h,live:false})));socket.on('connect_error',()=>setHarem(h=>({...h,live:false})));return()=>{socket.disconnect();};},[]);
  useEffect(()=>{if(!spot.live||!harem.live||!harem.satis)return;const day=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Istanbul'});if(snapshotDayRef.current===day||snapshotDayRef.current===`pending:${day}`)return;snapshotDayRef.current=`pending:${day}`;(async()=>{try{const response=await fetch(`${MODEL_API}/v1/snapshots`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model_price:spot.price,display_price:harem.satis,features,observed_at:new Date().toISOString(),source:'Binance PAXGUSDT',display_source:'Harem ONS'})});snapshotDayRef.current=response.ok?day:'';}catch{snapshotDayRef.current='';}})();},[spot.live,spot.price,harem.live,harem.satis,features]);

  const impacts=useMemo(()=>{const names={DFII10:'10Y reel faiz',DTWEXBGS:'Dolar',DGS10:'10Y faiz',VIXCLS:'VIX',CPIAUCSL_yoy_pct:'TÜFE',CPILFESL_yoy_pct:'Çekirdek TÜFE',UNRATE:'İşsizlik',gold_return_20d:'20g momentum'};const base=forecast.mean[1];return Object.entries(names).map(([k,name])=>{const changed={...features,[k]:model.xMean[model.features.indexOf(k)]};changed.yield_curve_10y_2y=changed.DGS10-changed.DGS2;changed.breakeven_inflation_10y=changed.DGS10-changed.DFII10;return{name,value:base-predict(changed,values.price).mean[1]};}).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));},[features,forecast,values.price]);
  const near=values.price*(1+forecast.mean[1]),band=values.price*forecast.err[1],atr=features.gold_atr14_pct*values.price,buy=[near-band*.72,near-band*.38],sell=[near+band*.35,near+band*.72],stop=buy[0]-Math.max(atr*1.5,band*.18),entry=avg(buy),units=(capital*riskPct/100)/Math.max(1,entry-stop);
  const dailyForecast=useMemo(()=>buildDailyPath(forecast,horizonDays),[forecast,horizonDays]);
  const loan=useMemo(()=>loanProjection(forecast,loanTerm),[forecast,loanTerm]);
  const loanCosts=useMemo(()=>{const amount=Math.max(0,+loanAmount||0),monthly=loanPayment(amount,Math.max(0,+loanRate||0)/100,loanTerm),total=monthly*loanTerm;return{monthly,total,results:loan.scenarios.map(s=>({...s,endValue:amount*(1+s.ret),net:amount*(1+s.ret)-total}))};},[loan,loanAmount,loanRate,loanTerm]);

  return <main className="app">
    <header><div><span className="eyebrow">Binance Modeli · Harem Karşılaştırması</span><h1>Çok Ufuklu Model Paneli</h1><p>Tahmin ve eğitim referansı Binance PAXG; Harem ONS yalnızca canlı karşılaştırmadır.</p></div><div className="header-market"><div className="live-price binance-price"><span><i className={spot.live?'ok':'warn'}/>Binance PAXG / USDT</span><strong>{money2(spot.price)}</strong><b className={spot.change>=0?'positive':'negative'}>{spot.change>=0?'▲':'▼'} %{Math.abs(spot.change).toFixed(2)}</b><small>{spot.time?`Son Binance tick ${spot.time.toLocaleTimeString('tr-TR')}`:'Binance akışı bekleniyor'}</small></div><div className="live-price harem-price"><span><i className={harem.live?'ok':'warn'}/>Harem ONS / XAUUSD</span><strong>{harem.satis?money2(harem.satis):'Bağlanıyor…'}</strong><div className="bid-ask"><b>Alış {harem.alis?money2(harem.alis):'—'}</b><b>Satış {harem.satis?money2(harem.satis):'—'}</b></div><TickSparkline ticks={haremTicks}/><small>{harem.satis?`Binance farkı ${(harem.satis-spot.price)>=0?'+':''}${money2(harem.satis-spot.price)}`:'Harem canlı akışı bekleniyor'}</small></div><div className="status"><b>Model {model.latestDate}</b><span>{model.rows.toLocaleString('tr-TR')} gözlem</span><button onClick={refresh}><i className={status.type}/>{status.text}</button></div></div></header>
    <div className="parameter-toggle-bar"><button onClick={()=>setWideChart(v=>!v)} aria-expanded={!wideChart}><span>⚙</span>{wideChart?'Parametreleri göster':'Parametreleri gizle'}</button></div>
    <div className={`layout ${wideChart?'wide-chart':''}`}><aside className="panel controls"><h2>Güncel parametreler</h2>{GROUPS.map(([title,items])=><section className="group" key={title}><h3>{title}</h3>{items.map(([id,label,unit])=><label key={id}><span>{label}{unit&&` (${unit})`}</span><input type="number" step="any" value={Number(values[id]).toFixed(id==='price'?2:3)} onChange={e=>setField(id,e.target.value)}/></label>)}</section>)}<button className="primary" onClick={()=>setValues(fieldDefaults())}>Eğitim değerlerine dön</button></aside>
      <section className="content"><div className="cards three">{model.horizons.map((h,j)=>({h,j})).filter(x=>x.h!==7).map(({h,j})=><article className="panel card" key={h}><span>{LABELS[h]}</span><strong>{money(values.price*(1+forecast.mean[j]))}</strong><b className={forecast.mean[j]>=0?'positive':'negative'}>{forecast.mean[j]>=0?'▲':'▼'} {pct(forecast.mean[j])}</b><small>%{BAND_COVERAGE} bant<br/>{money(values.price*(1+forecast.mean[j]-forecast.err[j]))} – {money(values.price*(1+forecast.mean[j]+forecast.err[j]))}</small></article>)}</div>
        <section className="panel block loan-break-even"><div className="loan-head"><div><h2>Altın kredisi kâr hesabı</h2><p>Krediyle alınan altının seçilen vade sonundaki tahmini net sonucunu gösterir.</p></div><div className="segmented">{[3,6,9].map(n=><button key={n} className={loanTerm===n?'active':''} onClick={()=>setLoanTerm(n)}>{n} Ay</button>)}</div></div><div className="loan-inputs"><label>Kredi miktarı (TL)<input type="number" min="0" step="1000" value={loanAmount} onChange={e=>setLoanAmount(+e.target.value)}/></label><label>Aylık faiz (%)<input type="number" min="0" step="0.01" value={loanRate} onChange={e=>setLoanRate(+e.target.value)}/></label><div><span>Aylık taksit</span><b>{tryMoney(loanCosts.monthly)}</b></div><div><span>Toplam geri ödeme</span><b>{tryMoney(loanCosts.total)}</b></div></div><div className="loan-results">{loanCosts.results.map(s=><article className={`loan-result ${s.tone}`} key={s.label}><span>{s.label} · Ons {pct(s.ret)}</span><strong className={s.net>=0?'positive':'negative'}>{s.net>=0?'+':''}{tryMoney(s.net)}</strong><small>{loanTerm} ay sonundaki net {s.net>=0?'kâr':'zarar'}</small></article>)}</div><details className="break-even-details"><summary>Başa baş faizlerini göster</summary><div className="loan-scenarios">{loan.scenarios.map(s=><article className={`loan-scenario ${s.tone}`} key={s.label}><span>{s.label}</span><strong>{s.monthly==null?'%0,00':`%${(s.monthly*100).toFixed(2).replace('.',',')}`}</strong><small>Aylık azami kredi faizi</small></article>)}</div></details><div className="loan-note">Kur sabit varsayılmıştır; makas, vergi, sigorta ve kredi masrafları dahil değildir.{loan.derived&&<em> 9 aylık sonuç, modelin 6 aylık eğiliminden türetilmiştir.</em>}</div></section>
        <section className="panel block impact-block"><h2>Aylık tahmine parametre katkısı</h2><div className="impact-grid">{impacts.map(x=><div className="impact" key={x.name}><span>{x.name}</span><div><i className={x.value>=0?'pos':'neg'} style={{width:`${Math.min(100,Math.abs(x.value)*1700)}%`}}/></div><b className={x.value>=0?'positive':'negative'}>{x.value>=0?'+':''}{pct(x.value)}</b></div>)}</div></section>
        <section className="panel block chart-block"><div className="chart-head"><div><h2>Gün gün fiyat yolu ve model bölgeleri</h2><p>Tahmin Binance PAXG referanslıdır; Harem ONS karşılaştırma çizgisi olarak gösterilir.</p></div><div className="chart-tools"><button className="wide-toggle" onClick={()=>setWideChart(v=>!v)}>{wideChart?'Parametreleri göster':'Grafiği genişlet'}</button><div className="tool-group"><span>Tahmin</span><div className="segmented">{([[30,'1 Ay'],[90,'3 Ay'],[180,'6 Ay']] as [number,string][]).map(([n,label])=><button key={n} className={horizonDays===n?'active':''} onClick={()=>setHorizonDays(n)}>{label}</button>)}</div></div><div className="tool-group"><span>Geçmiş</span><div className="segmented">{[30,90,180,260].map(n=><button key={n} className={rangeDays===n?'active':''} onClick={()=>setRangeDays(n)}>{n===260?'1Y':`${n}G`}</button>)}</div></div><label><input type="checkbox" checked={showBand} onChange={e=>setShowBand(e.target.checked)}/> Tahmin bandı</label><label><input type="checkbox" checked={showLevels} onChange={e=>setShowLevels(e.target.checked)}/> İşlem bölgeleri</label></div></div><ForecastChart forecast={forecast} history={history} rangeDays={rangeDays} horizonDays={horizonDays} showBand={showBand} showLevels={showLevels} levels={{buy,sell,stop}} spot={{...spot,price:harem.satis||spot.price}} binanceSpot={spot} mobile={mobile}/><details className="daily-table"><summary>{horizonDays} günlük tahmin değerlerini göster</summary><div><table><thead><tr><th>Gün</th><th>Tarih</th><th>Tahmin</th><th>Günlük değişim</th><th>%{BAND_COVERAGE} alt</th><th>%{BAND_COVERAGE} üst</th></tr></thead><tbody>{dailyForecast.slice(1).map((d,i)=><tr key={d.day}><td>{d.day}</td><td>{new Date(`${d.date}T00:00:00`).toLocaleDateString('tr-TR')}</td><td>{money(d.v)}</td><td className={d.v>=dailyForecast[i].v?'positive':'negative'}>{pct(d.v/dailyForecast[i].v-1)}</td><td>{money(d.lo)}</td><td>{money(d.hi)}</td></tr>)}</tbody></table></div></details></section>
        <div className="bottom"><section className="panel block"><h2>Altın etki bülteni</h2><div className="bulletins"><div><h3>Parametre özeti</h3><p><b>Reel faiz:</b> 5 günlük {features.real_yield_change_5d>=0?'+':''}{features.real_yield_change_5d.toFixed(2)} puan.</p><p><b>Dolar:</b> 5 günlük {pct(features.dollar_return_5d)}.</p><p><b>VIX:</b> 5 günlük {features.vix_change_5d>=0?'+':''}{features.vix_change_5d.toFixed(2)}.</p></div><div><h3>Canlı haberler</h3>{news.slice(0,5).map((n,i)=><a key={i} href={n.url} target="_blank" rel="noreferrer">{n.title}<small>{n.source}</small></a>)}</div></div></section>
          <section className="panel block"><h2>İşlem bölgeleri</h2><div className="level"><span>Kademeli alım</span><b>{money(buy[0])} – {money(buy[1])}</b></div><div className="level"><span>Kâr alma</span><b>{money(sell[0])} – {money(sell[1])}</b></div><div className="level danger"><span>Risk kesme</span><b>{money(stop)}</b></div><label className="risk">Portföy (USD)<input value={capital} onChange={e=>setCapital(+e.target.value)} type="number"/></label><label className="risk">Risk (%)<input value={riskPct} onChange={e=>setRiskPct(+e.target.value)} type="number" step=".1"/></label><div className="position">Örnek azami pozisyon <b>{units.toFixed(3)} PAXG · {money(units*entry)}</b></div></section></div>
        <footer>Karar destek ve araştırma aracıdır; kâr garantisi veya kişisel yatırım tavsiyesi değildir.</footer>
      </section></div>
  </main>;
}

export default App;
