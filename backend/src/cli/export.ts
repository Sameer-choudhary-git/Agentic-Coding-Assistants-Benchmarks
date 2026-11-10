/**
 * Write every export (JSONL, CSV, config, summary, data dictionary, manifest, bundle) to
 * artifacts/exports/<timestamp>/. Usage:
 *   npm run export --workspace backend -- [experimentId]
 */
import { loadConfig, loadDotEnv } from '../config.ts';
import { createLogger } from '../logger.ts';
import { createServices } from '../services/container.ts';

loadDotEnv();
const cfg = loadConfig();
const services = createServices(cfg, createLogger('warn'));
const experimentId = process.argv[2];
const result = services.exports.writeAll(experimentId);
console.log(`Exports written to ${result.directory}`);
for (const f of result.files) console.log(`  ${f.name.padEnd(36)} ${String(f.bytes).padStart(9)} bytes  sha256 ${f.sha256.slice(0, 16)}`);
services.db.close();
