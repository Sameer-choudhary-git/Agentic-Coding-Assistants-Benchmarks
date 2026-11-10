import type { NextFunction, Request, Response } from 'express';
import { ZodError } from 'zod';
import type { Logger } from '../logger.ts';

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
  }
}

export const badRequest = (message: string, details?: unknown) => new HttpError(400, 'bad_request', message, details);
export const notFound = (what: string) => new HttpError(404, 'not_found', `${what} not found`);
export const conflict = (message: string, details?: unknown) => new HttpError(409, 'conflict', message, details);
export const unprocessable = (message: string, details?: unknown) => new HttpError(422, 'unprocessable', message, details);

export function errorHandler(logger: Logger) {
  // Express recognises error handlers by their four-argument signature.
  return (err: unknown, req: Request, res: Response, _next: NextFunction): void => {
    if (err instanceof ZodError) {
      res.status(400).json({
        error: { code: 'validation_error', message: 'Request validation failed', details: err.issues },
      });
      return;
    }
    if (err instanceof HttpError) {
      res.status(err.status).json({ error: { code: err.code, message: err.message, details: err.details } });
      return;
    }
    const anyErr = err as { type?: string; status?: number; message?: string };
    if (anyErr?.type === 'entity.too.large') {
      res.status(413).json({ error: { code: 'payload_too_large', message: 'Request body is too large' } });
      return;
    }
    if (anyErr?.type === 'entity.parse.failed') {
      res.status(400).json({ error: { code: 'invalid_json', message: 'Request body is not valid JSON' } });
      return;
    }
    logger.error('unhandled error', {
      path: req.path,
      method: req.method,
      error: err instanceof Error ? { message: err.message, stack: err.stack } : String(err),
    });
    res.status(500).json({ error: { code: 'internal_error', message: 'Internal server error' } });
  };
}
