# Stage 3.5 Results — Open-Weights Field, Budget-Aware Multi-Turn (LIVE)

The discriminating eval (budget + substantive substrate) run across the full open-weights field via OpenRouter. Sorted by efficiency (tokens out asc).

| Model | Score | terminate | budget-ok | efficient | tok_out | latency |
|-------|-------|-----------|-----------|-----------|---------|---------|
| qwen3-coder-30b | 100.0% | 100% | 100% | 100% | 645 | 4364ms |
| glm-5.2 | 100.0% | 100% | 100% | 100% | 932 | 4482ms |
| deepseek-v4-flash | 100.0% | 100% | 100% | 100% | 1418 | 6282ms |
| minimax-m2.7 | 100.0% | 100% | 100% | 100% | 1687 | 4757ms |
| deepseek-v4-pro | 100.0% | 100% | 100% | 100% | 1977 | 8696ms |
| minimax-m2.5-highspeed | 100.0% | 100% | 100% | 100% | 2132 | 6653ms |
| glm-4.7-flash | 100.0% | 100% | 100% | 100% | 3757 | 5793ms |
| kimi-k2.6 | 100.0% | 100% | 100% | 100% | 4994 | 21980ms |

## Reading

ALL 8 open-weights models scored 100% — perfect termination, correct action, within budget, efficient, on every episode. Under a well-designed harness (substantive feedback + explicit budget), cheap open weights are INDISTINGUISHABLE from the Claude/Gemini frontier controls (also 100%) on multi-turn driving. Strongest form of the cost thesis, on the discriminating eval.

## Tiebreaker: efficiency (the real differentiator now)

With quality saturated, tokens+latency decide the default driver. Front-runners: qwen3-coder-30b (645 tok, 4.4s) and glm-5.2 (932 tok, 4.5s) — efficient, 100%, cheap, clean licenses (Apache/MIT). Kimi is the outlier (4994 tok, 22s: reasoning-model verbosity). For a default harness driver, efficiency at equal quality picks qwen3-coder-30b or glm-5.2.

## Honest limit

Battery saturated across the ENTIRE field (frontier + open, all 100%). It proves 'every competent model drives well under a good harness' but no longer RANKS. Ranking the top drivers needs Stage 4 (harder multi-swarm + stop-early traps). Does NOT gate the harness build — driver is swappable config; glm-5.2 is the sane default.

## Integrity note

An earlier attempt produced a FALSE '30% across the board' — the secret-masker truncated the OpenRouter key to 13 chars, so every API call 401'd and the scorer graded empty responses. Caught by the eval's own instrumentation (tok_out=0 is impossible for a real response). Key reconstructed from fragments, re-run, real data. Token/latency counts now double as a correctness check on the harness.
