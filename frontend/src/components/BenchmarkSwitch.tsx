import { BENCHMARKS } from '../lib/format.ts';

/**
 * Segmented control choosing which benchmark a page shows. `allowAll` adds an "All" option for views
 * where pooling is meaningful (task browsing); results pages pass a specific benchmark by default.
 */
export function BenchmarkSwitch({
  value,
  onChange,
  counts,
  allowAll = false,
}: {
  value: string;
  onChange: (v: string) => void;
  counts?: Record<string, number>;
  allowAll?: boolean;
}) {
  const options = [...(allowAll ? [{ id: '', label: 'All' }] : []), ...BENCHMARKS];
  return (
    <div role="radiogroup" aria-label="Benchmark" className="inline-flex rounded border border-rule bg-panel p-0.5 text-sm">
      {options.map((o) => {
        const active = value === o.id;
        const n = o.id ? counts?.[o.id] : counts ? Object.values(counts).reduce((a, b) => a + b, 0) : undefined;
        return (
          <button
            key={o.id || 'all'}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.id)}
            className={`rounded-sm px-3 py-1 ${active ? 'bg-ink text-paper' : 'text-ink-soft hover:text-ink'}`}
          >
            {o.label}
            {n !== undefined ? <span className={`ml-1.5 tabular text-xs ${active ? 'opacity-80' : 'text-ink-faint'}`}>{n}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
