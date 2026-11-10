import assert from 'node:assert/strict';
import path from 'node:path';
import { describe, it } from 'node:test';
import { loadConfig, REPO_ROOT } from '../src/config.ts';
import { Database } from '../src/db/database.ts';
import { csvEscape, mean, median, quantile, safeJoin, shuffle, toCsv, wilson } from '../src/lib/util.ts';
import { createLogger, redact } from '../src/logger.ts';
import { ResultsService, type FlatRecord } from '../src/services/resultsService.ts';
import { tempDir } from './helpers.ts';

describe('safeJoin', () => {
  it('allows nested relative paths', () => {
    assert.equal(safeJoin('/base', 'a/b.txt'), path.resolve('/base', 'a/b.txt'));
  });
  it('rejects traversal, absolute and drive paths', () => {
    for (const bad of ['../x', 'a/../../x', '/etc/passwd', 'C:\\Windows', '\\\\server\\share', '', 'a\0b']) {
      assert.throws(() => safeJoin('/base', bad), bad);
    }
  });
});

describe('statistics helpers', () => {
  it('computes Wilson intervals', () => {
    assert.equal(wilson(0, 0), null);
    const ci = wilson(18, 36)!;
    assert.ok(ci.low > 0.33 && ci.low < 0.35, String(ci.low));
    assert.ok(ci.high > 0.65 && ci.high < 0.67, String(ci.high));
    const all = wilson(10, 10)!;
    assert.equal(all.high, 1);
    assert.ok(all.low < 1);
  });
  it('computes median, mean and quantiles', () => {
    assert.equal(median([]), null);
    assert.equal(median([3, 1, 2]), 2);
    assert.equal(median([4, 1, 2, 3]), 2.5);
    assert.equal(mean([1, 2, 3, 6]), 3);
    assert.equal(quantile([1, 2, 3, 4, 5], 0.25), 2);
  });
  it('shuffles deterministically from a seed', () => {
    const items = Array.from({ length: 20 }, (_, i) => i);
    assert.deepEqual(shuffle(items, 42), shuffle(items, 42));
    assert.notDeepEqual(shuffle(items, 42), shuffle(items, 43));
    assert.deepEqual(
      [...shuffle(items, 7)].sort((a, b) => a - b),
      items,
    );
  });
});

describe('csv', () => {
  it('escapes special characters', () => {
    assert.equal(csvEscape('a,b'), '"a,b"');
    assert.equal(csvEscape('say "hi"'), '"say ""hi"""');
    assert.equal(csvEscape(null), '');
    assert.equal(toCsv(['x', 'y'], [{ x: 1, y: 'a\nb' }]), 'x,y\n1,"a\nb"\n');
  });
});

describe('logger', () => {
  it('redacts secrets and emits JSON lines', () => {
    const lines: string[] = [];
    const log = createLogger('info', { service: 't' }, (l) => lines.push(l));
    log.debug('hidden');
    log.info('hello', { apiKey: 'sk-123', nested: { password: 'p', ok: 1 } });
    assert.equal(lines.length, 1);
    const rec = JSON.parse(lines[0]);
    assert.equal(rec.msg, 'hello');
    assert.equal(rec.apiKey, '[redacted]');
    assert.deepEqual(rec.nested, { password: '[redacted]', ok: 1 });
    assert.deepEqual(redact({ Authorization: 'Bearer x' }), { Authorization: '[redacted]' });
  });
});

describe('configuration', () => {
  it('refuses a workspace root inside the repository', () => {
    assert.throws(() => loadConfig({ ACB_WORKSPACE_ROOT: path.join(REPO_ROOT, 'workspaces') }), /outside the repository/);
  });
  it('validates numeric settings', () => {
    assert.throws(() => loadConfig({ PORT: 'abc' }), /Invalid configuration/);
  });
});

describe('database migrations', () => {
  it('are idempotent and enforce constraints', () => {
    const dir = tempDir();
    const db = new Database(path.join(dir, 'x.sqlite'));
    assert.deepEqual(db.migrate(), [1]);
    assert.deepEqual(db.migrate(), []);
    assert.equal(db.schemaVersion(), 1);
    assert.throws(() => db.run(`INSERT INTO assistants (id, name, vendor, interface, capability_status) VALUES ('x','x','x','x','bogus')`));
    db.close();
  });
  it('rolls back failed transactions', () => {
    const db = new Database(':memory:');
    db.migrate();
    assert.throws(() =>
      db.transaction(() => {
        db.run(`INSERT INTO assistants (id, name, vendor, interface, capability_status) VALUES ('a','a','a','a','supported')`);
        throw new Error('boom');
      }),
    );
    assert.equal(db.all('SELECT * FROM assistants').length, 0);
  });
});

describe('aggregation', () => {
  const base = (over: Partial<FlatRecord>): FlatRecord =>
    ({
      is_effective_run: true,
      eligible_for_success: true,
      status: 'completed',
      success: true,
      timed_out: false,
      wall_clock_seconds: 100,
      iterations: 1,
      human_interventions: 0,
      regression_failure: false,
      ruff_status: 'ran',
      ruff_new: 0,
      semgrep_status: 'unavailable',
      semgrep_new: null,
      run_number: 1,
      line_coverage: null,
      mutation_score: null,
      out_of_scope_count: 0,
      ...over,
    }) as FlatRecord;

  it('uses completed effective runs as the success denominator', () => {
    const rows = [
      base({ success: true }),
      base({ success: false, wall_clock_seconds: 300 }),
      base({ status: 'failed', eligible_for_success: false, success: null }),
      base({ status: 'invalidated', eligible_for_success: false, success: null }),
      base({ is_effective_run: false, eligible_for_success: false, run_number: 1, status: 'failed', success: null }),
    ];
    const a = ResultsService.aggregate(rows, 6);
    assert.equal(a.completed, 2);
    assert.equal(a.successes, 1);
    assert.equal(a.successRate, 0.5);
    assert.equal(a.intentToTreatRate, 1 / 6);
    assert.equal(a.operationalFailures, 1);
    assert.equal(a.invalidated, 1);
    assert.equal(a.notStarted, 2);
    assert.equal(a.duration.median, 200);
    assert.equal(a.semgrep.n, 0, 'unavailable semgrep must not count as zero findings');
    assert.equal(a.semgrep.unavailable, 2);
  });

  it('returns nulls, not zeros, when there is no data', () => {
    const a = ResultsService.aggregate([], 0);
    assert.equal(a.successRate, null);
    assert.equal(a.successCi95, null);
    assert.equal(a.duration.median, null);
    assert.equal(a.intentToTreatRate, null);
  });
});

describe('WSL on a Windows drive', () => {
  it('is detected only for /mnt/<drive>/ paths on Linux inside WSL', async () => {
    const { onWslWindowsDrive } = await import('../src/config.ts');
    const prev = process.env.WSL_DISTRO_NAME;
    process.env.WSL_DISTRO_NAME = 'Ubuntu';
    try {
      assert.equal(onWslWindowsDrive('/mnt/d/Shinchan/acb'), process.platform === 'linux');
      assert.equal(onWslWindowsDrive('/home/me/acb'), false);
    } finally {
      if (prev === undefined) delete process.env.WSL_DISTRO_NAME;
      else process.env.WSL_DISTRO_NAME = prev;
    }
  });
});
