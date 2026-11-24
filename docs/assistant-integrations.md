# Assistant integrations

The platform never fakes an assistant response and never reports a run as automated unless a real
CLI process ran. Every assistant can always be evaluated through the **human-operated workflow**.

## Capability statuses

| Status | Meaning |
|---|---|
| Supported | A headless CLI was found, automation is enabled (`ACB_ENABLE_AUTOMATION=1`) and credentials appear to be present. Credentials are only proven when a run executes. |
| Requires authentication | CLI found and automation enabled, but no credential variable or login file was found. |
| Requires manual execution | No headless CLI on `PATH`; use the human-operated workflow. |
| Not configured | CLI found but automation is disabled, or an override is malformed, or a Windows `.cmd` shim could not be resolved safely. |
| Unsupported | Reserved for integrations that cannot work at all on this machine. |

Statuses are detected at start-up and with *Check integrations again* on the Assistants page.

## Status at delivery (build environment)

The build environment had none of the four assistant CLIs installed and no vendor credentials, so
**no automated integration was executed against a real assistant**. The adapter plumbing (command
templates, version detection, timeout, output capture, evaluation of the resulting workspace) is
covered by an automated test that uses a stand-in script. On a machine without the CLIs all four
assistants report *Requires manual execution*.

| Assistant | Human-operated | Headless CLI adapter | Verified against the real product here? |
|---|---|---|---|
| GitHub Copilot | Yes (VS Code agent mode) | `copilot -p … --allow-all-tools -s` (Copilot CLI) | No |
| Cursor | Yes (Cursor agent chat) | `cursor-agent -p --force …` (Cursor CLI; binary may be named `agent`) | No |
| Claude Code | Yes (`claude` in a terminal) | `claude -p … --permission-mode acceptEdits --allowedTools Read,Edit,Write,Glob,Grep,Bash --disallowedTools WebFetch,WebSearch --output-format json` | No |
| OpenAI Codex | Yes (`codex` in a terminal) | `codex exec --sandbox workspace-write --skip-git-repo-check …` | No |

Flags were taken from vendor documentation at build time (Claude Code headless docs, GitHub Copilot
CLI programmatic reference, Cursor CLI headless docs, Codex non-interactive docs). CLIs change
quickly — verify each command by hand before enabling automation.

## Enabling an adapter

1. Install the CLI and log in (or set its token variable):
   `ANTHROPIC_API_KEY` or `claude` login for Claude Code; `CODEX_API_KEY`/`OPENAI_API_KEY` or `codex login`;
   `COPILOT_GITHUB_TOKEN`/`GH_TOKEN`; `CURSOR_API_KEY`.
2. In a scratch copy of a starter (`python -m evaluator.cli create-workspace BF-01 ../scratch-bf01`),
   run the command from the table by hand and confirm it edits files without asking questions.
3. If the flags differ for your version, set an override in `.env`, e.g.
   `ACB_CODEX_CMD=["codex","exec","--full-auto","{prompt}"]`. Placeholders: `{prompt}` (prompt text),
   `{prompt_file}` (path to a file with the prompt), `{workspace}`.
4. Set `ACB_ENABLE_AUTOMATION=1`, restart the backend and check the Assistants page.
5. On a run in the *Ready* state, *Run headless CLI instead* executes the adapter with the run's time
   limit; stdout/stderr are stored as artifacts and the workspace is evaluated afterwards.

### Windows notes

npm-installed CLIs are `.cmd` shims, which Node cannot spawn without a shell. The adapter resolves
the shim to its JavaScript entry point and runs it with Node. If that fails, set the override to
`["node", "C:\\path\\to\\cli.js", …]`.

## Common adapter interface

`backend/src/services/adapters/adapters.ts` defines, for every assistant: detection
(`detectCapability`), task setup (the platform creates the workspace), prompt submission
(`executeHeadless` with the frozen prompt), output collection (stdout/stderr artifacts, workspace
snapshot), timeout handling (process killed at the time limit, run marked `timed_out`) and error
reporting (`adapter_error` with exit code and stderr tail).

## Tool parity

Every headless adapter gets the same capability: read, search and edit files and run shell commands in the
workspace without asking. That is what `--allow-all-tools` (Copilot), `--force` (Cursor) and
`--sandbox workspace-write` (Codex) give. Claude Code's allow-list was widened to match, because the earlier
list (Read/Edit/Write plus `python`/`pytest` only) could not search a real repository or run Go/JS/Rust tests
on Golden and SWE-bench tasks.

**Web access.** Golden and SWE-bench issues are public, and their upstream fixes are one search away. The frozen
prompt tells every assistant to work offline, and Claude Code's web tools are disabled. Codex's
`workspace-write` sandbox blocks network by default. Copilot and Cursor have no equivalent switch in the flags
used here. Report this in the paper. For a strict study, also run all four with the network blocked at the OS
or container level (except their own API endpoint), or check transcripts for web use and invalidate those runs.

## Fairness caveat

Headless modes are different products from the IDE experiences (fewer tools, no human in the loop,
different default permissions). Do not mix modes within one assistant in the official study, and
report the mode per assistant.
