# REST API (v1)

Base URL: `http://127.0.0.1:4000/api/v1`. All bodies are JSON. Errors have the form
`{"error": {"code": "...", "message": "...", "details": ...}}` with meaningful status codes:
400 `validation_error` / `bad_request` / `invalid_json`, 404 `not_found`, 409 `conflict` (invalid
lifecycle transition), 413 `payload_too_large`, 422 `unprocessable` / `patch_rejected`, 500 `internal_error`.
Identifiers in paths must match `^[A-Za-z0-9_-]{1,64}$`.

The examples below are real responses captured from the running server (long fields shortened with `…`).

## Health

`GET /health`

```json
{"status":"ok","version":"1.0.0","time":"2026-11-05T18:17:25.532Z","database":{"schemaVersion":1},"tasks":18,
 "evalMode":"local","automationEnabled":false,"operator":"reviewer","machineId":"vm","workspaceRoot":"/home/me/acb-workspaces"}
```

`GET /health/evaluator?mode=docker` — runs `evaluator.cli env`: Python, Ruff, Semgrep and Docker availability.

## Tasks

| Method | Path | Description |
|---|---|---|
| GET | `/tasks?category=&difficulty=&validation=&q=` | List tasks (no prompt text). |
| GET | `/tasks/:taskId` | Task with frozen prompt, acceptance-test descriptions, starter file list, hashes, validation, and all versions seen. Hidden test code and reference solutions are never returned. |
| GET | `/tasks/:taskId/starter?path=pager/paginate.py` | Content of one starter file listed in the manifest (404 for anything else). |
| POST | `/tasks/sync` | Re-read `benchmark_tasks/` through the evaluator. |

## Assistants

| Method | Path | Description |
|---|---|---|
| GET | `/assistants` | Capability status, detail, detected version, operator-reported version/model, manual instructions. |
| POST | `/assistants/detect` | Re-run capability detection. |
| PATCH | `/assistants/:id` | Body `{"version": "1.2.3" or null, "model": "…" or null}`. |

## Experiments

`POST /experiments/preview` and `POST /experiments` take:

```json
{"name":"Full study","description":"","taskIds":["BF-01","BF-02"],"assistantIds":["copilot","codex"],"attempts":2,
 "executionMode":"human","evalMode":"docker","timeLimitOverrideMinutes":null,"randomizeOrder":true,"seed":2026,
 "allowUnvalidatedTasks":false}
```

Preview response:

```json
{"plannedAttempts":8,"tasks":2,"assistants":2,"attempts":2,"formula":"2 tasks × 2 assistants × 2 attempts",
 "unvalidatedTasks":[],"unknownTasks":[],"evalMode":"local",
 "warnings":["Local evaluation mode runs submitted code on this machine without network or filesystem isolation."]}
```

Create returns `201 {"experiment": {...}, "plannedAttempts": 8}`; unvalidated tasks give `422` unless
`allowUnvalidatedTasks` is true. Validation failure example (`POST /experiments {"name":"x"}`):

```json
{"error":{"code":"validation_error","message":"Request validation failed","details":[{"code":"too_small","minimum":3,
 "path":["name"],"message":"String must contain at least 3 character(s)"},{"code":"invalid_type","expected":"array","path":["taskIds"],"message":"Required"}, …]}}
```

| Method | Path | Description |
|---|---|---|
| GET | `/experiments` | List with progress counts. |
| GET | `/experiments/:id` | `{experiment, progress, plannedAttempts, runs}`. |
| POST | `/experiments/:id/start` | Creates one `planned` run per planned attempt; `409` if already started. |
| POST | `/experiments/:id/status` | `{"status":"completed"}` or `{"status":"archived"}`. |

## Runs

