import fs from 'node:fs';
import { type NextFunction, type Request, type Response, Router } from 'express';
import { z } from 'zod';
import { PLATFORM_VERSION } from '../config.ts';
import { badRequest } from '../lib/errors.ts';
import type { Services } from '../services/container.ts';
import { experimentInputSchema } from '../services/experimentService.ts';
import { BENCHMARKS, benchmarkOf } from '../services/taskService.ts';
import { EVIDENCE_FORMATS } from '../services/evidenceService.ts';
import { EXPORT_FORMATS } from '../services/exportService.ts';
import { failSchema, invalidateSchema, labelSchema, logSchema, submitSchema } from '../services/runService.ts';
import { ASSISTANT_IDS } from '../types.ts';

type Handler = (req: Request, res: Response) => unknown | Promise<unknown>;
const h = (fn: Handler) => (req: Request, res: Response, next: NextFunction) => {
  Promise.resolve(fn(req, res)).catch(next);
};

const idParam = z.string().regex(/^[A-Za-z0-9_-]{1,64}$/, 'invalid identifier');
const optionalId = idParam.optional();

export function buildRouter(s: Services): Router {
  const r = Router();

  // ------------------------------------------------------------------------------ health
  r.get(
    '/health',
    h(async (_req, res) => {
      res.json({
        status: 'ok',
        version: PLATFORM_VERSION,
        time: new Date().toISOString(),
        database: { schemaVersion: s.db.schemaVersion() },
        tasks: s.repos.tasks.list().length,
        benchmarks: Object.fromEntries(
          BENCHMARKS.map((b) => [b, s.repos.tasks.list().filter((t) => benchmarkOf(t) === b).length]),
        ),
        evalMode: s.cfg.ACB_EVAL_MODE,
        automationEnabled: s.cfg.ACB_ENABLE_AUTOMATION === '1',
        operator: s.cfg.ACB_OPERATOR,
        machineId: s.cfg.ACB_MACHINE_ID,
        workspaceRoot: s.cfg.ACB_WORKSPACE_ROOT,
      });
    }),
  );

  r.get(
    '/health/evaluator',
    h(async (req, res) => {
      const mode = z.enum(['docker', 'local']).default(s.cfg.ACB_EVAL_MODE).parse(req.query.mode);
      res.json(await s.evaluator.environment(mode));
    }),
  );

  // ------------------------------------------------------------------------------- tasks
  r.get(
    '/tasks',
    h((req, res) => {
      const q = z
        .object({
          category: z.string().optional(),
          difficulty: z.string().optional(),
          validation: z.string().optional(),
          benchmark: z.enum(BENCHMARKS).optional(),
          q: z.string().max(100).optional(),
        })
        .parse(req.query);
      res.json({ tasks: s.tasks.list(q).map(({ prompt: _p, ...t }) => t) });
    }),
  );

  r.post(
    '/tasks/sync',
    h(async (_req, res) => {
      res.json(await s.tasks.sync());
    }),
  );

  r.get(
    '/tasks/:taskId',
    h((req, res) => {
      const task = s.tasks.get(idParam.parse(req.params.taskId));
      res.json({ task, versions: s.repos.tasks.versions(task.id) });
    }),
  );

  r.get(
    '/tasks/:taskId/starter',
    h((req, res) => {
      const filePath = z.string().min(1).max(300).parse(req.query.path);
      res.json(s.tasks.starterFile(idParam.parse(req.params.taskId), filePath));
    }),
  );

  // -------------------------------------------------------------------------- assistants
  r.get(
    '/assistants',
    h((_req, res) => res.json({ assistants: s.assistants.list() })),
  );
  r.post(
    '/assistants/detect',
    h(async (_req, res) => {
      await s.assistants.detectAll();
      res.json({ assistants: s.assistants.list() });
    }),
  );
  r.patch(
    '/assistants/:assistantId',
    h((req, res) => {
      const id = z.enum(ASSISTANT_IDS).parse(req.params.assistantId);
      const body = z.object({ version: z.string().max(120).nullable(), model: z.string().max(120).nullable() }).parse(req.body);
      res.json({ assistant: s.assistants.setOperatorReported(id, body.version || null, body.model || null) });
    }),
  );

  // ------------------------------------------------------------------------- experiments
  r.get(
    '/experiments',
    h((_req, res) => res.json({ experiments: s.experiments.list() })),
  );

  r.post(
    '/experiments/preview',
    h((req, res) => {
      res.json(s.experiments.preview(experimentInputSchema.parse(req.body)));
    }),
  );

  r.post(
    '/experiments',
    h((req, res) => {
      const created = s.experiments.create(experimentInputSchema.parse(req.body));
      res.status(201).json(created);
    }),
  );

  r.get(
    '/experiments/:experimentId',
    h((req, res) => {
      res.json(s.experiments.detail(idParam.parse(req.params.experimentId)));
    }),
  );

  r.post(
    '/experiments/:experimentId/start',
    h((req, res) => {
      res.json({ experiment: s.experiments.start(idParam.parse(req.params.experimentId)) });
    }),
  );

  r.post(
    '/experiments/:experimentId/status',
    h((req, res) => {
      const body = z.object({ status: z.enum(['completed', 'archived']) }).parse(req.body);
      res.json({ experiment: s.experiments.setStatus(idParam.parse(req.params.experimentId), body.status) });
    }),
  );

  // -------------------------------------------------------------------------------- runs
  r.get(
    '/runs',
    h((req, res) => {
      const q = z
        .object({
          experimentId: optionalId,
          status: z.string().max(30).optional(),
          assistantId: z.string().max(30).optional(),
          taskId: z.string().max(30).optional(),
          limit: z.coerce.number().int().min(1).max(5000).optional(),
        })
        .parse(req.query);
      res.json({ runs: s.repos.runs.list(q) });
    }),
  );

  r.get(
    '/runs/:runId',
    h((req, res) => res.json(s.runs.detail(idParam.parse(req.params.runId)))),
  );

  r.post(
    '/runs/:runId/prepare',
    h(async (req, res) => res.json({ run: await s.runs.prepare(idParam.parse(req.params.runId)) })),
  );

  r.post(
    '/runs/:runId/start',
    h((req, res) => {
      const body = z
        .object({ assistantVersion: z.string().max(120).optional(), model: z.string().max(120).optional() })
        .parse(req.body ?? {});
      res.json({ run: s.runs.start(idParam.parse(req.params.runId), body) });
    }),
  );

  r.post(
    '/runs/:runId/log',
    h((req, res) => res.json({ run: s.runs.logActivity(idParam.parse(req.params.runId), logSchema.parse(req.body)) })),
  );

  r.post(
    '/runs/:runId/stop',
    h((req, res) => res.json({ run: s.runs.stop(idParam.parse(req.params.runId)) })),
  );

  r.post(
    '/runs/:runId/submit',
    h(async (req, res) => {
      const run = await s.runs.submit(idParam.parse(req.params.runId), submitSchema.parse(req.body ?? {}));
      res.status(202).json({ run });
    }),
  );

  r.post(
    '/runs/:runId/evaluate',
    h((req, res) => {
      const result = s.runs.enqueueEvaluation(idParam.parse(req.params.runId));
      res.status(202).json(result);
    }),
  );

  r.post(
    '/runs/:runId/automate',
    h(async (req, res) => {
      const id = idParam.parse(req.params.runId);
      res.status(202).json({ run: await s.runs.automate(id) });
    }),
  );

  r.post(
    '/runs/:runId/retry',
    h((req, res) => res.status(201).json({ run: s.runs.retry(idParam.parse(req.params.runId)) })),
  );

  r.post(
    '/runs/:runId/fail',
    h((req, res) => res.json({ run: s.runs.fail(idParam.parse(req.params.runId), failSchema.parse(req.body)) })),
  );

  r.post(
    '/runs/:runId/invalidate',
    h((req, res) => {
      const body = invalidateSchema.parse(req.body);
      res.json({ run: s.runs.invalidate(idParam.parse(req.params.runId), body.reason) });
    }),
  );

  r.patch(
    '/runs/:runId/labels',
    h((req, res) => res.json({ run: s.runs.label(idParam.parse(req.params.runId), labelSchema.parse(req.body)) })),
  );

  r.get(
    '/runs/:runId/artifacts/:artifactId',
    h((req, res) => {
      const { file, name } = s.runs.artifactPath(idParam.parse(req.params.runId), idParam.parse(req.params.artifactId));
      const textual = /\.(txt|json|xml|patch|md|csv|jsonl)$/i.test(name);
      res.setHeader('Content-Type', textual ? 'text/plain; charset=utf-8' : 'application/octet-stream');
      res.setHeader('Content-Disposition', `inline; filename="${name.replace(/[^A-Za-z0-9._-]/g, '_')}"`);
      res.setHeader('X-Content-Type-Options', 'nosniff');
      fs.createReadStream(file).pipe(res);
    }),
  );

  // ----------------------------------------------------------------------------- results
  r.get(
    '/results/summary',
    h((req, res) => {
      const q = z.object({ experimentId: optionalId, benchmark: z.enum(BENCHMARKS).optional() }).parse(req.query);
      res.json(s.results.summary(q.experimentId, q.benchmark));
    }),
  );

  r.get(
    '/results/records',
    h((req, res) => {
      const q = z.object({ experimentId: optionalId, benchmark: z.enum(BENCHMARKS).optional() }).parse(req.query);
      res.json({ records: s.results.flatRecords(q.experimentId, q.benchmark) });
    }),
  );

  r.get(
    '/results/export',
    h((req, res) => {
      const q = z.object({ format: z.enum(EXPORT_FORMATS).default('jsonl'), experimentId: optionalId }).parse(req.query);
      const [name, type, body] = s.exports.render(q.format, q.experimentId);
      res.setHeader('Content-Type', `${type}; charset=utf-8`);
      res.setHeader('Content-Disposition', `attachment; filename="${name}"`);
      res.send(body);
    }),
  );

  r.post(
    '/results/export-all',
    h((req, res) => {
      const body = z.object({ experimentId: optionalId }).parse(req.body ?? {});
      res.json(s.exports.writeAll(body.experimentId));
    }),
  );

  r.post(
    '/results/import',
    h((req, res) => {
      if (!req.body || typeof req.body !== 'object') throw badRequest('expected a bundle JSON body');
      res.json(s.exports.importBundle(req.body));
    }),
  );

  // ---------------------------------------------------------------------------- evidence
  // Published figures from the literature. Secondary data, kept apart from measured runs.
  r.get(
    '/evidence',
    h((_req, res) => {
      res.json(s.evidence.load());
    }),
  );

  r.get(
    '/evidence/export',
    h((req, res) => {
      const q = z.object({ format: z.enum(EVIDENCE_FORMATS).default('csv') }).parse(req.query);
      const [name, type, body] = s.evidence.render(q.format);
      res.setHeader('Content-Type', `${type}; charset=utf-8`);
      res.setHeader('Content-Disposition', `attachment; filename="${name}"`);
      res.send(body);
    }),
  );

  // ------------------------------------------------------------------------------ events
  r.get(
    '/events',
    h((req, res) => {
      const q = z.object({ limit: z.coerce.number().int().min(1).max(200).default(20) }).parse(req.query);
      res.json({ events: s.repos.events.recent(q.limit) });
    }),
  );

  return r;
}
