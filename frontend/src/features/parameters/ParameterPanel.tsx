import { GROUPS } from '../../content/parameters';
import { useDashboard } from '../dashboard/DashboardContext';

function ParameterPanel() {
  const { values, setField, resetFields } = useDashboard();
  return (
    <aside className="panel controls">
    <h2>Güncel parametreler</h2>{GROUPS.map(([title,items])=>
    <section className="group" key={title}>
    <h3>{title}</h3>{items.map(([id,label,unit])=>
    <label key={id}><span>{label}{unit&&` (${unit})`}</span><input type="number" step="any" value={Number(values[id]).toFixed(id==='price'?2:3)} onChange={e=>setField(id,+e.target.value)}/></label>)}</section>)}<button className="primary" onClick={resetFields}>Eğitim değerlerine dön</button></aside>
  );
}

export default ParameterPanel;