| Method | Path | Body | Transition |
|---|---|---|---|
| GET | `/runs?experimentId=&status=&assistantId=&taskId=&limit=` | | |
| GET | `/runs/:id` | | Detail: run, prompt, assistant, evaluations, test outcomes, findings, artifacts, events, sibling runs |
| POST | `/runs/:id/prepare` | | planned → ready (creates workspace) |
| POST | `/runs/:id/start` | `{"assistantVersion"?, "model"?}` | ready → running |
| POST | `/runs/:id/log` | `{"type":"iteration"\|"intervention"\|"note","note":""}` | while running |
| POST | `/runs/:id/stop` | | running → awaiting_human |
| POST | `/runs/:id/submit` | see below | running/awaiting_human → submitted → evaluating (202) |
| POST | `/runs/:id/evaluate` | | submitted/completed/failed(evaluator_error) → evaluating (202) |
| POST | `/runs/:id/automate` | | ready → running → submitted (headless CLI; 409 unless supported) |
| POST | `/runs/:id/retry` | | failed/invalidated (latest run only) → new run, 201 |
| POST | `/runs/:id/fail` | `{"failureClass":"environment_error"\|"adapter_error"\|"operator_abort","message":"…"}` | → failed |
| POST | `/runs/:id/invalidate` | `{"reason":"at least 5 characters"}` | → invalidated |
| PATCH | `/runs/:id/labels` | `{"failureModes":["incomplete_implementation"],"notes":"…"}` | |
| GET | `/runs/:id/artifacts/:artifactId` | | Download a registered artifact |

Submit body:

```json
{"submissionType":"workspace","iterations":2,"humanInterventions":1,"notes":"…","assistantVersion":"…","model":"…","autoEvaluate":true}
{"submissionType":"patch","patch":"--- a/pager/paginate.py\n+++ b/pager/paginate.py\n@@ …"}
{"submissionType":"files","files":[{"path":"pager/paginate.py","content":"…"}]}
```

Invalid transition example: `POST /runs/<planned run>/start` →
`409 {"error":{"code":"conflict","message":"cannot start a run in status 'planned'","details":{"allowed":["ready"]}}}`.

Run object (excerpt):

```json
{"id":"a4c08f31-…","plannedAttemptId":"22041e94-…","experimentId":"84bc7412-…","taskId":"BF-02","assistantId":"codex",
 "attemptNumber":2,"runNumber":1,"retryOfRunId":null,"status":"completed","executionMode":"human","evalMode":"local",
 "taskHash":"f342ff91…","promptHash":"b6e10fd2…","workspacePath":"…/BF-02_a4c08f31_r1","assistantVersion":null,
 "assistantVersionSource":"unknown","timeLimitSeconds":1500,"wallClockSeconds":512.4,"timedOut":false,"iterations":2,
 "humanInterventions":1,"failureClass":null,"success":true,"outcome":"passed", …}
```

## Results and exports

`GET /results/summary?experimentId=` — totals, overall and per-assistant / per-category /
per-assistant×category aggregates (see `metrics-and-data-dictionary.md`). Excerpt:

```json
{"hasData":true,"totals":{"tasks":18,"validatedTasks":18,"assistants":4,"experiments":1,"plannedAttempts":144,"runsRecorded":144},
 "byAssistant":[{"assistantId":"codex","planned":36,"completed":4,"successes":3,"successRate":0.75,
   "successCi95":{"low":0.3006,"high":0.9544},"intentToTreatRate":0.0833,"operationalFailures":1, …}], …}
```

`GET /results/records?experimentId=` — flat records (one per run).

`GET /results/export?format=<f>&experimentId=` with `f` in `jsonl`, `csv`, `config`, `summary_csv`,
`dictionary`, `dictionary_md`, `manifest`, `bundle` (bundle requires `experimentId`). Returned as a
file download.

`POST /results/export-all` `{"experimentId"?: "…"}` — writes all formats plus `CHECKSUMS.json` to
`artifacts/exports/<timestamp>-<id>/`.

`POST /results/import` — body is a bundle file. Response:
`{"inserted":{"runs":12,…},"skippedIdentical":{…},"conflicts":[{"table":"runs","id":"…","reason":"…"}],"warnings":[…]}`.
Tampered bundles (checksum mismatch) are rejected with 400.

## Events

`GET /events?limit=20` — most recent audit events.
