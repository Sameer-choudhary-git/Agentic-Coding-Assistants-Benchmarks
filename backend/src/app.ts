import { randomUUID } from 'node:crypto';
import express, { type NextFunction, type Request, type Response } from 'express';
import { errorHandler, notFound } from './lib/errors.ts';
import { buildRouter } from './routes/routes.ts';
import type { Services } from './services/container.ts';

export function createApp(s: Services): express.Express {
  const app = express();
  app.disable('x-powered-by');
  app.set('trust proxy', false);

  // Request id + structured access log.
  app.use((req: Request, res: Response, next: NextFunction) => {
    const id = randomUUID().slice(0, 8);
    const started = process.hrtime.bigint();
    res.setHeader('X-Request-Id', id);
    res.on('finish', () => {
      s.logger.info('request', {
        reqId: id,
        method: req.method,
        path: req.path,
        status: res.statusCode,
        ms: Number(process.hrtime.bigint() - started) / 1e6,
      });
    });
    next();
  });

  // Local-only CORS for the Vite dev server. The API is intended for trusted local use.
  const allowed = new Set(
    s.cfg.ACB_ALLOWED_ORIGINS.split(',')
      .map((o) => o.trim())
      .filter(Boolean),
  );
  app.use((req: Request, res: Response, next: NextFunction) => {
    const origin = req.headers.origin;
    if (origin && allowed.has(origin)) {
      res.setHeader('Access-Control-Allow-Origin', origin);
      res.setHeader('Vary', 'Origin');
      res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PATCH,OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    }
    if (req.method === 'OPTIONS') {
      res.sendStatus(204);
      return;
    }
    next();
  });

  app.use(express.json({ limit: '5mb' }));
  app.use('/api/v1', buildRouter(s));
  app.use('/api', (_req: Request, _res: Response, next: NextFunction) => next(notFound('endpoint')));
  app.use(errorHandler(s.logger));
  return app;
}
