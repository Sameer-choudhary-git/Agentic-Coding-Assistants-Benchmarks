# Literature summary: agentic coding assistants

Every paper in the outline's reading list, checked against its source on 9 November 2026. Figures match the source text; where a source contradicts itself or the outline, the caution says so. The machine-readable version is `evidence/sources.json` and `evidence/evidence.json`.

## How the papers fit the outline

| Outline section | Papers |
|---|---|
| I. Introduction (positioning) | Pinna et al. (closest prior work), AIDev |
| II. Background (agent architecture) | SWE-agent, AutoCodeRover, OpenHands |
| III. Methodology (data sources) | SWE-bench, SWE-bench Verified, AIDev |
| V-A Benchmarks | SWE-bench, Verified, SWE-Bench+, Multimodal, SWE-smith, SWE-Bench++, Chen et al. |
| V-B/C PR acceptance, task type | Li et al. 2025, Rahman et al., Mazloomzadeh et al., Pinna et al., Cynthia et al. (core/peripheral) |
| V-D Post-merge quality | Cynthia et al. (post-merge), TDAD, Mazloomzadeh et al. |
| V-E Productivity | Peng et al., Cui et al., Bhati |
| VI Risks | Perry et al., Pearce et al., Rahman et al., SWE-Bench+ |

## Corrections to the outline

- **AIDev size.** 932,791 PRs and 116,211 repositories come from the MSR 2026 dataset paper (arXiv:2602.09185), not from arXiv:2507.15003. The 2025 preprint (v1) reports 456,535 PRs in 61,453 repositories. Cite 2602.09185 for the larger figure.
- **The 29-point gap** is in version 1 of Pinna et al. (chore 84.0% vs performance 55.4%). Version 2 (May 2026) headlines a 16-point gap instead (docs 82.1% vs features 66.1%). Name the version.
- **SWE-bench Verified has 500 tasks.** One survey (arXiv:2604.26275) says 489. Use OpenAI's 500.

## Agentic pull-request studies

### Pinna, Gong, Williams, Sarro (2026). Comparing AI Coding Agents: A Task-Stratified Analysis of Pull Request Acceptance. MSR 2026. arXiv:2602.08915
- **What it is:** the closest prior work. It covers five agents (Codex, Copilot, Devin, Cursor, Claude Code) and 7,156 AIDev PRs, stratified by task type.
- **Findings:** task type strongly affects acceptance. The gap is 29 pp in v1 (chore 84.0%, perf 55.4%). No agent leads everywhere:
  - Claude Code leads docs (92.3%) and features (72.6%).
  - Codex ranges from 59.6% to 88.6% across nine categories.
  - Devin is the only agent with a steady upward trend (+0.77%/week over 32 weeks).
- **Use:** Section I must say what we add, namely the feature comparison, synthesis beyond acceptance, risks, and open instruments.
- **Caution:** the abstract says Cursor leads fix tasks (80.4%), but Section 4.3 gives Codex 83.0% on fix.

### Mazloomzadeh, Morovati, Khomh (2026). How Do AI Coding Agents Contribute to Software Development? An Empirical Study of Agentic Pull Requests. Proc. ACM Meas. Anal. Comput. Syst. 37(4). arXiv:2607.21832
- **Data:** 220,612 closed PRs from 489 Python repositories, of which 9,428 are agentic.
- **Findings:** GLMM merge probabilities are Claude Code 84.3%, Codex 73.5%, Cursor 63.9%, Copilot 59.6% and Devin 43.0%. Claude Code and Codex do not differ significantly.
- **Findings:** there is no systematic change across quarters, and human PRs merge 84–86% of the time.
- **Findings:** CI, dependency and docs topics merge most often; LLM integration and model evaluation merge least.
- **Findings:** agentic and human PRs differ only slightly in size, time to merge and defect proneness.
- **Caution:** Table 1's column labels look inconsistent, so use the RQ1 estimates.

### Rahman, Rabbi, Zibran (2026). A Task-Level Evaluation of AI Agents in Open-Source Projects. MSR 2026. arXiv:2602.02345
- **Data:** 33,549 AIDev PRs from repositories with more than 100 stars, across 12 task types.
- **Mean acceptance:** Codex 0.83, Cursor 0.67, Claude 0.66, Devin 0.55, Copilot 0.45.
- **Review:** 90.6% of PRs have no recorded review comments (98.2% for Codex). Copilot draws the most discussion (2.56 comments per PR including bots).
- **Commit messages:** commit-message quality does not track acceptance. Claude has the best (0.68) and Codex the worst (0.32).

