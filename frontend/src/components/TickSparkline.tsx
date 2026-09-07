import type { Tick } from '../services/realtime/types';

function TickSparkline({ticks}:{ticks:Tick[]}) {
  if(ticks.length<2)return <div className="tick-empty">Saniyelik akış hazırlanıyor…</div>;
  const W=190,H=34,min=Math.min(...ticks.map(t=>t.price)),max=Math.max(...ticks.map(t=>t.price)),span=max-min||1;
  const pts=ticks.map((t,i)=>`${i/(ticks.length-1)*W},${H-3-(t.price-min)/span*(H-6)}`).join(' '),up=ticks[ticks.length-1].price>=ticks[0].price;
  return <svg className={`tick-spark ${up?'up':'down'}`} viewBox={`0 0 ${W} ${H}`} aria-label="Son saniyelerde ons fiyat hareketi"><polyline points={pts}/></svg>;
}

export default TickSparkline;
