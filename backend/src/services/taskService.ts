import fs from 'node:fs';
import path from 'node:path';
import type { Config } from '../config.ts';
import { notFound } from '../lib/errors.ts';
import { safeJoin } from '../lib/util.ts';
import type { Logger } from '../logger.ts';
import type { Repositories } from '../repositories/repositories.ts';
import type { TaskRecord } from '../types.ts';
import type { EvaluatorClient } from './evaluatorClient.ts';

export interface TaskFilter {
  category?: string;
  difficulty?: string;
  validation?: string;
  q?: string;
  benchmark?: string;
}

export const BENCHMARKS = ['custom', 'swebench_verified'] as const;

/** Which benchmark a task belongs to: the 18-task custom suite or SWE-bench Verified. */
export function benchmarkOf(task: Pick<TaskRecord, 'kind' | 'metadata'>): string {
  return (task.metadata.benchmark as string | undefined) ?? (task.kind === 'swebench' ? 'swebench_verified' : 'custom');
}

export class TaskService {
  constructor(
    private readonly cfg: Config,
    private readonly repos: Repositories,
    private readonly evaluator: EvaluatorClient,
    private readonly logger: Logger,
  ) {}

  /** Synchronise task metadata from the benchmark_tasks directory (via the evaluator CLI). */
  async sync(): Promise<{ count: number }> {
    const tasks = await this.evaluator.listTasks();
    for (const t of tasks) {
      this.repos.tasks.upsert({
        id: t.id,
        title: t.title,
        category: t.category,
        difficulty: t.difficulty,
        kind: t.kind,
        version: t.version,
        testVersion: t.test_version,
        taskHash: t.task_hash,
        promptHash: t.prompt_hash,
        testHash: t.test_hash,
        starterHash: t.starter_hash,
        validationStatus: t.validation.status,
        validatedAt: t.validation.validated_at,
        expectedAcceptanceTotal: t.validation.expected_acceptance_total,
        prompt: t.prompt,
        metadata: {
          summary: t.summary,
          difficultyRationale: t.difficulty_rationale,
          requiredBehavior: t.required_behavior,
          acceptanceCriteria: t.acceptance_criteria,
          acceptanceTests: t.acceptance_tests,
          scope: t.scope,
          timeLimitMinutes: t.time_limit_minutes,
          testTimeoutSeconds: t.test_timeout_seconds,
          testWriting: t.test_writing ?? null,
          directory: t.directory,
          starterLocation: t.starter_location,
          starterFiles: t.starter_files,
          benchmark: t.benchmark ?? (t.kind === 'swebench' ? 'swebench_verified' : 'custom'),
          swebench: t.swebench ?? null,
        },
      });
    }
    this.logger.info('tasks synchronised', { count: tasks.length });
    return { count: tasks.length };
  }

  list(filter: TaskFilter = {}): TaskRecord[] {
    const q = filter.q?.toLowerCase();
    return this.repos.tasks
      .list()
      .filter(
        (t) =>
          (!filter.category || t.category === filter.category) &&
          (!filter.difficulty || t.difficulty === filter.difficulty) &&
          (!filter.validation || t.validationStatus === filter.validation) &&
          (!filter.benchmark || benchmarkOf(t) === filter.benchmark) &&
          (!q || `${t.id} ${t.title} ${(t.metadata.summary as string) ?? ''}`.toLowerCase().includes(q)),
      );
  }

  get(id: string): TaskRecord {
    const task = this.repos.tasks.get(id);
    if (!task) throw notFound(`task ${id}`);
    return task;
  }

  /**
   * Read one starter file for display. Only files listed in the task's starter manifest are
   * served, so hidden tests, reference solutions and mutants can never be requested.
   */
  starterFile(id: string, relPath: string): { path: string; content: string } {
    const task = this.get(id);
    const files = (task.metadata.starterFiles as { path: string }[]) ?? [];
    if (!files.some((f) => f.path === relPath)) throw notFound(`starter file ${relPath}`);
    const starterDir = path.join(this.cfg.repoRoot, 'benchmark_tasks', String(task.metadata.directory), 'starter');
    const file = safeJoin(starterDir, relPath);
    return { path: relPath, content: fs.readFileSync(file, 'utf8') };
  }
}
