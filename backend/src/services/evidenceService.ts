/**
 * Evidence registry: published figures from the literature (evidence/*.json in the repo).
 * These are secondary data from cited sources, never results measured by this platform, and they are
 * kept strictly apart from experiment records. Files are read on each request so edits show up
 * without a restart.
 */
import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';

const sourceSchema = z.object({
  id: z.string(),
  title: z.string(),
  authors: z.array(z.string()),
  year: z.number().int(),
  venue: z.string(),
  url: z.string().url(),
  arxiv: z.string().optional(),
  doi: z.string().optional(),
  role: z.string(),
  verified: z.array(z.string()),
  cautions: z.array(z.string()),
});

const itemSchema = z.object({
  id: z.string(),
  theme: z.string(),
  source: z.string(),
  subject: z.string(),
  metric: z.string(),
  value: z.number().nullable(),
  unit: z.string(),
  n: z.number().optional(),
  conditions: z.string(),
});

const assistantSchema = z.object({
  id: z.string(),
  name: z.string(),
  vendor: z.string(),
  interactionModes: z.array(z.string()),
  autonomy: z.array(z.enum(['L1', 'L2', 'L3', 'L4'])),
  context: z.string(),
  tooling: z.string(),
  execution: z.string(),
  deployment: z.string(),
  prOutput: z.string(),
  sources: z.array(z.string().url()),
  note: z.string().optional(),
});

export type EvidenceSource = z.infer<typeof sourceSchema>;
export type EvidenceItem = z.infer<typeof itemSchema>;
export type AssistantFeatures = z.infer<typeof assistantSchema>;

export interface EvidenceRegistry {
  checkedOn: string;
  themes: Record<string, string>;
  sources: EvidenceSource[];
  items: EvidenceItem[];
  features: { checkedOn: string; autonomyScale: Record<string, string>; assistants: AssistantFeatures[] };
}

export const EVIDENCE_FORMATS = ['json', 'csv', 'latex'] as const;
export type EvidenceFormat = (typeof EVIDENCE_FORMATS)[number];

export class EvidenceService {
  constructor(private readonly dir: string) {}

  load(): EvidenceRegistry {
    const read = (f: string) => JSON.parse(fs.readFileSync(path.join(this.dir, f), 'utf8'));
    const src = z.object({ checkedOn: z.string(), sources: z.array(sourceSchema) }).parse(read('sources.json'));
    const ev = z
      .object({ checkedOn: z.string(), themes: z.record(z.string()), items: z.array(itemSchema) })
      .parse(read('evidence.json'));
    const feat = z
      .object({ checkedOn: z.string(), autonomyScale: z.record(z.string()), assistants: z.array(assistantSchema) })
      .parse(read('assistant_features.json'));
    const known = new Set(src.sources.map((s) => s.id));
    const dangling = ev.items.filter((i) => !known.has(i.source)).map((i) => i.id);
    if (dangling.length) throw new Error(`evidence items cite unknown sources: ${dangling.join(', ')}`);
    const unknownTheme = ev.items.filter((i) => !(i.theme in ev.themes)).map((i) => i.id);
    if (unknownTheme.length) throw new Error(`evidence items use unknown themes: ${unknownTheme.join(', ')}`);
    return { checkedOn: ev.checkedOn, themes: ev.themes, sources: src.sources, items: ev.items, features: feat };
  }

  render(format: EvidenceFormat): [filename: string, contentType: string, body: string] {
    const reg = this.load();
    if (format === 'json') return ['evidence.json', 'application/json', JSON.stringify(reg, null, 2)];
    if (format === 'csv') return ['evidence.csv', 'text/csv', toCsv(reg)];
    return ['evidence-tables.tex', 'application/x-tex', toLatex(reg)];
  }
}

function csvCell(v: unknown): string {
  const s = v === null || v === undefined ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv(reg: EvidenceRegistry): string {
  const bySource = new Map(reg.sources.map((s) => [s.id, s]));
  const header = ['id', 'theme', 'subject', 'metric', 'value', 'unit', 'n', 'conditions', 'source_id', 'source_title', 'source_url'];
  const rows = reg.items.map((i) => {
    const s = bySource.get(i.source);
    return [i.id, i.theme, i.subject, i.metric, i.value, i.unit, i.n, i.conditions, i.source, s?.title, s?.url];
  });
  return [header, ...rows].map((r) => r.map(csvCell).join(',')).join('\n') + '\n';
}

export function texEscape(s: string): string {
  return s
    .replace(/\\/g, '\\textbackslash{}')
    .replace(/([&%$#_{}])/g, '\\$1')
    .replace(/~/g, '\\textasciitilde{}')
    .replace(/\^/g, '\\textasciicircum{}')
    .replace(/>=/g, '$\\geq$')
    .replace(/</g, '$<$')
    .replace(/>/g, '$>$');
}

function fmtValue(i: EvidenceItem): string {
  if (i.value === null) return texEscape(i.unit);
  const v = Number.isInteger(i.value) ? i.value.toLocaleString('en-US') : String(i.value);
  return i.unit === '%' ? `${v}\\%` : `${v} ${texEscape(i.unit)}`;
}

export function toLatex(reg: EvidenceRegistry): string {
  const lines: string[] = [
    `% Generated from evidence/*.json (checked ${reg.checkedOn}). Do not edit by hand.`,
    '\\begin{table*}[t]',
    '\\caption{Published evidence used in this study (secondary data; values as reported by each source)}',
    '\\label{tab:evidence}',
    '\\centering\\scriptsize',
    '\\begin{tabular}{@{}p{0.17\\textwidth}p{0.31\\textwidth}r p{0.33\\textwidth}l@{}}',
    '\\toprule',
    'Subject & Metric & Value & Conditions & Src.\\\\',
  ];
  for (const [theme, label] of Object.entries(reg.themes)) {
    const items = reg.items.filter((i) => i.theme === theme);
    if (!items.length) continue;
    lines.push('\\midrule', `\\multicolumn{5}{@{}l}{\\textit{${texEscape(label)}}}\\\\`);
    for (const i of items)
      lines.push(
        `${texEscape(i.subject)} & ${texEscape(i.metric)} & ${fmtValue(i)} & ${texEscape(i.conditions)} & \\cite{${i.source}}\\\\`,
      );
  }
  lines.push('\\bottomrule', '\\end{tabular}', '\\end{table*}', '');
  return lines.join('\n');
}
