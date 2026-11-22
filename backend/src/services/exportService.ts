import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import { type Config, PLATFORM_VERSION } from '../config.ts';
import type { Database, Row } from '../db/database.ts';
import { badRequest, notFound } from '../lib/errors.ts';
import { sha256, toCsv } from '../lib/util.ts';
import type { Repositories } from '../repositories/repositories.ts';
import { DATA_DICTIONARY, ResultsService } from './resultsService.ts';

export const EXPORT_FORMATS = ['jsonl', 'csv', 'config', 'summary_csv', 'dictionary', 'dictionary_md', 'manifest', 'bundle'] as const;
export type ExportFormat = (typeof EXPORT_FORMATS)[number];

const BUNDLE_VERSION = 1;

export const bundleSchema = z.object({
  bundleVersion: z.literal(BUNDLE_VERSION),
  platformVersion: z.string(),
  exportedAt: z.string(),
  exportedBy: z.string(),
  machineId: z.string(),
  checksum: z.string().length(64),
  data: z.object({
    experiments: z.array(z.record(z.unknown())).length(1),
    planned_attempts: z.array(z.record(z.unknown())),
    runs: z.array(z.record(z.unknown())),
    evaluations: z.array(z.record(z.unknown())),
    test_outcomes: z.array(z.record(z.unknown())),
    findings: z.array(z.record(z.unknown())),
    events: z.array(z.record(z.unknown())),
  }),
});
export type Bundle = z.infer<typeof bundleSchema>;

function gitCommit(repoRoot: string): string | null {
  try {
    const head = fs.readFileSync(path.join(repoRoot, '.git', 'HEAD'), 'utf8').trim();
    if (!head.startsWith('ref:')) return head;
    const ref = head.slice(4).trim();
    const file = path.join(repoRoot, '.git', ref);
    return fs.existsSync(file) ? fs.readFileSync(file, 'utf8').trim() : null;
  } catch {
    return null;
  }
}

export class ExportService {
  constructor(
    private readonly cfg: Config,
    private readonly db: Database,
    private readonly repos: Repositories,
    private readonly results: ResultsService,
  ) {}

  /** Returns [filename, content-type, body]. */
  render(format: ExportFormat, experimentId?: string): [string, string, string] {
    if (experimentId && !this.repos.experiments.get(experimentId)) throw notFound(`experiment ${experimentId}`);
    const suffix = experimentId ? experimentId.slice(0, 8) : 'all';
    const records = () => this.results.flatRecords(experimentId);
    switch (format) {
      case 'jsonl': {
        const lines = records().map((r) => {
          const evaluations = this.repos.evaluations.forRun(r.run_id).map((e) => ({
            id: e.id,
            status: e.status,
            success: e.success,
            outcome: e.outcome,
            errorClass: e.errorClass,
            evaluatorVersion: e.evaluatorVersion,
            evalMode: e.evalMode,
            toolVersions: e.toolVersions,
            finishedAt: e.finishedAt,
          }));
          return JSON.stringify({ ...r, evaluations });
        });
        return [`runs-${suffix}.jsonl`, 'application/x-ndjson', lines.length ? `${lines.join('\n')}\n` : ''];
      }
      case 'csv':
        return [
          `results-${suffix}.csv`,
          'text/csv',
          toCsv(
            DATA_DICTIONARY.map((d) => d.field),
            records() as unknown as Record<string, unknown>[],
          ),
        ];
      case 'config': {
        const experiments = experimentId ? [this.repos.experiments.get(experimentId)!] : this.repos.experiments.list();
        const body = experiments.map((e) => ({ ...e, plannedAttempts: this.repos.experiments.planned(e.id) }));
        return [`experiment-config-${suffix}.json`, 'application/json', JSON.stringify(experimentId ? body[0] : body, null, 2)];
      }
      case 'summary_csv':
        return [`summary-${suffix}.csv`, 'text/csv', this.summaryCsv(experimentId)];
      case 'dictionary':
        return ['data-dictionary.json', 'application/json', JSON.stringify(DATA_DICTIONARY, null, 2)];
      case 'dictionary_md':
        return ['data-dictionary.md', 'text/markdown', this.dictionaryMarkdown()];
      case 'manifest':
        return [`manifest-${suffix}.json`, 'application/json', JSON.stringify(this.manifest(experimentId), null, 2)];
      case 'bundle':
        if (!experimentId) throw badRequest('bundle export requires experimentId');
        return [`bundle-${suffix}.json`, 'application/json', JSON.stringify(this.bundle(experimentId), null, 2)];
      default:
        throw badRequest(`unknown format ${format}`);
    }
  }

