import { useState } from 'react';
import { Button, CapabilityBadge, ErrorBox, Field, inputClass, Loading, Notice, PageHeader, Section } from '../components/ui.tsx';
import { api } from '../lib/api.ts';
import { assistantColor, dateTime } from '../lib/format.ts';
import type { Assistant } from '../lib/types.ts';
import { useAsync } from '../lib/useAsync.ts';

function AssistantCard({ a, onSaved }: { a: Assistant; onSaved: () => void }) {
  const [version, setVersion] = useState(a.operatorReportedVersion ?? '');
  const [model, setModel] = useState(a.operatorReportedModel ?? '');
  const [msg, setMsg] = useState<string>();
  return (
    <article className="border-l-4 bg-panel py-4 pl-5 pr-4" style={{ borderColor: assistantColor(a.id) }}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">{a.name}</h2>
        <CapabilityBadge status={a.capabilityStatus} />
      </div>
      <p className="text-sm text-ink-soft">{a.interface}</p>
      <p className="mt-2 max-w-[78ch] text-sm">{a.capabilityDetail}</p>
      <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-ink-soft">Detected CLI version</dt>
          <dd>{a.detectedVersion ?? 'not detected'}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Last checked</dt>
          <dd>{dateTime(a.checkedAt)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Documentation</dt>
          <dd>
            {a.docsUrl ? (
              <a className="text-action underline" href={a.docsUrl} target="_blank" rel="noreferrer">
                Vendor docs
              </a>
            ) : (
              '—'
            )}
          </dd>
        </div>
      </dl>
      <form
        className="mt-4 grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api.updateAssistant(a.id, version || null, model || null);
            setMsg('Saved. New runs will record this version.');
            onSaved();
          } catch (err) {
            setMsg((err as Error).message);
          }
        }}
      >
        <Field label="Version reported by the operator" hint="e.g. from Help, About or --version">
          <input className={inputClass} value={version} onChange={(e) => setVersion(e.target.value)} />
        </Field>
        <Field label="Model reported by the operator">
          <input className={inputClass} value={model} onChange={(e) => setModel(e.target.value)} />
        </Field>
        <Button type="submit">Save</Button>
      </form>
      {msg ? <p className="mt-2 text-sm text-ink-soft">{msg}</p> : null}
    </article>
  );
}

export function Assistants() {
  const state = useAsync(() => api.assistants(), []);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <PageHeader
        title="Assistants"
        actions={
          <Button
            busy={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api.detectAssistants();
                state.reload();
              } finally {
                setBusy(false);
              }
            }}
          >
            Check integrations again
          </Button>
        }
      >
        Capability is detected from installed command-line tools and credentials on this machine. Nothing is assumed: an assistant without a
        working headless CLI is run through the human-operated workflow.
      </PageHeader>
      <div className="mb-6">
        <Notice>
          Automated execution is off by default. Enable it with <code className="font-mono">ACB_ENABLE_AUTOMATION=1</code> only after
          checking each CLI by hand; see docs/assistant-integrations.md.
        </Notice>
      </div>
      {state.error ? <ErrorBox error={state.error} onRetry={state.reload} /> : null}
      {!state.data ? (
        <Loading label="Loading assistants" />
      ) : (
        <Section title="Configured assistants">
          <div className="space-y-4">
            {state.data.assistants.map((a) => (
              <AssistantCard key={a.id} a={a} onSaved={state.reload} />
            ))}
          </div>
        </Section>
      )}
    </>
  );
}
