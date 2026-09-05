import { useRef, type ReactNode } from 'react';

/** A single choice, with the same keyboard behavior as a native radio group. */
export default function SegmentedControl<T extends string | number>({ label, value, options, onChange }: {
  label: string; value: T; options: { value: T; label: ReactNode; disabled?: boolean }[]; onChange: (value: T) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  return <div className="segmented" role="radiogroup" aria-label={label} ref={ref}>
    {options.map((option, index) => <button key={option.value} type="button" role="radio"
      aria-checked={value === option.value} tabIndex={value === option.value ? 0 : -1}
      disabled={option.disabled} className={value === option.value ? 'active' : ''}
      onClick={() => onChange(option.value)} onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const enabled = options.map((item, i) => !item.disabled ? i : -1).filter(i => i >= 0);
        const next = event.key === 'Home' ? enabled[0] : event.key === 'End' ? enabled.at(-1)!
          : enabled[(enabled.indexOf(index) + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1) + enabled.length) % enabled.length];
        onChange(options[next].value);
        ref.current?.querySelectorAll('button')[next]?.focus();
      }}>{option.label}</button>)}
  </div>;
}
