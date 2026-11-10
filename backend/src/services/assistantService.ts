import type { Config } from '../config.ts';
import { notFound } from '../lib/errors.ts';
import type { Repositories } from '../repositories/repositories.ts';
import type { AssistantRecord } from '../types.ts';
import { ADAPTERS, type CapabilityReport, detectCapability, getAdapter } from './adapters/adapters.ts';

export class AssistantService {
  private reports = new Map<string, CapabilityReport>();

  constructor(
    private readonly cfg: Config,
    private readonly repos: Repositories,
  ) {}

  ensureDefinitions(): void {
    for (const a of ADAPTERS) this.repos.assistants.ensure({ id: a.id, name: a.name, vendor: a.vendor, interface: a.interface });
  }

  async detectAll(): Promise<AssistantRecord[]> {
    for (const def of ADAPTERS) {
      const report = await detectCapability(def, this.cfg.ACB_ENABLE_AUTOMATION === '1');
      this.reports.set(def.id, report);
      this.repos.assistants.setCapability(def.id, report.status, report.detail, report.detectedVersion);
    }
    return this.list();
  }

  list(): (AssistantRecord & { manualInstructions: string; docsUrl: string })[] {
    return this.repos.assistants.list().map((a) => {
      const def = getAdapter(a.id)!;
      return { ...a, manualInstructions: def.manualInstructions, docsUrl: def.docsUrl };
    });
  }

  get(id: string): AssistantRecord {
    const a = this.repos.assistants.get(id);
    if (!a) throw notFound(`assistant ${id}`);
    return a;
  }

  async report(id: string): Promise<CapabilityReport> {
    const def = getAdapter(id);
    if (!def) throw notFound(`assistant ${id}`);
    const cached = this.reports.get(id);
    if (cached) return cached;
    const fresh = await detectCapability(def, this.cfg.ACB_ENABLE_AUTOMATION === '1');
    this.reports.set(id, fresh);
    return fresh;
  }

  setOperatorReported(id: string, version: string | null, model: string | null): AssistantRecord {
    this.get(id);
    this.repos.assistants.setOperatorReported(id, version, model);
    return this.get(id);
  }
}
