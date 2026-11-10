import fs from 'node:fs';
import path from 'node:path';
import express from 'express';
import { createApp } from './app.ts';
import { loadConfig, onWslWindowsDrive, loadDotEnv } from './config.ts';
import { createLogger } from './logger.ts';
import { createServices } from './services/container.ts';

async function main(): Promise<void> {
  loadDotEnv();
  const cfg = loadConfig();
  const logger = createLogger(cfg.LOG_LEVEL, { service: 'acb-backend' });
  const services = createServices(cfg, logger);
  logger.info('database ready', { file: cfg.ACB_DB_PATH, schemaVersion: services.db.schemaVersion() });
  if (onWslWindowsDrive() && !process.env.ACB_DB_PATH) {
    logger.info('running in WSL on a Windows drive: this copy uses its own database in the Linux home directory', {
      file: cfg.ACB_DB_PATH,
    });
  }

  const recovered = services.runs.recoverInterrupted();
  if (recovered.evaluations || recovered.runs) logger.warn('recovered interrupted work', recovered);

  try {
    await services.tasks.sync();
  } catch (err) {
    logger.error('task synchronisation failed; check ACB_PYTHON and the Python environment', { error: String(err) });
  }
  await services.assistants.detectAll().catch((err) => logger.warn('assistant detection failed', { error: String(err) }));

  const app = createApp(services);
  // Serve the built frontend if present (production-style single-process start).
  const dist = path.join(cfg.repoRoot, 'frontend', 'dist');
  if (fs.existsSync(path.join(dist, 'index.html'))) {
    app.use(express.static(dist));
    app.get(/^\/(?!api\/).*/, (_req, res) => res.sendFile(path.join(dist, 'index.html')));
  }
  // Express 5 calls the listen callback on failure too, so check the error before announcing success.
  const server = app.listen(cfg.PORT, cfg.HOST, (err?: Error) => {
    if (err) {
      const code = (err as NodeJS.ErrnoException).code;
      logger.error('could not start the API server', {
        url: `http://${cfg.HOST}:${cfg.PORT}`,
        error: String(err),
        hint:
          code === 'EADDRINUSE' || code === 'EACCES'
            ? `Port ${cfg.PORT} is in use or reserved by Windows. Stop the other copy of the app, or start with another port, e.g. PORT=4100 npm run dev`
            : undefined,
      });
      services.db.close();
      process.exit(1);
    }
    logger.info('listening', { url: `http://${cfg.HOST}:${cfg.PORT}`, evalMode: cfg.ACB_EVAL_MODE, workspaceRoot: cfg.ACB_WORKSPACE_ROOT });
  });

  const shutdown = async (signal: string) => {
    logger.info('shutting down', { signal });
    server.close();
    await Promise.race([services.runs.idle(), new Promise((r) => setTimeout(r, 10_000))]);
    services.db.close();
    process.exit(0);
  };
  process.on('SIGINT', () => void shutdown('SIGINT'));
  process.on('SIGTERM', () => void shutdown('SIGTERM'));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