  summaryCsv(experimentId?: string): string {
    const s = this.results.summary(experimentId);
    const columns = [
      'group_level',
      'assistant_id',
      'category',
      'planned',
      'completed',
      'successes',
      'success_rate',
      'ci95_low',
      'ci95_high',
      'intent_to_treat_rate',
      'not_started',
      'in_progress',
      'operational_failures',
      'invalidated',
      'timeouts',
      'retries',
      'regression_failures',
      'regression_denominator',
      'duration_n',
      'duration_median_s',
      'duration_mean_s',
      'duration_q1_s',
      'duration_q3_s',
      'iterations_mean',
      'interventions_mean',
      'ruff_n',
      'ruff_new_mean',
      'ruff_unavailable',
      'semgrep_n',
      'semgrep_new_total',
      'semgrep_runs_with_new',
      'semgrep_unavailable',
      'quality_n',
      'quality_mean',
      'quality_mean_resolved',
      'quality_n_resolved',
      'quality_mean_delta_vs_gold',
      'quality_unavailable',
      'exploratory',
    ];
    const row = (
      level: string,
      assistant: string | null,
      category: string | null,
      a: ReturnType<typeof ResultsService.aggregate>,
      exploratory: boolean,
    ) => ({
      group_level: level,
      assistant_id: assistant,
      category,
      planned: a.planned,
      completed: a.completed,
      successes: a.successes,
      success_rate: a.successRate,
      ci95_low: a.successCi95?.low ?? null,
      ci95_high: a.successCi95?.high ?? null,
      intent_to_treat_rate: a.intentToTreatRate,
      not_started: a.notStarted,
      in_progress: a.inProgress,
      operational_failures: a.operationalFailures,
      invalidated: a.invalidated,
      timeouts: a.timeouts,
      retries: a.retries,
      regression_failures: a.regressionFailures,
      regression_denominator: a.regressionDenominator,
      duration_n: a.duration.n,
      duration_median_s: a.duration.median,
      duration_mean_s: a.duration.mean,
      duration_q1_s: a.duration.q1,
      duration_q3_s: a.duration.q3,
      iterations_mean: a.iterations.mean,
      interventions_mean: a.interventions.mean,
      ruff_n: a.ruff.n,
      ruff_new_mean: a.ruff.newMean,
      ruff_unavailable: a.ruff.unavailable,
      semgrep_n: a.semgrep.n,
      semgrep_new_total: a.semgrep.newTotal,
      semgrep_runs_with_new: a.semgrep.runsWithNewFindings,
      semgrep_unavailable: a.semgrep.unavailable,
      quality_n: a.quality.n,
      quality_mean: a.quality.meanScore,
      quality_mean_resolved: a.quality.meanScoreResolved,
      quality_n_resolved: a.quality.nResolved,
      quality_mean_delta_vs_gold: a.quality.meanDeltaVsGold,
      quality_unavailable: a.quality.unavailable,
      exploratory,
    });
    const rows = [
      row('overall', null, null, s.overall, false),
      ...s.byAssistant.map((a) => row('assistant', a.assistantId, null, a, false)),
      ...s.byCategory.map((c) => row('category', null, c.category, c, true)),
      ...s.byAssistantCategory.map((c) => row('assistant_category', c.assistantId, c.category, c, true)),
    ];
    return toCsv(columns, rows);
  }

  dictionaryMarkdown(): string {
    const lines = ['| Field | Type | Description |', '|---|---|---|'];
    for (const d of DATA_DICTIONARY) lines.push(`| \`${d.field}\` | ${d.type} | ${d.description.replace(/\|/g, '\\|')} |`);
    return `${lines.join('\n')}\n`;
  }

  manifest(experimentId?: string) {
    const records = this.results.flatRecords(experimentId);
    const experiments = experimentId ? [this.repos.experiments.get(experimentId)!] : this.repos.experiments.list();
    const evaluatorVersions = new Set<string>();
    const toolVersions = new Map<string, unknown>();
    for (const r of records) {
      if (!r.evaluation_id) continue;
      const ev = this.repos.evaluations.get(r.evaluation_id);
      if (!ev) continue;
      if (ev.evaluatorVersion) evaluatorVersions.add(ev.evaluatorVersion);
      toolVersions.set(JSON.stringify(ev.toolVersions), ev.toolVersions);
    }
    const taskIds = new Set(experiments.flatMap((e) => this.repos.experiments.planned(e.id).map((p) => p.taskId)));
    return {
      generatedAt: new Date().toISOString(),
      platformVersion: PLATFORM_VERSION,
      gitCommit: gitCommit(this.cfg.repoRoot),
      node: process.version,
      os: `${process.platform}-${process.arch}`,
      databaseSchemaVersion: this.db.schemaVersion(),
      operator: this.cfg.ACB_OPERATOR,
      machineId: this.cfg.ACB_MACHINE_ID,
      experiments: experiments.map((e) => ({
        id: e.id,
        name: e.name,
        status: e.status,
        evalMode: e.evalMode,
        executionMode: e.executionMode,
        seed: e.seed,
        createdAt: e.createdAt,
      })),
      runCounts: {
        total: records.length,
        effective: records.filter((r) => r.is_effective_run).length,
        completedEffective: records.filter((r) => r.eligible_for_success).length,
      },
      evaluationModes: [...new Set(records.filter((r) => r.evaluation_id).map((r) => r.eval_mode))],
      executionModes: [...new Set(records.filter((r) => r.started_at).map((r) => r.execution_mode))],
      evaluatorVersions: [...evaluatorVersions],
      toolVersionsObserved: [...toolVersions.values()],
      assistantVersionsObserved: [
        ...new Set(
          records
            .filter((r) => r.assistant_version)
            .map((r) => `${r.assistant_id}: ${r.assistant_version} (${r.assistant_version_source})`),
        ),
      ],
      tasks: [...taskIds].sort().map((id) => {
        const t = this.repos.tasks.get(id);
        return t
          ? {
              id,
              version: t.version,
              testVersion: t.testVersion,
              taskHash: t.taskHash,
              promptHash: t.promptHash,
              validationStatus: t.validationStatus,
            }
          : { id, missing: true };
      }),
      demoDataIncluded: false,
    };
  }

