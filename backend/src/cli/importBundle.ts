/**
 * Merge an experiment bundle exported by another team member. Usage:
 *   npm run import-bundle --workspace backend -- path/to/bundle-xxxx.json
 * Identical records are skipped; conflicting records are reported and never overwritten.
 */
import fs from 'node:fs';
import { loadConfig, loadDotEnv } from '../config.ts';
import { createLogger } from '../logger.ts';
import { createServices } from '../services/container.ts';

const file = process.argv[2];
if (!file) {
  console.error('usage: import-bundle <bundle.json>');
  process.exit(2);
}
loadDotEnv();
const services = createServices(loadConfig(), createLogger('warn'));
try {
  const report = services.exports.importBundle(JSON.parse(fs.readFileSync(file, 'utf8')));
  console.log(JSON.stringify(report, null, 2));
  process.exitCode = report.conflicts.length ? 1 : 0;
} catch (err) {
  console.error(`import failed: ${(err as Error).message}`);
  process.exitCode = 2;
} finally {
  services.db.close();
}
