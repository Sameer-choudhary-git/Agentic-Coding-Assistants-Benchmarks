/**
 * Assistant adapters. Each adapter shares one interface: capability detection, task setup,
 * prompt submission (only where a headless CLI exists), output collection, timeout handling and
 * error reporting. Nothing here fakes an assistant response: if automation is unavailable the
 * adapter says so and the platform falls back to the human-operated workflow.
 *
 * Command templates follow the vendors' documentation at the time of writing (see
 * docs/assistant-integrations.md). They are overridable per assistant with an environment variable
 * containing a JSON array, e.g. ACB_CLAUDE_CODE_CMD='["claude","-p","{prompt}","--output-format","json"]'.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { runProcess } from '../../lib/util.ts';
import type { AssistantId, CapabilityStatus } from '../../types.ts';

export interface AdapterDefinition {
  id: AssistantId;
  name: string;
  vendor: string;
  interface: string;
  manualInstructions: string;
  binaryCandidates: string[];
  versionArgs: string[];
  /** Headless invocation template. Placeholders: {prompt}, {prompt_file}, {workspace}. */
  headlessTemplate: string[] | null;
  envOverride: string;
  authEnvVars: string[];
  authFiles: string[];
  docsUrl: string;
}

export const ADAPTERS: AdapterDefinition[] = [
  {
    id: 'copilot',
    name: 'GitHub Copilot',
    vendor: 'GitHub',
    interface: 'VS Code agent mode (manual) or Copilot CLI (headless)',
    manualInstructions:
      'Open the workspace folder in VS Code, open Copilot Chat in Agent mode, paste the frozen prompt and let the agent work. ' +
      'Record each additional prompt you send as an iteration and any manual edit/approval as an intervention.',
    binaryCandidates: ['copilot'],
    versionArgs: ['--version'],
    headlessTemplate: ['{bin}', '-p', '{prompt}', '--allow-all-tools', '-s'],
    envOverride: 'ACB_COPILOT_CMD',
    authEnvVars: ['COPILOT_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN'],
    authFiles: [],
    docsUrl: 'https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference',
  },
  {
    id: 'cursor',
    name: 'Cursor',
    vendor: 'Anysphere',
    interface: 'Cursor editor agent (manual) or Cursor CLI (headless)',
    manualInstructions:
      'Open the workspace folder in Cursor, start a new Agent chat, paste the frozen prompt and let the agent work. ' +
      'Record follow-up prompts as iterations and manual edits/approvals as interventions.',
    binaryCandidates: ['cursor-agent', 'agent'],
    versionArgs: ['--version'],
    headlessTemplate: ['{bin}', '-p', '--force', '--output-format', 'text', '{prompt}'],
    envOverride: 'ACB_CURSOR_CMD',
    authEnvVars: ['CURSOR_API_KEY'],
    authFiles: [],
    docsUrl: 'https://cursor.com/docs/cli/headless',
  },
  {
    id: 'claude_code',
    name: 'Claude Code',
    vendor: 'Anthropic',
    interface: 'Claude Code terminal agent (manual or headless `claude -p`)',
    manualInstructions:
      'Open a terminal in the workspace folder, run `claude`, paste the frozen prompt and let the agent work. ' +
      'Record follow-up prompts as iterations and permission approvals/manual edits as interventions.',
    binaryCandidates: ['claude'],
    versionArgs: ['--version'],
    headlessTemplate: [
      '{bin}',
      '-p',
      '{prompt}',
      '--permission-mode',
      'acceptEdits',
      '--allowedTools',
      'Read,Edit,Write,Bash(python *),Bash(pytest *)',
      '--output-format',
      'json',
    ],
    envOverride: 'ACB_CLAUDE_CODE_CMD',
    authEnvVars: ['ANTHROPIC_API_KEY'],
    authFiles: ['.claude/.credentials.json'],
    docsUrl: 'https://code.claude.com/docs/en/headless',
  },
  {
    id: 'codex',
    name: 'OpenAI Codex',
    vendor: 'OpenAI',
    interface: 'Codex CLI (manual or headless `codex exec`)',
    manualInstructions:
      'Open a terminal in the workspace folder, run `codex`, paste the frozen prompt and let the agent work. ' +
      'Record follow-up prompts as iterations and approvals/manual edits as interventions.',
    binaryCandidates: ['codex'],
    versionArgs: ['--version'],
    headlessTemplate: ['{bin}', 'exec', '--sandbox', 'workspace-write', '--skip-git-repo-check', '{prompt}'],
    envOverride: 'ACB_CODEX_CMD',
    authEnvVars: ['CODEX_API_KEY', 'OPENAI_API_KEY'],
    authFiles: ['.codex/auth.json'],
    docsUrl: 'https://developers.openai.com/codex/noninteractive',
  },
];

export function getAdapter(id: string): AdapterDefinition | undefined {
  return ADAPTERS.find((a) => a.id === id);
}

function which(binary: string): string | null {
  const exts = process.platform === 'win32' ? (process.env.PATHEXT ?? '.EXE;.CMD;.BAT').split(';') : [''];
  for (const dir of (process.env.PATH ?? '').split(path.delimiter)) {
    if (!dir) continue;
    for (const ext of exts) {
      const candidate = path.join(dir, binary + ext.toLowerCase());
      const candidateUpper = path.join(dir, binary + ext);
      for (const c of [candidate, candidateUpper]) {
        try {
          if (fs.statSync(c).isFile()) return c;
        } catch {
          /* not here */
        }
      }
    }
  }
  return null;
}

/**
 * On Windows, npm-installed CLIs are ``.cmd`` shims, which Node refuses to spawn without a shell
 * (and passing a prompt through cmd.exe would be unsafe). Resolve the shim to the JavaScript entry
 * point it wraps and run that with the current Node executable instead.
 */
