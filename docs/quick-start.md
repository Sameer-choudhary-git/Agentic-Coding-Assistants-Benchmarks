# Quick-start guide

The app compares GitHub Copilot, Cursor, Claude Code and OpenAI Codex on two benchmarks: an 18-task custom
Python suite and a 12-issue SWE-bench Verified pilot. Run it from Ubuntu (WSL) so both benchmarks share one database.

## Setup (once)

| Tool | Why | Check |
|---|---|---|
| Docker Desktop, running | Scores tasks in isolated containers | `docker info` |
| Ubuntu on WSL2 | The SWE-bench harness only runs on Linux | `wsl -l -v` |
| Node.js 22 (in Ubuntu) | Runs the app | `node --version` |
| Python 3.12 + venv, git (in Ubuntu) | Evaluator, analysis, SWE-bench | `python3 --version` |

1. **Install Ubuntu.** In PowerShell run `wsl --install -d Ubuntu`, then create a Linux user.
2. **Connect Docker.** In Docker Desktop open Settings > Resources > WSL integration, turn on Ubuntu, and click Apply & restart.
3. **Install tools in Ubuntu:**
   ```
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
   curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
   ```
4. **Install the project:**
   ```
   cd /mnt/d/Shinchan/agentic-coding-benchmark/agentic-coding-benchmark/agentic-coding-benchmark
   python3 -m venv .venv-wsl && source .venv-wsl/bin/activate
   pip install -r requirements.txt -r requirements-swebench.txt
   npm install
   python swebench_pilot/pilot.py select --ids-from swebench_pilot/candidates.json
   ```
5. **Set the port.** `.env` must contain `PORT=4100`, because Windows reserves port 4000 on this PC.

The Ubuntu copy stores its database at `~/.acb/acb.sqlite`. Back it up.

## Daily use

```
cd /mnt/d/Shinchan/agentic-coding-benchmark/agentic-coding-benchmark/agentic-coding-benchmark
source .venv-wsl/bin/activate
npm run dev        # open http://127.0.0.1:5173 ; stop with one Ctrl+C
```

- **Experiment:** go to Experiments > New experiment and choose a benchmark. SWE-bench is 12 × 4 × 1 = 48 runs; the custom suite is 18 × 4 × 2 = 144. Then click Start.
- **A run:**
  1. Create workspace.
  2. Open the folder in the named assistant.
  3. Start session timer and paste the frozen prompt.
  4. Log every follow-up prompt and intervention.
  5. Stop timer, then Submit and evaluate. Leave the changes uncommitted.
- **Scoring failed because of tooling?** Press **Re-evaluate submission**. It keeps your session. Use Retry attempt only if the session went wrong.
- **Result:**
  - SWE-bench counts a task as Resolved only when every FAIL_TO_PASS test passes (the bug is fixed) and every PASS_TO_PASS test still passes (nothing broke).
  - The custom suite uses the same rule with hidden acceptance and regression tests.
- **Scores:** the Dashboard and Results pages show, per benchmark, each assistant's resolved/completed count, a 95% range, and median time, prompts and interventions. Tooling failures never count. Report exact counts such as "7/12". Download data from Exports and data.

## Tests

| Command | Checks |
|---|---|
| `npm test` | Python, backend and frontend tests |
| `npm run typecheck` | TypeScript |
| `npm run lint:python` | Ruff |
| `npm run evaluator:env` | Docker, Ruff, Semgrep and the SWE-bench harness are reachable |

## Common problems

| You see | Fix |
|---|---|
| `ECONNREFUSED` / "could not start the API server" | Port busy: keep `PORT=4100` in `.env`, run `wsl --shutdown` in PowerShell, restart |
| "Docker engine is not reachable" / `DockerException` | Start Docker Desktop and turn on WSL integration for Ubuntu, then Re-evaluate |
| SWE-bench tasks "Dataset not downloaded" | Run the `pilot.py select` command, then Synchronise tasks |
| First SWE-bench scoring is slow | Normal: it downloads that repository's Docker image once |
| "disk I/O error" | Run the app from Ubuntu only, never from Windows and Ubuntu at once |

## Next steps

1. Finish all 48 SWE-bench runs, in the experiment's order.
2. Optionally run the 144-run custom suite.
3. Export, then run `npm run analyze -- --input <export.csv> --benchmark swebench_verified`.
4. Run `python paper/build_tables.py`, then recompile `paper/main.tex`. Fill in the author names.

More detail: `README.md` and `docs/scoring-and-key-links.md`.
