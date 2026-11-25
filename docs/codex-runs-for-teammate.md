# Running the Codex runs and merging results

Claude Code is being run on laptop 2 on the 12 tasks below. To compare Codex fairly, run Codex on the **same
12 tasks** in **this app**, then send the exported bundle so both sets of results land in one database.

## The 12 tasks (2 per domain)

| # | Task ID | Domain | Difficulty |
|---|---|---|---|
| 1 | `django__django-16801` | performance | easy |
| 2 | `NodeBB__NodeBB-767973717b` | performance | hard |
| 3 | `faker-ruby__faker-2970` | bug fix | easy |
| 4 | `element-hq__element-web-ce554276db` | bug fix | easy |
| 5 | `tokio-rs__tokio-6724` | feature | easy |
| 6 | `sphinx-doc__sphinx-8035` | feature | medium |
| 7 | `qutebrowser__qutebrowser-44e64199ed` | refactoring | easy |
| 8 | `element-hq__element-web-27139ca68e` | refactoring | medium |
| 9 | `caddyserver__caddy-6115` | security fix | easy |
| 10 | `NodeBB__NodeBB-97c8569a79` | security fix | easy |
| 11 | `diegomura__react-pdf-1280` | frontend | easy |
| 12 | `processing__p5-js-3709` | frontend | easy |

## Rules (same as the Claude Code runs)

- Same task IDs, 1 attempt each, 30-minute limit per run.
- Use the frozen prompt the app gives. Do not add hints.
- **No web search or browsing** in Codex.
- Pin and write down the Codex model (for example the one `codex` shows at start-up).
- Claude Code runs **headless** (`claude -p`). Prefer Codex headless too: `codex exec ...` (step 4b).
  If you use Codex by hand in an editor instead, tell us, because the paper must report the mode difference.

## Steps

1. **Set up the app** on your laptop (once): follow `docs/EVALUATION_GUIDE.md` section A2 (Ubuntu/WSL,
   Docker Desktop with WSL integration, Node 22, Python venv). In `.env` set your own name:
   `ACB_OPERATOR=<your-name>`.
2. **Start the app** from Ubuntu: `npm run dev`, then open http://127.0.0.1:5173
   (or the port in your `.env`).
3. **Create the experiment:** Experiments → New → benchmark **Golden** → select only the 12 task IDs above →
   assistant **OpenAI Codex** → attempts **1** → create → *Start experiment*.
4. **Do each run** (*Open next run in order*):
   - a. **Manual:** Create workspace → Start session timer → Copy frozen prompt → run Codex in that workspace
     folder → log any extra prompts / manual help → Stop timer → **Submit and evaluate**.
   - b. **Headless (recommended):** install the Codex CLI in Ubuntu and log in (`codex login`), set
     `ACB_ENABLE_AUTOMATION=1` in `.env`, restart the app, then on each run click
     **Run headless CLI instead**. Or run all of them with
     `python scripts/batch_run.py --name "Codex core-12" --assistant codex --tasks <the 12 IDs>`.
     To stay within usage limits, add `--max-runs 1` and continue later with
     `python scripts/batch_run.py --experiment <id> --max-runs 1` until it reports 0 left.
   - Codex model: put the model **id** in `.env`, e.g.
     `ACB_CODEX_CMD=["codex","exec","-m","<id>","-c","model_reasoning_effort=medium","--sandbox","workspace-write","--skip-git-repo-check","{prompt}"]`
     (`grep ^model ~/.codex/config.toml` shows the id). Install `bubblewrap` (`sudo apt install -y bubblewrap`).
   - Leave changes uncommitted. Do not edit the code yourself.
5. If a SWE-bench Pro run fails with `error getting credentials`, remove `credsStore` from `~/.docker/config.json`,
   `docker pull` the task's image, then **Re-evaluate submission** (the agent is not rerun).
6. **Check** the Results page: every run is scored (resolved / not resolved). If scoring failed because of
   Docker or tooling, press **Re-evaluate submission**.
7. **Export:** Exports page → choose your experiment → **Team exchange bundle (JSON)** → download.
8. **Send** that `.json` file. It is imported on laptop 2 with Exports → Import (or
   `npm run import-bundle --workspace backend -- <file>`). Identical records are skipped; nothing is overwritten.

After the import, the Results page and the score tables show Claude Code and Codex side by side.

**Do not** run Claude Code on these tasks on your laptop (that is being done on laptop 2): the same
(task, agent, attempt) must never be run on both laptops.
