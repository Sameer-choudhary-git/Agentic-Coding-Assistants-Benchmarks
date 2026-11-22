import { useEffect, useState } from 'react';
import {
  Button,
  ConfirmDialog,
  CopyButton,
  EmptyState,
  ErrorBox,
  Field,
  Hash,
  Info,
  inputClass,
  Loading,
  Notice,
  OutcomeBadge,
  PageHeader,
  Section,
  StatusBadge,
  Table,
} from '../components/ui.tsx';
import { api, artifactUrl } from '../lib/api.ts';
import {
  assistantName,
  bytes,
  categoryLabel,
  dateTime,
  duration,
  FAILURE_CLASS_LABEL,
  FAILURE_MODES,
  num,
  pct,
  STATUS_LABEL,
} from '../lib/format.ts';
import { Link } from '../lib/router.tsx';
import type { Evaluation, Run, RunDetail as Detail } from '../lib/types.ts';
import { useAsync } from '../lib/useAsync.ts';

function Elapsed({ since, limit }: { since: string; limit: number }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const s = Math.max(0, (now - Date.parse(since)) / 1000);
  const over = s > limit;
  return (
    <span className={`tabular text-3xl font-semibold ${over ? 'text-fail' : ''}`}>
      {duration(s)}
      <span className="ml-2 text-sm font-normal text-ink-soft">
        of {duration(limit)}
        {over ? ', over the limit' : ''}
      </span>
    </span>
  );
}

