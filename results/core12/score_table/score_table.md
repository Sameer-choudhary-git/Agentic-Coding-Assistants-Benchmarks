# Score table

Source: `codex-core12-results.csv, copilot-core12-results.csv`. Completed effective runs only; seed 20261121, 5000 bootstrap samples.

## 1. Main results

| Assistant | Completed | Resolved | Success [95% CI] | Domain-balanced [95% CI] | Quality (all) | Quality (resolved) | vs reference | Regressions |
|---|---|---|---|---|---|---|---|---|
| codex | 12 | 6 | 50.0% [25.4%, 74.6%] | 50.0% [33.3%, 66.7%] | 98.6 | 97.4 (n=6) | -0.3 | 2 |
| copilot | 12 | 7 | 58.3% [32.0%, 80.7%] | 58.3% [41.7%, 75.0%] | 99.3 | 98.8 (n=7) | +0.6 | 2 |

## 2. Success by domain (resolved / completed)

| Assistant | Bug fix | Feature | Frontend/visual | Performance | Refactoring | Security fix |
|---|---|---|---|---|---|---|
| codex | 2/2 | 0/2 | 0/2 | 2/2 | 1/2 | 1/2 |
| copilot | 1/2 | 2/2 | 0/2 | 2/2 | 1/2 | 1/2 |

## 3. Code quality sub-scores (mean, 0–100)

| Assistant | n | Reliability | Complexity | Maintainability | Security | Hygiene | Size |
|---|---|---|---|---|---|---|---|
| codex | 11 | 100 | 97 | 100 | 100 | 96 | 93 |
| copilot | 12 | 100 | 98 | 100 | 100 | 97 | 100 |

## 4. Pairwise comparisons (paired on the same task and attempt)

| A | B | Paired | A rate | B rate | Only A | Only B | McNemar p (Holm) | Quality A−B [95% CI] |
|---|---|---|---|---|---|---|---|---|
| codex | copilot | 12 | 50.0% | 58.3% | 1 | 2 | 1.000 (1.000) | -0.7 [-1.5, 0.0] |

Domain-balanced success is the mean of the per-domain success rates, so a domain with more tasks does not dominate. With 5 tasks per domain, per-domain rates are very uncertain; report them as exploratory.
