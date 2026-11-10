# Requirements review: conflicts and open questions

The build prompt says to document genuine conflicts with the supplied research documents (the
B.Tech synopsis, the paper outline and the detailed research plan) rather than silently change the
protocol. These are the points found, with the choice made and what needs the team's decision.

| # | Topic | Documents say | Implemented | Needs decision? |
|---|---|---|---|---|
| 1 | Persistence | Synopsis and research plan: JSON/JSONL files, "without a database". Build prompt: SQLite + JSON/JSONL artifacts. | Both: SQLite for application records; JSON/JSONL/CSV exports and per-run JSON reports as the research artifacts. Exports contain everything needed without the database. | Confirm SQLite is acceptable to the guide. |
| 2 | Benchmark source | Synopsis lists SWE-bench / SWE-bench Verified + custom tasks and a SWE-bench harness. Research plan and build prompt: 18 synthetic Python tasks only. | 18 synthetic tasks. SWE-bench is used only as related work for positioning, not run by the platform. | Confirm that SWE-bench execution is out of scope for Project-I. |
| 3 | ESLint / Jest | Synopsis lists ESLint and Jest. | All tasks are Python, so ESLint/Jest do not apply to submissions. They are not used. | No (document in the methods section). |
| 4 | Amazon Bedrock judge | Synopsis: optional LLM provider for helper/judge analysis. | Not implemented: the build prompt forbids combining unlike metrics, and LLM-as-judge would add an unvalidated, paid dependency. Blinded human review is supported instead. | Confirm it is dropped. |
| 5 | "Compilation validation" | Research plan mentions compilation checks. | Python has no compile step; import/syntax failures surface as `collection_error` outcomes. | No. |
| 6 | "Test assertion coverage" | Research plan: evaluator computes assertion coverage. | Line coverage of the target module and mutation score are computed for test-writing tasks; assertion counting is not. | Confirm line coverage + mutation score is acceptable. |
| 7 | Blinded patch reviews | Research plan: two members independently review patches, blinded. | Supported procedurally (protocol §7, failure-mode labels per run, exports without assistant name). There is no dedicated two-reviewer UI with stored per-reviewer labels or agreement statistics. | Decide whether per-reviewer labels must be stored in the platform. |
| 8 | Node version | Research plan: Node 20 LTS or newer. | Node ≥ 22.13 required (built-in SQLite; Node 20 reached end of life in April 2026). | No. |
| 9 | Python version | Research plan: Python 3.12+. | Works with 3.10+; Docker sandbox uses 3.12. Use 3.12 locally for the study. | No. |
| 10 | Group identifiers | Synopsis: Group Key A6. Research plan: Group Key/ID DTU/CSE/BTP/GP045 with "Group Key-A6" in footers. | Not used by the software. | Check which ID the department expects. |
| 11 | Model configuration | Research plan quota table names "Cursor (Claude-3.5-Sonnet / GPT-4o)" and "GitHub Copilot (Latest Engine)". | Models are recorded per run as reported by the operator; nothing is assumed. Those model names are outdated for a November 2026 study. | Update the plan's table to the models actually available when runs are executed. |
| 12 | Schedule | Research plan: Config A/B runs 24–29 Oct, C/D runs 30 Oct–04 Nov 2026. | The platform is delivered on 5 Nov 2026. | Revise the timeline with the guide. |
| 13 | Difficulty levels | RQ2 stratifies by "assigned difficulty levels". | Each task has easy/medium/hard with a written rationale; distribution is uneven (5 easy, 8 medium, 5 hard) because difficulty follows the task, not a quota. | Confirm, or adjust labels before validation is frozen. |