### Li, Zhang, Hassan (2025). The Rise of AI Teammates in Software Engineering (SE) 3.0. arXiv:2507.15003
- **Data:** first AIDev release (v1: 456,535 PRs). AIDev-pop covers repositories with more than 500 stars and has 7,122 agent PRs.
- **Merge rates:** humans 76.8%; Codex 65.3%, Claude Code 52.5%, Cursor 51.4%, Devin 48.9% and Copilot 38.2%.
- **By task type:** agents trail humans by 15–40 pp on features, fixes and performance. On docs they beat humans (Codex 88.6%, Claude Code 85.7%, humans 76.5%).
- **Review:** 58.2% of agent PRs have no review, against 75.3% of human PRs.
- **Attribution:** Codex leaves no authorship trace, and Claude Code's co-author line can be disabled.

### Li, Zhang, Hassan (2026). AIDev: Studying AI Coding Agents on GitHub. MSR 2026. arXiv:2602.09185
- **Contents:** the dataset paper. It has 932,791 agentic PRs, 116,211 repositories and 72,189 developers from five agents, with a 1 Aug 2025 cutoff.
- **Curated subset:** 33,596 PRs from 2,807 repositories, with comments, reviews, commits and timelines.
- **Where to get it:** Hugging Face `hao-li/AIDev`, Zenodo 10.5281/zenodo.16899501, or GitHub `SAILResearch/AI_Teammates_in_SE3`.

### Cynthia, Das, Roy (2026). Are We All Using Agents the Same Way? Core and Peripheral Developers. MSR 2026. arXiv:2601.20106
- **Data:** 9,427 agentic PRs (Claude Code, Cursor, Copilot, Codex) from 1,701 developers.
- **Acceptance:** core developers accept 72.8% and peripheral developers 72.3%. Core developers merge into main more often (85.8% vs 77.8%).
- **Delegation:** core developers delegate more testing and documentation work.
- **Modification:** 74.1% of PRs are accepted without modification.
- **CI:** peripheral developers merge with no CI checks 19.1% of the time, against 11.2% for core developers.

### Cynthia, Muttakin, Roy (2026). Beyond Bug Fixes: Post-Merge Code Quality Issues in Agent-Generated PRs. MSR 2026. arXiv:2601.20109
- **Data:** SonarQube run on base and merged commits of 1,210 merged bug-fix PRs from Python repositories.
- **Issues found:** 1,190 in total:
  - 1,059 code smells (89%)
  - 48 bugs
  - 83 security hotspots
  - 0 vulnerabilities
- **By agent:** differences between agents disappear once counts are normalised by churn.
- **Takeaway:** a merge does not show that the code is good.
- **Caution:** the Claude Code (15) and Cursor (40) samples are small.

### Bhati (2026). Agentic AI in the Software Development Lifecycle. arXiv:2604.26275 (single author, under review)
- **Contents:**
  - a six-layer reference architecture
  - an "Agentic SDLC"
  - productivity evidence in three tiers: controlled experiments, field experiments and longitudinal team studies, with effects shrinking from tier to tier
  - a SWE-bench Verified trajectory from 1.96% (2023) to about 78% (2026)
- **Caution:** it says Verified has 489 tasks; the correct number is 500.
- **Caution:** its field-experiment citation points to the wrong reference, so cite Cui et al. directly.
- **Caution:** its tool-level scores are approximate.

## Benchmarks and agent systems

### Jimenez et al. (2024). SWE-bench: Can Language Models Resolve Real-World GitHub Issues? ICLR 2024. arXiv:2310.06770
2,294 issues from 12 Python repositories. The best baseline, Claude 2, resolved 1.96%.

### OpenAI (2024). Introducing SWE-bench Verified
- **Size:** 500 instances, chosen from 1,699 annotated by 93 developers (3 labels each).
- **Filtering:** 68.3% of samples were removed, mainly for underspecified issues or unfair tests.
- **Effect on scores:** GPT-4o scored 33.2% on Verified against 16% on the original benchmark.

### Yang et al. (2024). SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. NeurIPS 2024. arXiv:2405.15793
- **Idea:** a purpose-built interface for searching, viewing and editing files.
- **Results:** 12.5% pass@1 on SWE-bench and 87.7% on HumanEvalFix.

