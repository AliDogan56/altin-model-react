import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

/** Native disclosure works with touch, keyboard and screen readers. */
export default function InfoTooltip({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  const ref = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  const close = () => { if (ref.current) ref.current.open = false; };
  useEffect(() => {
    if (!open) return;
    const pointer = (event: PointerEvent) => { if (!ref.current?.contains(event.target as Node)) close(); };
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') { close(); ref.current?.querySelector('summary')?.focus(); } };
    document.addEventListener('pointerdown', pointer);
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('pointerdown', pointer); document.removeEventListener('keydown', key); };
  }, [open]);
  return <details className="info-tooltip" ref={ref} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary aria-label={`${label} hakkında bilgi`} aria-controls={id}>i</summary>
    <div id={id} role="note"><b>{label}</b><button type="button" className="info-close" aria-label="Bilgiyi kapat" onClick={() => { close(); ref.current?.querySelector('summary')?.focus(); }}>×</button><p>{children}</p></div>
  </details>;
}