export function resolveSpawnable(binary: string): string[] {
  if (process.platform !== 'win32' || !/\.(cmd|bat)$/i.test(binary)) return [binary];
  try {
    const text = fs.readFileSync(binary, 'utf8');
    const match = text.match(/"%(?:~)?dp0%\\?([^"]+\.(?:js|cjs|mjs))"/i);
    if (match) return [process.execPath, path.join(path.dirname(binary), match[1])];
  } catch {
    /* fall through */
  }
  throw new Error(`cannot safely execute ${binary} without a shell; set the adapter's *_CMD override to ["node", "<path to cli.js>", ...]`);
}

export interface CapabilityReport {
  status: CapabilityStatus;
  detail: string;
  detectedVersion: string | null;
  binary: string | null;
  command: string[] | null;
}

function overrideTemplate(def: AdapterDefinition): string[] | null {
  const raw = process.env[def.envOverride];
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.every((p) => typeof p === 'string') && parsed.length > 0) return parsed;
  } catch {
    /* ignored: reported below */
  }
  return null;
}

/** Detect whether a headless CLI is installed and whether credentials appear to be present. */
export async function detectCapability(def: AdapterDefinition, automationEnabled: boolean): Promise<CapabilityReport> {
  const override = overrideTemplate(def);
  if (process.env[def.envOverride] && !override) {
    return {
      status: 'not_configured',
      detail: `${def.envOverride} is not a JSON array of strings`,
      detectedVersion: null,
      binary: null,
      command: null,
    };
  }
  const binary = override
    ? (which(override[0]) ?? (fs.existsSync(override[0]) ? override[0] : null))
    : (def.binaryCandidates.map(which).find(Boolean) ?? null);
  if (!binary) {
    return {
      status: 'requires_manual_execution',
      detail: `No headless CLI found on PATH (looked for: ${override ? override[0] : def.binaryCandidates.join(', ')}). Use the human-operated workflow: ${def.interface}.`,
      detectedVersion: null,
      binary: null,
      command: null,
    };
  }
  let detectedVersion: string | null = null;
  let spawnable: string[];
  try {
    spawnable = resolveSpawnable(binary);
  } catch (err) {
    return { status: 'not_configured', detail: (err as Error).message, detectedVersion: null, binary, command: null };
  }
  // For an override such as ["node", "cli.js", "-p", "{prompt}"], the executable prefix is the part
  // before the first flag or placeholder.
  const prefix = override
    ? [
        ...spawnable,
        ...override.slice(
          1,
          Math.max(
            1,
            override.findIndex((a, i) => i > 0 && (a.startsWith('-') || a.includes('{'))),
          ),
        ),
      ]
    : spawnable;
  const versionRun = await runProcess(prefix[0], [...prefix.slice(1), ...def.versionArgs], { timeoutMs: 20_000 });
  if (versionRun.code === 0) detectedVersion = (versionRun.stdout || versionRun.stderr).trim().split(/\r?\n/)[0]?.slice(0, 120) || null;
  const command = override
    ? [...resolveSpawnable(binary), ...override.slice(1)]
    : def.headlessTemplate!.flatMap((p) => (p === '{bin}' ? spawnable : [p]));
  if (!automationEnabled) {
    return {
      status: 'not_configured',
      detail: `CLI detected${detectedVersion ? ` (${detectedVersion})` : ''}, but automated execution is disabled. Verify authentication manually, then set ACB_ENABLE_AUTOMATION=1. Human-operated runs remain available.`,
      detectedVersion,
      binary,
      command,
    };
  }
  const home = os.homedir();
  const hasAuth = def.authEnvVars.some((v) => !!process.env[v]) || def.authFiles.some((f) => fs.existsSync(path.join(home, f)));
  if (!hasAuth) {
    return {
      status: 'requires_authentication',
      detail: `CLI detected${detectedVersion ? ` (${detectedVersion})` : ''}, but no credentials were found (${def.authEnvVars.join(', ')}${def.authFiles.length ? ` or ~/${def.authFiles.join(', ~/')}` : ''}). Log in with the CLI or set the token, then re-check. Credentials are only verified when a run executes.`,
      detectedVersion,
      binary,
      command,
    };
  }
  return {
    status: 'supported',
    detail: `CLI detected${detectedVersion ? ` (${detectedVersion})` : ''} and credentials appear to be present (not verified until a run executes). Headless template: ${command.join(' ')}`,
    detectedVersion,
    binary,
    command,
  };
}

export interface AdapterRunResult {
  exitCode: number | null;
  timedOut: boolean;
  error: string | null;
  stdout: string;
  stderr: string;
  durationMs: number;
  command: string[];
}

/** Execute a headless CLI in the workspace. Credentials come from the operator's environment. */
export async function executeHeadless(
  command: string[],
  opts: { prompt: string; promptFile: string; workspace: string; timeoutMs: number },
): Promise<AdapterRunResult> {
  const args = command
    .slice(1)
    .map((p) => p.replace('{prompt_file}', opts.promptFile).replace('{workspace}', opts.workspace).replace('{prompt}', opts.prompt));
  const result = await runProcess(command[0], args, { cwd: opts.workspace, timeoutMs: opts.timeoutMs, maxBytes: 2_000_000 });
  return {
    exitCode: result.code,
    timedOut: result.timedOut,
    error: result.error ?? null,
    stdout: result.stdout,
    stderr: result.stderr,
    durationMs: result.durationMs,
    command: [command[0], ...args.map((a) => (a === opts.prompt ? '{prompt}' : a))],
  };
}
