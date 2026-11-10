import { useState } from 'react';
import { Button, ErrorBox, inputClass, Notice, PageHeader, Section, Table } from '../components/ui.tsx';
import { api, exportUrl } from '../lib/api.ts';
import { bytes } from '../lib/format.ts';
import { useAsync } from '../lib/useAsync.ts';

const FORMATS: { id: string; label: string; description: string; needsExperiment?: boolean }[] = [
  {
    id: 'jsonl',
    label: 'Raw run records (JSONL)',
    description: 'One JSON object per run, including retries, failed and invalidated runs, with evaluation history.',
  },
  {
    id: 'csv',
    label: 'Normalised results (CSV)',
    description: 'One row per run with every field in the data dictionary. Filter on is_effective_run and eligible_for_success.',
  },
  {
    id: 'config',
    label: 'Experiment configuration (JSON)',
    description: 'Frozen configuration, task versions, prompt hashes and the planned attempt matrix.',
  },
  {
    id: 'summary_csv',
    label: 'Summary tables (CSV)',
    description: 'Overall, per assistant, per category and per assistant × category aggregates with sample sizes.',
  },
  { id: 'dictionary', label: 'Data dictionary (JSON)', description: 'Definition of every exported field.' },
  { id: 'dictionary_md', label: 'Data dictionary (Markdown)', description: 'The same dictionary as a table for the report appendix.' },
  {
    id: 'manifest',
    label: 'Reproducibility manifest (JSON)',
    description: 'Platform, evaluator, tool, assistant and task versions observed in the data.',
  },
  {
    id: 'bundle',
    label: 'Team exchange bundle (JSON)',
    description: 'Complete, checksummed records of one experiment for merging on another machine.',
    needsExperiment: true,
  },
];

export function Exports() {
  const experiments = useAsync(() => api.experiments(), []);
  const [experimentId, setExperimentId] = useState('');
  const [written, setWritten] = useState<{ directory: string; files: { name: string; bytes: number; sha256: string }[] }>();
  const [importResult, setImportResult] = useState<string>();
  const [error, setError] = useState<Error>();
  return (
    <>
      <PageHeader title="Exports and data">
        Exports contain only recorded data. No demonstration or fabricated values are included in any file.
      </PageHeader>
      <label className="mb-6 block max-w-md text-sm">
        <span className="mb-1 block font-medium">Experiment</span>
        <select className={inputClass} value={experimentId} onChange={(e) => setExperimentId(e.target.value)}>
          <option value="">All experiments</option>
          {experiments.data?.experiments.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
      </label>
      {error ? (
        <div className="mb-4">
          <ErrorBox error={error} />
        </div>
      ) : null}
      <Section title="Download">
        <ul className="divide-y divide-rule rounded border border-rule bg-panel">
          {FORMATS.map((f) => {
            const disabled = f.needsExperiment && !experimentId;
            return (
              <li key={f.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="max-w-[70ch]">
                  <p className="font-medium">{f.label}</p>
                  <p className="text-sm text-ink-soft">
                    {disabled ? 'Select an experiment first. ' : ''}
                    {f.description}
                  </p>
                </div>
                {disabled ? (
                  <span className="text-sm text-ink-faint">Download</span>
                ) : (
                  <a
                    className="rounded border border-rule-strong px-3 py-1.5 text-sm font-medium hover:border-ink-faint"
                    href={exportUrl(f.id, experimentId || undefined)}
                  >
                    Download
                  </a>
                )}
              </li>
            );
          })}
        </ul>
        <div className="mt-4 flex items-center gap-3">
          <Button
            variant="primary"
            onClick={async () => {
              setError(undefined);
              try {
                setWritten(await api.exportAll(experimentId || undefined));
              } catch (e) {
                setError(e as Error);
              }
            }}
          >
            Write all exports to the artifacts folder
          </Button>
        </div>
        {written ? (
          <div className="mt-4">
            <p className="mb-2 text-sm">
              Written to <code className="break-all font-mono text-xs">{written.directory}</code>
            </p>
            <Table caption="Written files">
              <thead>
                <tr>
                  <th>File</th>
                  <th className="text-right">Size</th>
                  <th>SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {written.files.map((f) => (
                  <tr key={f.name}>
                    <td className="font-mono text-xs">{f.name}</td>
                    <td className="text-right text-xs">{bytes(f.bytes)}</td>
                    <td className="font-mono text-xs">{f.sha256.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        ) : null}
      </Section>
      <Section title="Import a team member's bundle">
        <p className="mb-3 max-w-[78ch] text-sm text-ink-soft">
          Records are matched by their IDs. Identical records are skipped, new ones are added and conflicting ones are reported and left
          untouched, so importing the same bundle twice never duplicates results.
        </p>
        <input
          type="file"
          accept="application/json,.json"
          className="text-sm"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setImportResult(undefined);
            setError(undefined);
            try {
              const res = await api.importBundle(JSON.parse(await file.text()));
              setImportResult(
                `Added ${JSON.stringify(res.inserted)}; skipped identical ${JSON.stringify(res.skippedIdentical)}; ${res.conflicts.length} conflicts.` +
                  (res.warnings.length ? ` ${res.warnings.join(' ')}` : ''),
              );
              experiments.reload();
            } catch (err) {
              setError(err as Error);
            }
          }}
        />
        {importResult ? (
          <div className="mt-3">
            <Notice tone="success">{importResult}</Notice>
          </div>
        ) : null}
      </Section>
    </>
  );
}
