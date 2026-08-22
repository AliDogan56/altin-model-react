import { emaSeries, sma, wilder } from './math';

export type Candle = { date: string; h: number; l: number; c: number };
export type IndicatorRow = { name: string; value: string; text: string; tone: string; note: string };
export type MovingAverage = { n: number; sma: number | null; ema: number | null; price: number };
export type Indicators = { rows: IndicatorRow[]; averages: MovingAverage[] };

/* Hepsi zaten çekilen günlük OHLC mumlarından hesaplanır, yeni veri kaynağı gerekmez.
   Bilinçli olarak "al/sat" kararı üretilmez; yalnız göstergenin bulunduğu durum yazılır. */
export function indicators(candles: Candle[]): Indicators | null {
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
  /* sma 20 gözlemden az veri varsa null döner; guard olmadan NaN yayılıyordu. */
  const tpMean=sma(tp,20) ?? tp[last];
  const dev=tp.slice(-20).reduce((s,v)=>s+Math.abs(v-tpMean),0)/20;
  const cci=dev?(tp[last]-tpMean)/(0.015*dev):0;

  const tr=[],plusDM=[],minusDM=[];
  for(let i=1;i<c.length;i++){
    tr.push(Math.max(h[i]-l[i],Math.abs(h[i]-c[i-1]),Math.abs(l[i]-c[i-1])));
    const up=h[i]-h[i-1], down=l[i-1]-l[i];
    plusDM.push(up>down&&up>0?up:0); minusDM.push(down>up&&down>0?down:0);}
  const n=14, trS=wilder(tr,n), pS=wilder(plusDM,n), mS=wilder(minusDM,n), dx=[];
  for(let i=n-1;i<tr.length;i++){
    const trValue=trS[i], plus=pS[i], minus=mS[i];
    if(!trValue||plus==null||minus==null) continue;
    const pdi=100*plus/trValue, mdi=100*minus/trValue, sum=pdi+mdi;
    dx.push(sum?100*Math.abs(pdi-mdi)/sum:0);}
  const adx=dx.length>=n?dx.slice(-n).reduce((s,v)=>s+v,0)/n:null;
  const lastTr=trS[tr.length-1], lastPlus=pS[tr.length-1], lastMinus=mS[tr.length-1];
  const pdiNow=lastTr&&lastPlus!=null?100*lastPlus/lastTr:0;
  const mdiNow=lastTr&&lastMinus!=null?100*lastMinus/lastTr:0;

  const atr=tr.slice(-14).reduce((s,v)=>s+v,0)/14, atrPct=atr/c[last]*100;
  const atrHist=[];
  for(let i=14;i<tr.length;i++) atrHist.push(tr.slice(i-14,i).reduce((s,v)=>s+v,0)/14/c[i]*100);
  const atrMed=[...atrHist].sort((a,b)=>a-b)[Math.floor(atrHist.length/2)]||atrPct;
  const roc=c[last-12]?(c[last]/c[last-12]-1)*100:0;

  const state=(text:string,tone:string)=>({text,tone});   // value döndürmüyor: yayılma sırasında gerçek değeri eziyordu
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
