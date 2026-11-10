/**
 * Charts drawn with D3 scales and plain SVG so they render identically in the browser and in
 * server-side component tests. Every chart states its denominator (n) next to the mark.
 */
import { max } from 'd3-array';
import { scaleBand, scaleLinear } from 'd3-scale';
import { assistantColor, axisDuration, duration, pct } from '../lib/format.ts';

export interface SuccessDatum {
  key: string;
  label: string;
  colorKey?: string;
  rate: number | null;
  low: number | null;
  high: number | null;
  successes: number;
  n: number;
}

const ROW = 30;
const LABEL_W = 150;
const RIGHT_W = 110;

/** Horizontal bars with Wilson 95% interval whiskers. Rows without completed runs show "no data". */
export function SuccessChart({ data, width = 640, title }: { data: SuccessDatum[]; width?: number; title: string }) {
  const height = data.length * ROW + 30;
  const x = scaleLinear()
    .domain([0, 1])
    .range([LABEL_W, width - RIGHT_W]);
  const y = scaleBand<string>()
    .domain(data.map((d) => d.key))
    .range([8, height - 22])
    .padding(0.3);
  return (
    <svg role="img" aria-label={title} viewBox={`0 0 ${width} ${height}`} className="w-full max-w-[720px]">
      <title>{title}</title>
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={4} y2={height - 20} stroke="var(--color-rule)" />
          <text x={x(t)} y={height - 6} textAnchor="middle" fontSize="11" fill="var(--color-ink-faint)">
            {t * 100}%
          </text>
        </g>
      ))}
      {data.map((d) => {
        const yy = y(d.key) ?? 0;
        const bh = y.bandwidth();
        const color = assistantColor(d.colorKey ?? d.key);
        return (
          <g key={d.key}>
            <text x={LABEL_W - 8} y={yy + bh / 2 + 4} textAnchor="end" fontSize="12" fill="var(--color-ink)">
              {d.label}
            </text>
            {d.rate === null ? (
              <text x={x(0) + 6} y={yy + bh / 2 + 4} fontSize="12" fill="var(--color-ink-faint)">
                no completed runs
              </text>
            ) : (
              <>
                <rect x={x(0)} y={yy} width={Math.max(1, x(d.rate) - x(0))} height={bh} fill={color} opacity={0.85} />
                {d.low !== null && d.high !== null ? (
                  <g stroke="var(--color-ink)" strokeWidth={1.25}>
                    <line x1={x(d.low)} x2={x(d.high)} y1={yy + bh / 2} y2={yy + bh / 2} />
                    <line x1={x(d.low)} x2={x(d.low)} y1={yy + 3} y2={yy + bh - 3} />
                    <line x1={x(d.high)} x2={x(d.high)} y1={yy + 3} y2={yy + bh - 3} />
                  </g>
                ) : null}
              </>
            )}
            <text x={width - RIGHT_W + 8} y={yy + bh / 2 + 4} fontSize="12" fill="var(--color-ink-soft)" className="tabular">
              {d.rate === null ? `n = ${d.n}` : `${pct(d.rate)} (${d.successes}/${d.n})`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export interface RangeDatum {
  key: string;
  label: string;
  n: number;
  min: number | null;
  q1: number | null;
  median: number | null;
  q3: number | null;
  max: number | null;
}

/** Box-and-whisker summary (min, quartiles, median, max) of wall-clock durations. */
export function RangeChart({ data, width = 640, title }: { data: RangeDatum[]; width?: number; title: string }) {
  const height = data.length * ROW + 30;
  const top = max(data, (d) => d.max ?? 0) ?? 0;
  const x = scaleLinear()
    .domain([0, top > 0 ? top : 1])
    .nice()
    .range([LABEL_W, width - RIGHT_W]);
  const y = scaleBand<string>()
    .domain(data.map((d) => d.key))
    .range([8, height - 22])
    .padding(0.35);
  return (
    <svg role="img" aria-label={title} viewBox={`0 0 ${width} ${height}`} className="w-full max-w-[720px]">
      <title>{title}</title>
      {x.ticks(5).map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={4} y2={height - 20} stroke="var(--color-rule)" />
          <text x={x(t)} y={height - 6} textAnchor="middle" fontSize="11" fill="var(--color-ink-faint)">
            {axisDuration(t, x.domain()[1])}
          </text>
        </g>
      ))}
      {data.map((d) => {
        const yy = y(d.key) ?? 0;
        const bh = y.bandwidth();
        const mid = yy + bh / 2;
        const ok = d.n > 0 && d.min !== null && d.q1 !== null && d.median !== null && d.q3 !== null && d.max !== null;
        return (
          <g key={d.key}>
            <text x={LABEL_W - 8} y={mid + 4} textAnchor="end" fontSize="12" fill="var(--color-ink)">
              {d.label}
            </text>
            {ok ? (
              <g>
                <line x1={x(d.min!)} x2={x(d.max!)} y1={mid} y2={mid} stroke="var(--color-ink-soft)" />
                <rect
                  x={x(d.q1!)}
                  y={yy}
                  width={Math.max(1, x(d.q3!) - x(d.q1!))}
                  height={bh}
                  fill={assistantColor(d.key)}
                  opacity={0.35}
                  stroke={assistantColor(d.key)}
                />
                <line x1={x(d.median!)} x2={x(d.median!)} y1={yy} y2={yy + bh} stroke="var(--color-ink)" strokeWidth={2} />
              </g>
            ) : (
              <text x={x(0) + 6} y={mid + 4} fontSize="12" fill="var(--color-ink-faint)">
                no completed runs
              </text>
            )}
            <text x={width - RIGHT_W + 8} y={mid + 4} fontSize="12" fill="var(--color-ink-soft)">
              {ok ? `median ${duration(d.median)} (n=${d.n})` : `n = ${d.n}`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export interface CountDatum {
  key: string;
  label: string;
  value: number | null;
  n: number;
  colorKey?: string;
}

/** Simple horizontal bars for means and counts; null values render as "no data". */
export function CountBars({
  data,
  width = 640,
  title,
  format = (v: number) => v.toFixed(1),
}: {
  data: CountDatum[];
  width?: number;
  title: string;
  format?: (v: number) => string;
}) {
  const height = data.length * ROW + 10;
  const top = max(data, (d) => d.value ?? 0) ?? 0;
  const x = scaleLinear()
    .domain([0, top > 0 ? top : 1])
    .range([LABEL_W, width - RIGHT_W]);
  const y = scaleBand<string>()
    .domain(data.map((d) => d.key))
    .range([4, height - 4])
    .padding(0.3);
  return (
    <svg role="img" aria-label={title} viewBox={`0 0 ${width} ${height}`} className="w-full max-w-[720px]">
      <title>{title}</title>
      {data.map((d) => {
        const yy = y(d.key) ?? 0;
        const bh = y.bandwidth();
        return (
          <g key={d.key}>
            <text x={LABEL_W - 8} y={yy + bh / 2 + 4} textAnchor="end" fontSize="12" fill="var(--color-ink)">
              {d.label}
            </text>
            {d.value === null ? (
              <text x={x(0) + 6} y={yy + bh / 2 + 4} fontSize="12" fill="var(--color-ink-faint)">
                no data
              </text>
            ) : (
              <rect
                x={x(0)}
                y={yy}
                width={Math.max(1, x(d.value) - x(0))}
                height={bh}
                fill={assistantColor(d.colorKey ?? d.key)}
                opacity={0.85}
              />
            )}
            <text x={width - RIGHT_W + 8} y={yy + bh / 2 + 4} fontSize="12" fill="var(--color-ink-soft)">
              {d.value === null ? `n = ${d.n}` : `${format(d.value)} (n=${d.n})`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
