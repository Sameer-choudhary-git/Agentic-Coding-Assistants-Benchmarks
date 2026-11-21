/**
 * Golden dataset overview: reads what the golden pipeline (golden/, `python -m agentbench`) wrote to disk.
 * dataset/manifest.json describes the dataset; reports/results.json holds the published-agent analysis.
 * These are offline analysis outputs, kept apart from the platform's own experiment records. Files are
 * read on each request, so a rebuild shows up without a restart.
 */
import fs from 'node:fs';
import path from 'node:path';
import { notFound } from '../lib/errors.ts';

const FIGURE = /^fig[\w-]{1,60}\.png$/;

export class GoldenService {
  constructor(private readonly root: string) {}

  /** Python's json writes NaN for undefined statistics; JSON.parse does not accept it. */
  private readJson(rel: string): unknown {
    const file = path.join(this.root, rel);
    if (!fs.existsSync(file)) return null;
    return JSON.parse(fs.readFileSync(file, 'utf8').replace(/\bNaN\b|-?\bInfinity\b/g, 'null'));
  }

  overview() {
    const manifest = this.readJson('dataset/manifest.json') as Record<string, unknown> | null;
    if (!manifest) throw notFound('golden dataset (golden/dataset/manifest.json)');
    const app = this.readJson('dataset/app_swebench_verified.json') as { instances?: unknown[] } | null;
    const figDir = path.join(this.root, 'reports', 'figures');
    const figures = fs.existsSync(figDir) ? fs.readdirSync(figDir).filter((f) => FIGURE.test(f)).sort() : [];
    return {
      name: manifest.name,
      version: manifest.version,
      seed: manifest.seed,
      builtAt: manifest.built_at,
      nTasks: manifest.n_tasks,
      summary: manifest.summary,
      gateStats: manifest.gate_stats,
      difficultyCalibration: manifest.difficulty_calibration,
      appTasks: app?.instances?.length ?? 0,
      results: this.readJson('reports/results.json'),
      figures,
    };
  }

  figurePath(name: string): string {
    if (!FIGURE.test(name)) throw notFound(`figure ${name}`);
    const file = path.join(this.root, 'reports', 'figures', name);
    if (!fs.existsSync(file)) throw notFound(`figure ${name}`);
    return file;
  }
}