  bundle(experimentId: string): Bundle {
    const exp = this.repos.experiments.get(experimentId);
    if (!exp) throw notFound(`experiment ${experimentId}`);
    const runs = this.db.all('SELECT * FROM runs WHERE experiment_id = ? ORDER BY id', experimentId);
    const runIds = runs.map((r) => String(r.id));
    const data = {
      experiments: this.repos.experiments.rawRows('experiments', experimentId),
      planned_attempts: this.repos.experiments.rawRows('planned_attempts', experimentId),
      runs,
      evaluations: this.repos.evaluations.rawRowsForRuns(runIds, 'evaluations'),
      test_outcomes: this.repos.evaluations.rawRowsForRuns(runIds, 'test_outcomes'),
      findings: this.repos.evaluations.rawRowsForRuns(runIds, 'findings'),
      events: this.repos.events.rawForExperiment(experimentId),
    };
    return {
      bundleVersion: BUNDLE_VERSION,
      platformVersion: PLATFORM_VERSION,
      exportedAt: new Date().toISOString(),
      exportedBy: this.cfg.ACB_OPERATOR,
      machineId: this.cfg.ACB_MACHINE_ID,
      checksum: sha256(JSON.stringify(data)),
      data: data as Bundle['data'],
    };
  }

  /**
   * Merge a bundle exported by a team member. Records are matched by their stable UUIDs:
   * identical records are skipped, new records are inserted and differing records are reported as
   * conflicts and never overwritten. Nothing is imported if the checksum does not match.
   */
  importBundle(raw: unknown) {
    const bundle = bundleSchema.parse(raw);
    if (sha256(JSON.stringify(bundle.data)) !== bundle.checksum)
      throw badRequest('bundle checksum mismatch; the file was modified or truncated');
    const report = {
      inserted: {} as Record<string, number>,
      skippedIdentical: {} as Record<string, number>,
      conflicts: [] as { table: string; id: string; reason: string }[],
      warnings: [] as string[],
    };
    const bump = (o: Record<string, number>, k: string) => {
      o[k] = (o[k] ?? 0) + 1;
    };
    const exp = bundle.data.experiments[0] as Row;
    const sameExceptVolatile = (a: Row, b: Row) => JSON.stringify(a) === JSON.stringify(b);

    this.db.transaction(() => {
      for (const t of bundle.data.planned_attempts) {
        const task = this.repos.tasks.get(String(t.task_id));
        if (!task) throw badRequest(`bundle references unknown task ${String(t.task_id)}`);
        if (task.taskHash !== t.task_hash)
          report.warnings.push(
            `task ${task.id} content differs locally (hash ${String(t.task_hash).slice(0, 12)} vs ${task.taskHash.slice(0, 12)})`,
          );
      }
      const existingExp = this.db.get('SELECT * FROM experiments WHERE id = ?', String(exp.id));
      if (!existingExp) {
        this.repos.experiments.insertRaw(exp);
        bump(report.inserted, 'experiments');
      } else if (sameExceptVolatile(existingExp, exp)) bump(report.skippedIdentical, 'experiments');
      else {
        const { status: _a, started_at: _b, completed_at: _c, ...restLocal } = existingExp;
        const { status: _d, started_at: _e, completed_at: _f, ...restIncoming } = exp;
        if (JSON.stringify(restLocal) !== JSON.stringify(restIncoming))
          report.conflicts.push({ table: 'experiments', id: String(exp.id), reason: 'experiment definition differs' });
        else bump(report.skippedIdentical, 'experiments');
      }
      for (const p of bundle.data.planned_attempts) {
        const local = this.db.get('SELECT * FROM planned_attempts WHERE id = ?', String(p.id));
        if (!local) {
          const cols = Object.keys(p);
          this.db.run(
            `INSERT INTO planned_attempts (${cols.join(',')}) VALUES (${cols.map(() => '?').join(',')})`,
            ...(cols.map((c) => p[c]) as (string | number | null)[]),
          );
          bump(report.inserted, 'planned_attempts');
        } else if (sameExceptVolatile(local, p as Row)) bump(report.skippedIdentical, 'planned_attempts');
        else report.conflicts.push({ table: 'planned_attempts', id: String(p.id), reason: 'planned attempt differs' });
      }
      const insertedRuns = new Set<string>();
      // Runs referencing an earlier run (retries) must be inserted after it.
      const runs = [...bundle.data.runs].sort((a, b) => Number(a.run_number) - Number(b.run_number));
      for (const r of runs) {
        const local = this.repos.runs.rawRow(String(r.id));
        if (!local) {
          const clash = this.db.get(
            'SELECT id FROM runs WHERE planned_attempt_id = ? AND run_number = ?',
            String(r.planned_attempt_id),
            Number(r.run_number),
          );
          if (clash) {
            report.conflicts.push({
              table: 'runs',
              id: String(r.id),
              reason: `attempt already has a local run #${String(r.run_number)} (${String(clash.id)})`,
            });
            continue;
          }
          this.repos.runs.insertRaw({ ...(r as Row), latest_evaluation_id: r.latest_evaluation_id ?? null });
          insertedRuns.add(String(r.id));
          bump(report.inserted, 'runs');
        } else if (sameExceptVolatile(local, r as Row)) bump(report.skippedIdentical, 'runs');
        else
          report.conflicts.push({
            table: 'runs',
            id: String(r.id),
            reason: `local status ${String(local.status)} vs incoming ${String(r.status)}; not overwritten`,
          });
      }
      const insertedEvals = new Set<string>();
      for (const e of bundle.data.evaluations) {
        if (!insertedRuns.has(String(e.run_id))) continue;
        this.repos.evaluations.insertRaw('evaluations', e as Row);
        insertedEvals.add(String(e.id));
        bump(report.inserted, 'evaluations');
      }
      for (const table of ['test_outcomes', 'findings'] as const) {
        for (const row of bundle.data[table]) {
          if (!insertedEvals.has(String(row.evaluation_id))) continue;
          this.repos.evaluations.insertRaw(table, row as Row);
          bump(report.inserted, table);
        }
      }
      for (const ev of bundle.data.events) {
        if (ev.run_id && !insertedRuns.has(String(ev.run_id))) continue;
        if (!ev.run_id && report.inserted.experiments !== 1) continue;
        const { id: _id, ...rest } = ev;
        const cols = Object.keys(rest);
        this.db.run(
          `INSERT INTO events (${cols.join(',')}) VALUES (${cols.map(() => '?').join(',')})`,
          ...(cols.map((c) => (rest as Row)[c]) as (string | number | null)[]),
        );
        bump(report.inserted, 'events');
      }
      this.repos.events.add({
        experimentId: String(exp.id),
        type: 'bundle_imported',
        actor: this.cfg.ACB_OPERATOR,
        payload: { from: bundle.exportedBy, machine: bundle.machineId, inserted: report.inserted, conflicts: report.conflicts.length },
      });
    });
    if (insertedArtifactsNote(bundle))
      report.warnings.push(
        'Artifact files (logs, patches, reports) are not part of the bundle; copy the artifacts/runs/<run-id> folders separately if needed.',
      );
    return report;
  }

  /** Write every export format for one experiment (or all) to a timestamped directory. */
  writeAll(experimentId?: string): { directory: string; files: { name: string; sha256: string; bytes: number }[] } {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const dir = path.join(this.cfg.ACB_ARTIFACT_ROOT, 'exports', `${stamp}-${experimentId ? experimentId.slice(0, 8) : 'all'}`);
    fs.mkdirSync(dir, { recursive: true });
    const files: { name: string; sha256: string; bytes: number }[] = [];
    const formats: ExportFormat[] = ['jsonl', 'csv', 'config', 'summary_csv', 'dictionary', 'dictionary_md', 'manifest'];
    if (experimentId) formats.push('bundle');
    for (const f of formats) {
      const [name, , body] = this.render(f, experimentId);
      fs.writeFileSync(path.join(dir, name), body, 'utf8');
      files.push({ name, sha256: sha256(body), bytes: Buffer.byteLength(body) });
    }
    fs.writeFileSync(path.join(dir, 'CHECKSUMS.json'), JSON.stringify(files, null, 2));
    return { directory: dir, files };
  }
}

function insertedArtifactsNote(bundle: Bundle): boolean {
  return bundle.data.runs.length > 0;
}
