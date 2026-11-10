import fs from 'node:fs';
import path from 'node:path';
import type { Config } from '../config.ts';
import { runProcess } from '../lib/util.ts';

export interface PublicTask {
  id: string;
  title: string;
  category: string;
  difficulty: string;
  difficulty_rationale: string;
  version: string;
  test_version: string;
  kind: string;
  /** 'custom' (the 18-task suite) or 'swebench_verified'. */
  benchmark?: string;
  swebench?: Record<string, unknown>;
  summary: string;
  required_behavior: string[];
  acceptance_criteria: string[];
  acceptance_tests: { id: string; description: string }[];
  scope: { allowed_paths: string[]; protected_paths: string[] };
  time_limit_minutes: number;
  test_timeout_seconds: number;
  test_writing?: Record<string, unknown>;
  directory: string;
  starter_location: string;
  starter_files: { path: string; size: number }[];
  prompt: string;
  task_hash: string;
  prompt_hash: string;
  starter_hash: string;
  test_hash: string;
  metadata_hash: string;
  validation: { status: string; validated_at: string | null; expected_acceptance_total: number | null };
}

export class EvaluatorError extends Error {
  constructor(
    message: string,
    readonly stderr = '',
  ) {
    super(message);
  }
}

/**
 * Talks to the Python evaluator exclusively through its CLI. Submitted code is never executed
 * inside the API server process: the evaluator runs it in a separate process (and, in docker
 * mode, a container).
 */
export class EvaluatorClient {
  constructor(private readonly cfg: Config) {}

  private env(): NodeJS.ProcessEnv {
    return { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', ACB_REPO_ROOT: this.cfg.repoRoot };
  }

  private async cli(args: string[], timeoutMs = 120_000) {
    const result = await runProcess(this.cfg.ACB_PYTHON, ['-m', 'evaluator.cli', ...args], {
      cwd: this.cfg.repoRoot,
      timeoutMs,
      env: this.env(),
    });
    if (result.error) throw new EvaluatorError(`cannot start Python (${this.cfg.ACB_PYTHON}): ${result.error}`);
    if (result.timedOut) throw new EvaluatorError(`evaluator command timed out: ${args[0]}`);
    return result;
  }

  async listTasks(): Promise<PublicTask[]> {
    const r = await this.cli(['list-tasks', '--json', '--compact']);
    if (r.code !== 0) throw new EvaluatorError('list-tasks failed', r.stderr);
    return JSON.parse(r.stdout) as PublicTask[];
  }

  async createWorkspace(taskId: string, destination: string): Promise<void> {
    // SWE-bench workspaces clone a real repository, which can take several minutes.
    const r = await this.cli(['create-workspace', taskId, destination, '--json'], 900_000);
    if (r.code !== 0) throw new EvaluatorError(`create-workspace failed: ${r.stderr.trim()}`, r.stderr);
  }

  async evaluate(opts: {
    taskId: string;
    workspace: string;
    outDir: string;
    mode: string;
    expectedTaskHash: string;
    context: Record<string, unknown>;
    timeoutSeconds?: number;
  }): Promise<Record<string, any>> {
    fs.mkdirSync(opts.outDir, { recursive: true });
    const r = await this.cli(
      [
        'evaluate',
        '--task',
        opts.taskId,
        '--workspace',
        opts.workspace,
        '--out',
        opts.outDir,
        '--mode',
        opts.mode,
        '--expected-task-hash',
        opts.expectedTaskHash,
        '--context-json',
        JSON.stringify(opts.context),
      ],
      (opts.timeoutSeconds ?? this.cfg.ACB_EVALUATOR_TIMEOUT_SECONDS) * 1000,
    );
    const reportPath = path.join(opts.outDir, 'report.json');
    if (!fs.existsSync(reportPath)) {
      throw new EvaluatorError(`evaluator produced no report (exit ${r.code}): ${(r.stderr || r.stdout).slice(-2000)}`, r.stderr);
    }
    return JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  }

  async environment(mode: string): Promise<Record<string, unknown>> {
    const r = await this.cli(['env', '--mode', mode], 180_000);
    try {
      return JSON.parse(r.stdout);
    } catch {
      return { error: (r.stderr || r.stdout || 'unknown error').slice(0, 2000) };
    }
  }
}
