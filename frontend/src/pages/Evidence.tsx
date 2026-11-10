import { useState } from 'react';
import { ErrorBox, inputClass, Loading, Notice, PageHeader, Section, Table } from '../components/ui.tsx';
import { api, evidenceExportUrl } from '../lib/api.ts';
import type { EvidenceItem, EvidenceRegistry } from '../lib/types.ts';
import { useAsync } from '../lib/useAsync.ts';

export function formatEvidenceValue(i: EvidenceItem): string {
  if (i.value === null) return i.unit;
  const v = Number.isInteger(i.value) ? i.value.toLocaleString('en-US') : String(i.value);
  return i.unit === '%' ? `${v}%` : `${v} ${i.unit}`;
}

export function filterEvidence(items: EvidenceItem[], theme: string, q: string): EvidenceItem[] {
  const needle = q.trim().toLowerCase();
  return items.filter(
    (i) =>
      (!theme || i.theme === theme) &&
      (!needle || `${i.subject} ${i.metric} ${i.conditions} ${i.source}`.toLowerCase().includes(needle)),
  );
}

export function EvidenceView({ reg }: { reg: EvidenceRegistry }) {
  const [theme, setTheme] = useState('');
  const [q, setQ] = useState('');
  const bySource = new Map(reg.sources.map((s) => [s.id, s]));
  const items = filterEvidence(reg.items, theme, q);
  const cautioned = reg.sources.filter((s) => s.cautions.length);
  return (
    <>
      <PageHeader
        title="Literature evidence"
        actions={
          <>
            <a className="rounded border border-rule bg-panel px-3 py-1.5 text-sm hover:border-action" href={evidenceExportUrl('csv')}>
              Download CSV
            </a>
            <a className="rounded border border-rule bg-panel px-3 py-1.5 text-sm hover:border-action" href={evidenceExportUrl('latex')}>
              Download LaTeX table
            </a>
          </>
        }
      >
        Published figures the paper cites, each linked to its source. These are secondary data reported by other studies, not results
        measured on this platform. Checked against the sources on {reg.checkedOn}.
      </PageHeader>

      <Section title="Assistant features" aside={`Vendor documentation, checked ${reg.features.checkedOn}`}>
        <Table caption="Feature comparison of the four assistants">
          <thead>
            <tr>
              <th scope="col">Assistant</th>
              <th scope="col">Interaction modes</th>
              <th scope="col">Autonomy</th>
              <th scope="col">Context</th>
              <th scope="col">Execution</th>
              <th scope="col">Pull request output</th>
            </tr>
          </thead>
          <tbody>
            {reg.features.assistants.map((a) => (
              <tr key={a.id} className="align-top">
                <th scope="row" className="font-medium text-ink">
                  {a.name}
                  <span className="block text-xs font-normal text-ink-faint">{a.vendor}</span>
                </th>
                <td>{a.interactionModes.join('; ')}</td>
                <td className="whitespace-nowrap">{a.autonomy.join(', ')}</td>
                <td>{a.context}</td>
                <td>{a.execution}</td>
                <td>
                  {a.prOutput}
                  {a.note ? <span className="mt-1 block text-xs text-ink-faint">{a.note}</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
        <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          {Object.entries(reg.features.autonomyScale).map(([k, v]) => (
            <div key={k}>
              <dt className="inline font-medium">{k}</dt> <dd className="inline text-ink-soft">{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Published figures" aside={`${items.length} of ${reg.items.length} shown`}>
        <div className="mb-3 flex flex-wrap gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-ink-soft">Paper section</span>
            <select className={inputClass} value={theme} onChange={(e) => setTheme(e.target.value)}>
              <option value="">All sections</option>
              {Object.entries(reg.themes).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-ink-soft">Search</span>
            <input className={inputClass} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Agent, metric or source" />
          </label>
        </div>
        <Table caption="Published figures">
          <thead>
            <tr>
              <th scope="col">Subject</th>
              <th scope="col">Metric</th>
              <th scope="col" className="text-right">
                Value
              </th>
              <th scope="col">Conditions</th>
              <th scope="col">Source</th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => {
              const s = bySource.get(i.source);
              return (
                <tr key={i.id} className="align-top">
                  <td>{i.subject}</td>
                  <td>{i.metric}</td>
                  <td className="whitespace-nowrap text-right tabular-nums">
                    {formatEvidenceValue(i)}
                    {i.n ? <span className="block text-xs text-ink-faint">n = {i.n.toLocaleString('en-US')}</span> : null}
                  </td>
                  <td className="text-ink-soft">{i.conditions}</td>
                  <td>
                    {s ? (
                      <a className="text-action underline" href={s.url} target="_blank" rel="noreferrer" title={s.title}>
                        {s.authors[0].split(' ').slice(-1)[0]} {s.year}
                      </a>
                    ) : (
                      i.source
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      </Section>

      <Section title="Quoting cautions" aside={`${cautioned.length} sources need care`}>
        <Notice tone="warn">These inconsistencies were found while checking the sources. Quote the version named here.</Notice>
        <ul className="mt-3 space-y-2 text-sm">
          {cautioned.map((s) => (
            <li key={s.id}>
              <span className="font-medium">{s.title}</span>
              <ul className="ml-5 list-disc text-ink-soft">
                {s.cautions.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

export function Evidence() {
  const { data, error, loading, reload } = useAsync(() => api.evidence(), []);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading || !data) return <Loading />;
  return <EvidenceView reg={data} />;
}