### Zhang, Ruan, Fan, Roychoudhury (2024). AutoCodeRover: Autonomous Program Improvement. ISSTA 2024. arXiv:2404.05427
- **Idea:** code search over AST structure plus spectrum-based fault localisation.
- **Results:** 19% on SWE-bench Lite (300 issues) at about $0.43 per issue.

### Wang et al. (2025). OpenHands: An Open Platform for AI Software Developers as Generalist Agents. ICLR 2025. arXiv:2407.16741
- **What it is:** an open platform where agents write code, use a shell and browse.
- **Evaluation:** 15 benchmarks, including SWE-bench and WebArena.
- **Community:** more than 188 contributors.

### Aleithan et al. (2024). SWE-Bench+: Enhanced Coding Benchmark for LLMs. arXiv:2410.06992
- **Problems found in passing patches:** in 32.67% the solution was leaked in the issue text, and 31.08% passed only because the tests were weak.
- **Effect on Verified:** after filtering, SWE-Agent+GPT-4 falls from 22.4% to 10.0%.
- **New benchmark:** SWE-Bench+ has 548 post-cutoff issues. AutoCodeRover falls from 18.83% to 3.83% on it.
- **Caution:** the paper gives two different filtered rates (3.97% and 5.49%).

### Yang et al. (2024). SWE-bench Multimodal. arXiv:2410.03859
- **Size:** 617 JavaScript instances from 17 libraries, each with images.
- **Results:** the best system (SWE-agent) scored 12%; the next best scored 6%.

### Yang et al. (2025). SWE-smith: Scaling Data for Software Engineering Agents. NeurIPS 2025. arXiv:2504.21798
- **Data:** 50k synthetic task instances from 128 repositories.
- **Result:** SWE-agent-LM-32B reaches 40.2% on Verified.

### Wang et al. (2025). SWE-Bench++. arXiv:2512.17419
- **Size:** 11,133 instances from 3,971 repositories in 11 languages, built from live PRs.
- **Best result:** 36.2% pass@10 (claude-sonnet-4.5) on a 1,782-instance subset.

### Chen, Ma, Jiang (2026). Beyond Final Code: A Process-Oriented Error Analysis of Software Development Agents. ICSE 2026. arXiv:2503.12374
- **Data:** 3,977 trajectories from 8 agents on Verified.
- **Findings:** resolution falls from 53.8% (no errors) to 22.6% (more than 20 errors). The most frequent errors are ModuleNotFoundError and TypeError. Three SWE-bench platform bugs were confirmed.

### Alonso, Yovine, Braberman (2026). TDAD: Test-Driven Agentic Development. arXiv:2603.17973
- **Idea:** a static code-to-test map, searched with grep before commit.
- **Results:** test-level regressions fall from 6.08% to 1.82% on Verified. TDD prompting alone raised them to 9.94%.
- **Caution:** small samples (100 and 25 instances) and quantised local models.

## Productivity and security

### Peng, Kalliamvakou, Cihon, Demirer (2023). The Impact of AI on Developer Productivity: Evidence from GitHub Copilot. arXiv:2302.06590
- **Design:** controlled experiment with 95 recruited and 35 completers per arm, building a JavaScript HTTP server.
- **Result:** the Copilot group was 55.8% faster (95% CI 21–89%, p = 0.0017). Less experienced developers gained more.

### Cui, Demirer, Jaffe, Musolff, Peng, Salz (2025). The Effects of Generative AI on High-Skilled Work: Three Field Experiments with Software Developers. Management Science. doi:10.1287/mnsc.2025.00535
- **Design:** RCTs at Microsoft, Accenture and a Fortune 100 firm with 4,867 developers.
- **Result:** 26.08% more completed tasks (SE 10.3%), with larger gains for less experienced developers.

### Perry, Srivastava, Kumar, Boneh (2023). Do Users Write More Insecure Code with AI Assistants? ACM CCS 2023, pp. 2785–2799
- **Design:** user study with 47 participants analysed.
- **Results:** participants with an AI assistant produced secure encryption 21% of the time (control 43%). 36% wrote SQL-injectable code (control 7%).
- **Overconfidence:** they rated their code as more secure.

### Pearce, Ahmad, Tan, Dolan-Gavitt, Karri (2025). Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions. CACM 68(2):96–105
Copilot output was tested against MITRE Top-25 CWE scenarios across weaknesses, prompts and domains. The paper is the CACM version of the IEEE S&P 2022 study.