/** Step-by-step panel for the human-operated protocol. */
function Workflow({ d, onChange }: { d: Detail; onChange: () => void }) {
  const r = d.run;
  const swe = d.task?.kind === 'swebench';
  const [busy, setBusy] = useState<string>();
  const [err, setErr] = useState<string>();
  const [version, setVersion] = useState(d.assistant?.operatorReportedVersion ?? d.assistant?.detectedVersion ?? '');
  const [model, setModel] = useState(d.assistant?.operatorReportedModel ?? '');
  const [note, setNote] = useState('');
  const [mode, setMode] = useState<'workspace' | 'patch'>('workspace');
  const [patch, setPatch] = useState('');
  const [iterations, setIterations] = useState<string>('');
  const [interventions, setInterventions] = useState<string>('');
  const [notes, setNotes] = useState('');
  useEffect(() => {
    setIterations(r.iterations === null ? '' : String(r.iterations));
    setInterventions(r.humanInterventions === null ? '' : String(r.humanInterventions));
  }, [r.iterations, r.humanInterventions]);
  const act = async (name: string, fn: () => Promise<unknown>) => {
    setBusy(name);
    setErr(undefined);
    try {
      await fn();
      onChange();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(undefined);
    }
  };
  const step = (n: number, title: string, active: boolean, done: boolean, body: React.ReactNode) => (
    <li className={`border-l-2 py-3 pl-4 ${active ? 'border-action' : done ? 'border-pass' : 'border-rule'}`}>
      <p className={`text-sm font-semibold ${active ? '' : 'text-ink-soft'}`}>
        Step {n}. {title} {done ? <span className="font-normal text-pass">done</span> : null}
      </p>
      {active ? <div className="mt-2 space-y-3 text-sm">{body}</div> : null}
    </li>
  );
  const editor = r.assistantId === 'cursor' ? 'cursor' : r.assistantId === 'copilot' ? 'code' : null;
  const order = ['planned', 'ready', 'running', 'awaiting_human', 'submitted', 'evaluating', 'completed'];
  const at = order.indexOf(r.status);
  const autoAvailable = d.assistant?.capabilityStatus === 'supported';
  return (
    <Section title="Human-operated workflow" aside="Follow the protocol in docs/experimental-protocol.md">
      {err ? (
        <div className="mb-3">
          <ErrorBox error={new Error(err)} />
        </div>
      ) : null}
      <ol>
        {step(
          1,
          'Create a clean workspace',
          r.status === 'planned',
          at > 0,
          <>
            <p>
              {swe
                ? "Clones the issue's real repository at its base commit into a new folder outside this project and saves the issue text as ISSUE.md. Large repositories can take a few minutes."
                : "Copies the task's starter files into a new folder outside the repository and records a starter commit."}
            </p>
            <Button variant="primary" busy={busy === 'prepare'} onClick={() => act('prepare', () => api.prepare(r.id))}>
              Create workspace
            </Button>
          </>,
        )}
        {step(
          2,
          'Open the workspace and start the session',
          r.status === 'ready',
          at > 1,
          <>
            <p>
              Workspace: <code className="break-all font-mono text-xs">{r.workspacePath}</code>{' '}
              {r.workspacePath ? <CopyButton text={r.workspacePath} label="Copy path" /> : null}
            </p>
            {editor && r.workspacePath ? (
              <p>
                Open it with{' '}
                <code className="font-mono text-xs">
                  {editor} "{r.workspacePath}"
                </code>
                .
              </p>
            ) : (
              <p>Open a terminal in this folder and launch the assistant there.</p>
            )}
            <p className="text-ink-soft">{d.assistant?.manualInstructions}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Assistant version" hint="As shown by the tool. Leave empty if unknown; it is never guessed.">
                <input className={inputClass} value={version} onChange={(e) => setVersion(e.target.value)} />
              </Field>
              <Field label="Model (if shown)">
                <input className={inputClass} value={model} onChange={(e) => setModel(e.target.value)} />
              </Field>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                busy={busy === 'start'}
                onClick={() => act('start', () => api.start(r.id, { assistantVersion: version || undefined, model: model || undefined }))}
              >
                Start session timer
              </Button>
              {autoAvailable ? (
                <Button busy={busy === 'automate'} onClick={() => act('automate', () => api.automate(r.id))}>
                  Run headless CLI instead
                </Button>
              ) : null}
            </div>
          </>,
        )}
        {step(
          3,
          'Give the frozen prompt to the assistant and record activity',
          r.status === 'running',
          at > 2,
          <>
            {r.startedAt ? <Elapsed since={r.startedAt} limit={r.timeLimitSeconds} /> : null}
            <div className="flex flex-wrap gap-2">
              <CopyButton text={d.prompt} label="Copy frozen prompt" />
            </div>
            <p className="text-ink-soft">
              Iterations so far: <strong className="text-ink">{r.iterations ?? 0}</strong>. Human interventions:{' '}
              <strong className="text-ink">{r.humanInterventions ?? 0}</strong>.
              <Info>
                Iteration: each prompt you send to the assistant, including the first. Intervention: any human action other than sending a
                prompt: approving a permission request, editing code yourself, giving a hint that is not in the frozen prompt, or restarting
                the tool.
              </Info>
            </p>
            <Field label="Note for the log (optional)">
              <input
                className={inputClass}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. asked it to rerun the tests"
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button
                busy={busy === 'iteration'}
                onClick={() =>
                  act('iteration', async () => {
                    await api.log(r.id, 'iteration', note);
                    setNote('');
                  })
                }
              >
                Log follow-up prompt
              </Button>
              <Button
                busy={busy === 'intervention'}
                onClick={() =>
                  act('intervention', async () => {
                    await api.log(r.id, 'intervention', note);
                    setNote('');
                  })
                }
              >
                Log intervention
              </Button>
              <Button variant="primary" busy={busy === 'stop'} onClick={() => act('stop', () => api.stop(r.id))}>
                Stop timer
              </Button>
            </div>
          </>,
        )}
        {step(
          4,
          'Submit the result',
          r.status === 'awaiting_human' || r.status === 'running',
          at > 3,
          <>
            <p>
              Session duration: <strong>{duration(r.wallClockSeconds)}</strong>
              {r.timedOut ? <span className="ml-2 text-fail">over the time limit; this attempt will count as not passed</span> : null}
            </p>
            <fieldset className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2">
                <input type="radio" checked={mode === 'workspace'} onChange={() => setMode('workspace')} /> Use the files in the workspace
                folder
              </label>
              <label className="flex items-center gap-2">
                <input type="radio" checked={mode === 'patch'} onChange={() => setMode('patch')} /> Paste a unified diff
              </label>
            </fieldset>
            {mode === 'patch' ? (
              <Field label="Patch (git diff format)" hint="Applied with git apply. Paths must stay inside the workspace.">
                <textarea className={`${inputClass} font-mono text-xs`} rows={8} value={patch} onChange={(e) => setPatch(e.target.value)} />
              </Field>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Iterations (final)">
                <input type="number" min={0} className={inputClass} value={iterations} onChange={(e) => setIterations(e.target.value)} />
              </Field>
              <Field label="Human interventions (final)">
                <input
                  type="number"
                  min={0}
                  className={inputClass}
                  value={interventions}
                  onChange={(e) => setInterventions(e.target.value)}
                />
              </Field>
            </div>
            <Field label="Notes">
              <textarea className={inputClass} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Field>
            <Button
              variant="primary"
              busy={busy === 'submit'}
              disabled={mode === 'patch' && !patch.trim()}
              onClick={() =>
                act('submit', () =>
                  api.submit(r.id, {
                    submissionType: mode,
                    patch: mode === 'patch' ? patch : undefined,
                    iterations: iterations === '' ? undefined : Number(iterations),
                    humanInterventions: interventions === '' ? undefined : Number(interventions),
                    notes: notes || undefined,
                  }),
                )
              }
            >
              Submit and evaluate
            </Button>
          </>,
        )}
        {step(
          5,
          'Evaluation',
          r.status === 'submitted' || r.status === 'evaluating',
          at > 5,
          <>
            {r.status === 'evaluating' ? (
              <p role="status">
                {swe
                  ? 'Running the official SWE-bench harness in Docker (FAIL_TO_PASS and PASS_TO_PASS tests). The first run for a repository builds its Docker image and can take 20 minutes or more.'
                  : 'Running hidden acceptance and regression tests, Ruff and Semgrep…'}
              </p>
            ) : (
              <p>The submission is stored but not evaluated yet.</p>
            )}
            {r.status === 'submitted' ? (
              <Button variant="primary" busy={busy === 'evaluate'} onClick={() => act('evaluate', () => api.evaluate(r.id))}>
                Evaluate now
              </Button>
            ) : null}
          </>,
        )}
      </ol>
    </Section>
  );
}

const SWE_SUITE: Record<string, string> = { acceptance: 'FAIL_TO_PASS', regression: 'PASS_TO_PASS' };

function Results({ d }: { d: Detail }) {
  const e = d.latestEvaluation;
  if (!e) return null;
  const swe = d.task?.kind === 'swebench';
  const tests = d.testOutcomes;
  const ruff = d.findings.filter((f) => f.tool === 'ruff');
  const semgrep = d.findings.filter((f) => f.tool === 'semgrep');
  return (
    <>
      <Section title="Evaluation" aside={`Evaluator ${e.evaluatorVersion ?? '—'}, ${e.evalMode} mode, finished ${dateTime(e.finishedAt)}`}>
        {e.status === 'error' ? (
          <Notice tone="warn">
            Evaluator failure ({e.errorClass}): {e.errorMessage}. This is an operational failure, not a task result. Fix the cause and
            re-evaluate.
          </Notice>
        ) : (
          <dl className="grid grid-cols-2 gap-x-8 gap-y-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-ink-soft">{swe ? 'FAIL_TO_PASS passed' : 'Acceptance'}</dt>
              <dd className="tabular text-xl font-semibold">
                {e.acceptancePassed ?? '—'} / {e.acceptanceExpected ?? e.acceptanceTotal ?? '—'}
              </dd>
            </div>
            <div>
              <dt className="text-ink-soft">{swe ? 'PASS_TO_PASS failures' : 'Regression failures'}</dt>
              <dd className="tabular text-xl font-semibold">
                {e.regressionTotal ? (e.regressionFailed ?? 0) + (e.regressionErrors ?? 0) : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-ink-soft">Ruff findings (new)</dt>
              <dd className="tabular text-xl font-semibold">
                {e.ruffStatus === 'ran' ? `${e.ruffCount} (${e.ruffNew})` : e.ruffStatus === 'not_applicable' ? 'not run' : e.ruffStatus}
              </dd>
            </div>
            <div>
              <dt className="text-ink-soft">Semgrep findings (new)</dt>
              <dd className="tabular text-xl font-semibold">
                {e.semgrepStatus === 'ran'
                  ? `${e.semgrepCount} (${e.semgrepNew})`
                  : e.semgrepStatus === 'not_applicable'
                    ? 'not run'
                    : e.semgrepStatus}
              </dd>
            </div>
            <div>
              <dt className="text-ink-soft">Files changed</dt>
              <dd className="tabular">
                {e.filesChanged ?? '—'} (+{e.linesAdded ?? 0} / −{e.linesRemoved ?? 0})
              </dd>
            </div>
            <div>
              <dt className="text-ink-soft">Outside task scope</dt>
              <dd className={`tabular ${e.outOfScopeCount ? 'text-fail' : ''}`}>{e.outOfScopeCount ?? '—'} files</dd>
            </div>
            {e.lineCoverage !== null ? (
              <div>
                <dt className="text-ink-soft">Line coverage</dt>
                <dd className="tabular">{pct(e.lineCoverage, 1)}</dd>
              </div>
            ) : null}
            {e.mutationScore !== null ? (
              <div>
                <dt className="text-ink-soft">Mutants detected</dt>
                <dd className="tabular">{pct(e.mutationScore, 0)}</dd>
              </div>
            ) : null}
          </dl>
        )}
        {e && e.qualityStatus && e.qualityStatus !== 'not_applicable' ? <PatchQuality e={e} /> : null}
      </Section>
      {tests.length ? (
        <Section title="Test outcomes">
          <Table caption="Test outcomes">
            <thead>
              <tr>
                <th>Suite</th>
                <th>Test</th>
                <th>Outcome</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((t, i) => (
                <tr key={`${t.suite}-${t.test_id}-${i}`}>
                  <td className={swe ? 'font-mono text-xs' : 'capitalize'}>{swe ? (SWE_SUITE[t.suite] ?? t.suite) : t.suite}</td>
                  <td className="font-mono text-xs">{t.test_id}</td>
                  <td
                    className={t.outcome === 'passed' ? 'text-pass' : t.outcome === 'skipped' ? 'text-ink-faint' : 'font-medium text-fail'}
                  >
                    {t.outcome}
                  </td>
                  <td className="max-w-md truncate text-xs text-ink-soft" title={t.message ?? ''}>
                    {t.message}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Section>
      ) : null}
      {swe ? (
        <Section title="Scoring rule">
          <p className="text-sm text-ink-soft">
            Scored by the official SWE-bench harness: resolved only if every FAIL_TO_PASS and PASS_TO_PASS test passes. Ruff and Semgrep are
            not run on SWE-bench repositories, which carry their own pre-existing findings.
          </p>
        </Section>
      ) : null}
      {swe ? null : (
        <Section title="Static analysis" aside="New = not present in the starter code">
          {ruff.length + semgrep.length === 0 ? (
            <p className="text-sm text-ink-soft">
              No findings recorded. Ruff: {e.ruffStatus ?? 'not run'}. Semgrep: {e.semgrepStatus ?? 'not run'}
              {e.semgrepStatus === 'unavailable' ? ' (install Semgrep; unavailable is never counted as zero findings)' : ''}.
            </p>
          ) : (
            <Table caption="Findings">
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Rule</th>
                  <th>Location</th>
                  <th>Message</th>
                  <th>New</th>
                </tr>
              </thead>
              <tbody>
                {[...semgrep, ...ruff].map((f, i) => (
                  <tr key={i}>
                    <td>{f.tool}</td>
                    <td className="font-mono text-xs">
                      {f.rule_id}
                      {f.severity ? <span className="ml-1 text-ink-faint">{f.severity}</span> : null}
                    </td>
                    <td className="font-mono text-xs">
                      {f.path}:{f.line}
                    </td>
                    <td className="text-xs">{f.message}</td>
                    <td>
                      {f.is_new ? <span className="font-medium text-fail">new</span> : <span className="text-ink-faint">baseline</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Section>
      )}
    </>
  );
}

export function RunDetail({ id }: { id: string }) {
  const [poll, setPoll] = useState<number | null>(null);
  const state = useAsync(() => api.run(id), [id], poll);
  const [dialog, setDialog] = useState<'retry' | 'invalidate' | 'fail' | null>(null);
  const [failClass, setFailClass] = useState('environment_error');
  const [modes, setModes] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [reevalBusy, setReevalBusy] = useState(false);
  const [reevalError, setReevalError] = useState<string | null>(null);
  const status = state.data?.run.status;
  useEffect(() => setPoll(status === 'evaluating' || status === 'running' ? 2000 : null), [status]);
  useEffect(() => {
    if (state.data) setModes(state.data.run.failureModes);
  }, [state.data?.run.id, state.data?.run.updatedAt]);
  if (state.error && !state.data) return <ErrorBox error={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading label="Loading run" />;
  const d = state.data;
  const r: Run = d.run;
  const canFail = ['ready', 'running', 'awaiting_human', 'submitted'].includes(r.status);
  const canRetry = ['failed', 'invalidated'].includes(r.status) && d.siblings[d.siblings.length - 1]?.id === r.id;
  // An evaluator (tooling) failure keeps the operator's session and submission; score it again instead of
  // repeating the whole run.
  const canReevaluate = r.status === 'failed' && r.failureClass === 'evaluator_error' && Boolean(r.workspacePath);
  const reevaluate = async () => {
    setReevalBusy(true);
    setReevalError(null);
    try {
      await api.evaluate(r.id);
      state.reload();
    } catch (err) {
      setReevalError(err instanceof Error ? err.message : String(err));
    } finally {
      setReevalBusy(false);
    }
  };
  return (
    <>
      <PageHeader
        title={`${r.taskId} with ${assistantName(r.assistantId)}, attempt ${r.attemptNumber}`}
        crumbs={[
          { label: 'Experiments', to: '/experiments' },
          { label: r.experimentId.slice(0, 8), to: `/experiments/${r.experimentId}` },
          { label: `Run ${r.id.slice(0, 8)}` },
        ]}
        actions={
          <>
            <StatusBadge status={r.status} />
            <OutcomeBadge success={r.success} status={r.status} />
          </>
        }
      >
        {d.task ? `${d.task.title} (${categoryLabel(d.task.category)}, ${d.task.difficulty}).` : null} Run #{r.runNumber}
        {r.retryOfRunId ? (
          <>
            , retry of{' '}
            <Link to={`/runs/${r.retryOfRunId}`} className="text-action underline">
              {r.retryOfRunId.slice(0, 8)}
            </Link>
          </>
        ) : null}
        . {r.executionMode === 'automated' ? 'Executed by a headless CLI adapter.' : 'Human-operated.'}
      </PageHeader>

      {r.status === 'failed' ? (
        <div className="mb-6">
          <Notice tone="warn">
            <strong>{FAILURE_CLASS_LABEL[r.failureClass ?? ''] ?? 'Failed'}.</strong> {r.errorMessage} Operational failures are excluded
            from success rates.
            {r.failureClass === 'evaluator_error'
              ? ' Your session and submission are kept: fix the cause, then re-evaluate. There is no need to redo the run.'
              : ' Retry the attempt to create a new run; this record is kept.'}
          </Notice>
          {canReevaluate ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button variant="primary" busy={reevalBusy} onClick={reevaluate}>
                Re-evaluate submission
              </Button>
              <span className="text-sm text-ink-soft">Scores the same submission again. Time, prompts and interventions stay as recorded.</span>
            </div>
          ) : null}
          {reevalError ? <p className="mt-2 text-sm text-fail">{reevalError}</p> : null}
        </div>
      ) : null}
      {r.status === 'invalidated' ? (
        <div className="mb-6">
          <Notice tone="warn">Invalidated: {r.invalidationReason}</Notice>
        </div>
      ) : null}
      {r.status === 'completed' && !r.success ? (
        <div className="mb-6">
          <Notice>
            Result: {FAILURE_CLASS_LABEL[r.failureClass ?? ''] ?? 'did not pass'} ({r.outcome?.replace(/_/g, ' ')}). This is a measured task
            outcome.
          </Notice>
        </div>
      ) : null}

      {['planned', 'ready', 'running', 'awaiting_human', 'submitted', 'evaluating'].includes(r.status) ? (
        <Workflow d={d} onChange={state.reload} />
      ) : null}

      <Results d={d} />

      <div className="grid gap-8 lg:grid-cols-2">
        <Section title="Run record">
          <dl className="grid grid-cols-[10rem_1fr] gap-y-1.5 text-sm">
            <dt className="text-ink-soft">Status</dt>
            <dd>{STATUS_LABEL[r.status]}</dd>
            <dt className="text-ink-soft">Assistant version</dt>
            <dd>
              {r.assistantVersion ?? 'unknown'} <span className="text-ink-faint">({r.assistantVersionSource})</span>
            </dd>
            <dt className="text-ink-soft">Model</dt>
            <dd>{r.model ?? 'unknown'}</dd>
            <dt className="text-ink-soft">Workspace prepared</dt>
            <dd>{dateTime(r.preparedAt)}</dd>
            <dt className="text-ink-soft">Session</dt>
            <dd>
              {dateTime(r.startedAt)} to {dateTime(r.endedAt)}
            </dd>
            <dt className="text-ink-soft">Duration</dt>
            <dd>
              {duration(r.wallClockSeconds)} (limit {duration(r.timeLimitSeconds)})
            </dd>
            <dt className="text-ink-soft">Iterations</dt>
            <dd>{num(r.iterations)}</dd>
            <dt className="text-ink-soft">Interventions</dt>
            <dd>{num(r.humanInterventions)}</dd>
            <dt className="text-ink-soft">Submission</dt>
            <dd>
              {r.submissionKind ?? '—'} <Hash value={r.submissionHash} />
            </dd>
            <dt className="text-ink-soft">Prompt hash</dt>
            <dd>
              <Hash value={r.promptHash} />
            </dd>
            <dt className="text-ink-soft">Task hash</dt>
            <dd>
              <Hash value={r.taskHash} />
            </dd>
            <dt className="text-ink-soft">Evaluation mode</dt>
            <dd>{r.evalMode}</dd>
            <dt className="text-ink-soft">Operator</dt>
            <dd>
              {r.operator} on {r.machineId}
            </dd>
            <dt className="text-ink-soft">Notes</dt>
            <dd className="whitespace-pre-wrap">{r.notes || '—'}</dd>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            {canReevaluate ? (
              <Button variant="primary" busy={reevalBusy} onClick={reevaluate}>
                Re-evaluate submission
              </Button>
            ) : null}
            {canRetry ? <Button onClick={() => setDialog('retry')}>Retry attempt</Button> : null}
            {canFail ? (
              <Button variant="danger" onClick={() => setDialog('fail')}>
                Mark operational failure
              </Button>
            ) : null}
            {r.status !== 'invalidated' && r.status !== 'evaluating' ? (
              <Button variant="danger" onClick={() => setDialog('invalidate')}>
                Invalidate run
              </Button>
            ) : null}
          </div>
        </Section>
        <Section
          title="Failure-mode labels"
          aside={
            <Info>
              Assigned by researchers after reviewing the patch and logs. Used for the qualitative failure taxonomy; they never change
              success.
            </Info>
          }
        >
          <div className="grid gap-1 sm:grid-cols-2">
            {FAILURE_MODES.map((m) => (
              <label key={m.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={modes.includes(m.id)}
                  onChange={() => {
                    setSaved(false);
                    setModes(modes.includes(m.id) ? modes.filter((x) => x !== m.id) : [...modes, m.id]);
                  }}
                />
                {m.label}
              </label>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Button
              onClick={async () => {
                await api.label(r.id, { failureModes: modes });
                setSaved(true);
                state.reload();
              }}
            >
              Save labels
            </Button>
            {saved ? <span className="text-sm text-pass">Labels saved</span> : null}
          </div>
        </Section>
      </div>

      <Section title="Frozen prompt" aside={<CopyButton text={d.prompt} label="Copy" />}>
        <details>
          <summary className="cursor-pointer text-sm text-action">Show the prompt used for this run</summary>
          <pre className="mt-2 whitespace-pre-wrap rounded border border-rule bg-panel p-4 font-sans text-sm">{d.prompt}</pre>
        </details>
      </Section>

      <div className="grid gap-8 lg:grid-cols-2">
        <Section title="Artifacts">
          {d.artifacts.length === 0 ? (
            <EmptyState title="No artifacts yet">Patches, logs and evaluator reports appear after submission.</EmptyState>
          ) : (
            <ul className="divide-y divide-rule rounded border border-rule bg-panel text-sm">
              {d.artifacts.map((a) => (
                <li key={a.id} className="flex justify-between gap-2 px-3 py-1.5">
                  <a
                    href={artifactUrl(r.id, a.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="truncate font-mono text-xs text-action hover:underline"
                  >
                    {a.relativePath.split('/').slice(-1)[0]}
                  </a>
                  <span className="text-xs text-ink-faint">{bytes(a.sizeBytes)}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
        <Section title="Lifecycle">
          <ol className="space-y-1.5 text-sm">
            {d.events.map((e) => (
              <li key={e.id} className="flex justify-between gap-3">
                <span>
                  {e.type.replace(/_/g, ' ')}
                  {e.payload && typeof e.payload.note === 'string' && e.payload.note ? (
                    <span className="text-ink-soft">: {e.payload.note}</span>
                  ) : null}
                </span>
                <span className="whitespace-nowrap text-xs text-ink-faint">{dateTime(e.createdAt)}</span>
              </li>
            ))}
          </ol>
        </Section>
      </div>

      <ConfirmDialog
        open={dialog === 'retry'}
        title="Retry this attempt?"
        confirmLabel="Create retry"
        body={
          canReevaluate
            ? 'This run failed only because of an evaluator error, so "Re-evaluate submission" scores it again without a new session. Retry starts the attempt from scratch: a new workspace, timer and session. This run is kept and shown as superseded.'
            : 'Creates a new run for the same planned attempt. This run and its history are kept and shown as superseded.'
        }
        onClose={() => setDialog(null)}
        onConfirm={async () => {
          const res = await api.retry(r.id);
          window.history.pushState({}, '', `/runs/${res.run.id}`);
          window.dispatchEvent(new PopStateEvent('popstate'));
        }}
      />
      <ConfirmDialog
        open={dialog === 'invalidate'}
        title="Invalidate this run?"
        danger
        confirmLabel="Invalidate run"
        body="Use this when the protocol was violated (wrong prompt, contaminated workspace, wrong assistant). Invalidated runs are excluded from all metrics."
        reason={{ label: 'Reason', minLength: 5 }}
        onClose={() => setDialog(null)}
        onConfirm={async (reason) => {
          await api.invalidate(r.id, reason);
          state.reload();
        }}
      />
      <ConfirmDialog
        open={dialog === 'fail'}
        title="Mark as an operational failure?"
        danger
        confirmLabel="Mark failed"
        body={
          <>
            For problems unrelated to the assistant's ability (crash, lost session, tool outage). The run is excluded from success rates and
            can be retried.
            <select className={`${inputClass} mt-3`} value={failClass} onChange={(e) => setFailClass(e.target.value)}>
              <option value="environment_error">Environment failure</option>
              <option value="adapter_error">Adapter or tool failure</option>
              <option value="operator_abort">Aborted by operator</option>
            </select>
          </>
        }
        reason={{ label: 'What happened', minLength: 3 }}
        onClose={() => setDialog(null)}
        onConfirm={async (reason) => {
          await api.fail(r.id, failClass, reason);
          state.reload();
        }}
      />
    </>
  );
}

const QUALITY_DIMS = ['reliability', 'complexity', 'maintainability', 'security', 'hygiene', 'size'] as const;

/** Code quality of the submitted patch (evaluator/patch_quality.py, golden Code Quality Module). */
function PatchQuality({ e }: { e: Evaluation }) {
  const q = e.quality ?? {};
  if (e.qualityStatus !== 'ran') {
    return (
      <p className="mt-4 text-sm text-ink-soft">
        Patch code quality: {e.qualityStatus}
        {q.error ? ` (${String(q.error)})` : ''}
      </p>
    );
  }
  const issues: string[] = [];
  const list = (label: string, m: Record<string, number> | undefined) => {
    const parts = Object.entries(m ?? {}).map(([k, v]) => `${k}×${v}`);
    if (parts.length) issues.push(`${label}: ${parts.join(', ')}`);
  };
  list('new lint findings', q.lint_new);
  list('new security findings', q.bandit_new);
  list('insecure patterns', q.security_patterns);
  list('hygiene', q.smells);
  if (q.new_complex_functions?.length) issues.push(`new over-complex functions: ${q.new_complex_functions.join(', ')}`);
  if (q.stray_files?.length) issues.push(`stray scratch files: ${q.stray_files.join(', ')}`);
  const delta = e.qualityGoldScore !== null && e.qualityScore !== null ? e.qualityScore - e.qualityGoldScore : null;
  return (
    <div className="mt-6 border-t border-slate-200 pt-4">
      <h3 className="mb-2 text-sm font-semibold">Patch code quality</h3>
      <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-ink-soft">QualityScore</dt>
          <dd className="tabular text-xl font-semibold">{num(e.qualityScore, 1)} / 100</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Reference fix</dt>
          <dd className="tabular text-xl font-semibold">
            {e.qualityGoldScore !== null ? num(e.qualityGoldScore, 1) : '—'}
            {delta !== null ? <span className="ml-2 text-sm font-normal">({delta >= 0 ? '+' : ''}{num(delta, 1)})</span> : null}
          </dd>
        </div>
        <div>
          <dt className="text-ink-soft">Size vs reference</dt>
          <dd className="tabular">{q.size_ratio_vs_reference != null ? `${num(q.size_ratio_vs_reference, 2)}×` : '—'}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Tests added</dt>
          <dd>{q.tests_included ? 'yes' : 'no'}</dd>
        </div>
        {QUALITY_DIMS.map((d) => (
          <div key={d}>
            <dt className="capitalize text-ink-soft">{d}</dt>
            <dd className="tabular">{num(q.subscores?.[d], 0)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-sm text-ink-soft">
        {issues.length ? issues.join(' · ') : 'No new problems detected in the patch.'}
        {q.note ? ` (${q.note})` : ''}
      </p>
    </div>
  );
}
