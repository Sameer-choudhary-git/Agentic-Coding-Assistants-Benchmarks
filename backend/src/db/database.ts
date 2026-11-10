import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { MIGRATIONS } from './migrations.ts';

export type Row = Record<string, unknown>;
type Param = string | number | bigint | null | Uint8Array;

/**
 * Thin wrapper around Node's built-in SQLite driver (node:sqlite, Node >= 22.13).
 * Using the built-in driver avoids native add-on builds on student laptops (Windows included).
 * All SQL lives in the repository modules; services never write SQL directly.
 */
export class Database {
  readonly raw!: DatabaseSync;
  private depth = 0;

  constructor(readonly file: string) {
    if (file !== ':memory:') fs.mkdirSync(path.dirname(file), { recursive: true });
    try {
      this.raw = new DatabaseSync(file);
      this.raw.exec('PRAGMA foreign_keys = ON;');
      this.raw.exec('PRAGMA busy_timeout = 5000;');
      if (file !== ':memory:') this.raw.exec('PRAGMA journal_mode = WAL;');
    } catch (err) {
      if (/disk I\/O error/i.test(String(err)) && /^\/mnt\/[a-z]\//i.test(file)) {
        throw new Error(
          `Cannot open the database at ${file}: SQLite cannot use a Windows drive from WSL. ` +
            'Remove ACB_DB_PATH from .env (WSL then uses ~/.acb/acb.sqlite) or point it at a Linux path, ' +
            'and stop any copy of the app running on Windows.',
          { cause: err },
        );
      }
      throw err;
    }
  }

  all<T = Row>(sql: string, ...params: Param[]): T[] {
    return this.raw.prepare(sql).all(...params) as T[];
  }

  get<T = Row>(sql: string, ...params: Param[]): T | undefined {
    return this.raw.prepare(sql).get(...params) as T | undefined;
  }

  run(sql: string, ...params: Param[]): { changes: number; lastInsertRowid: number } {
    const r = this.raw.prepare(sql).run(...params);
    return { changes: Number(r.changes), lastInsertRowid: Number(r.lastInsertRowid) };
  }

  /** Run ``fn`` in a transaction (nested calls join the outer transaction). */
  transaction<T>(fn: () => T): T {
    if (this.depth > 0) return fn();
    this.raw.exec('BEGIN IMMEDIATE');
    this.depth += 1;
    try {
      const result = fn();
      this.raw.exec('COMMIT');
      return result;
    } catch (err) {
      this.raw.exec('ROLLBACK');
      throw err;
    } finally {
      this.depth -= 1;
    }
  }

  migrate(): number[] {
    this.raw.exec(
      'CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)',
    );
    const applied = new Set(this.all<{ version: number }>('SELECT version FROM schema_migrations').map((r) => r.version));
    const ran: number[] = [];
    for (const m of MIGRATIONS) {
      if (applied.has(m.version)) continue;
      this.transaction(() => {
        this.raw.exec(m.sql);
        this.run('INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)', m.version, m.name, nowIso());
      });
      ran.push(m.version);
    }
    return ran;
  }

  schemaVersion(): number {
    const row = this.get<{ v: number | null }>('SELECT MAX(version) AS v FROM schema_migrations');
    return row?.v ?? 0;
  }

  close(): void {
    this.raw.close();
  }
}

export function nowIso(): string {
  return new Date().toISOString();
}

export function json<T>(value: unknown, fallback: T): T {
  if (typeof value !== 'string' || value === '') return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}
