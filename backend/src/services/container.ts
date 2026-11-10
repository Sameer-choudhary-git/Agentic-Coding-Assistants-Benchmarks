import path from 'node:path';
import type { Config } from '../config.ts';
import { Database } from '../db/database.ts';
import type { Logger } from '../logger.ts';
import { createRepositories, type Repositories } from '../repositories/repositories.ts';
import { AssistantService } from './assistantService.ts';
import { EvaluatorClient } from './evaluatorClient.ts';
import { EvidenceService } from './evidenceService.ts';
import { ExperimentService } from './experimentService.ts';
import { ExportService } from './exportService.ts';
import { ResultsService } from './resultsService.ts';
import { RunService } from './runService.ts';
import { TaskService } from './taskService.ts';

export interface Services {
  cfg: Config;
  db: Database;
  logger: Logger;
  repos: Repositories;
  evaluator: EvaluatorClient;
  tasks: TaskService;
  assistants: AssistantService;
  experiments: ExperimentService;
  runs: RunService;
  results: ResultsService;
  exports: ExportService;
  evidence: EvidenceService;
}

export function createServices(cfg: Config, logger: Logger, db = new Database(cfg.ACB_DB_PATH)): Services {
  db.migrate();
  const repos = createRepositories(db);
  const evaluator = new EvaluatorClient(cfg);
  const tasks = new TaskService(cfg, repos, evaluator, logger);
  const assistants = new AssistantService(cfg, repos);
  assistants.ensureDefinitions();
  const experiments = new ExperimentService(cfg, db, repos);
  const runs = new RunService(cfg, db, repos, evaluator, assistants, logger);
  const results = new ResultsService(repos);
  const exports = new ExportService(cfg, db, repos, results);
  const evidence = new EvidenceService(path.join(cfg.repoRoot, 'evidence'));
  return { cfg, db, logger, repos, evaluator, tasks, assistants, experiments, runs, results, exports, evidence };
}
