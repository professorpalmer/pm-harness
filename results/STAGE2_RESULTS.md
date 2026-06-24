# Stage 2 Results — Single-Turn Driver Eval (LIVE)

Battery: 10 labeled tasks (swarm/answer/stop). Swarm cases executed against real Puppetmaster local adapter. Deterministic scoring. Native pricing for cost.

| Model | Tier | Score | json | schema | action | tok_out | cost/run | latency |
|-------|------|-------|------|--------|--------|---------|----------|---------|
| qwen3-coder-30b | value | 100.0% | 100% | 100% | 100% | 539 | $0.00044 | 2344ms |
| deepseek-v4-flash | value | 100.0% | 100% | 100% | 100% | 956 | $0.00066 | 4531ms |
| glm-4.7-flash | value | 100.0% | 100% | 100% | 100% | 3031 | $0.00118 | 5916ms |
| minimax-m2.7 | flagship | 100.0% | 100% | 100% | 100% | 1531 | $0.00267 | 2837ms |
| minimax-m2.5-highspeed | value | 100.0% | 100% | 100% | 100% | 1966 | $0.00641 | 4155ms |
| glm-5.2 | flagship | 100.0% | 100% | 100% | 100% | 856 | $0.00770 | 3966ms |
| deepseek-v4-pro | flagship | 100.0% | 100% | 100% | 100% | 3097 | $0.00833 | 9121ms |
| claude-frontier | frontier_control | 100.0% | 100% | 100% | 100% | 917 | $0.04415 | 2108ms |
| gemini-frontier | frontier_control | 94.0% | 100% | 100% | 90% | 587 | $0.00643 | 4673ms |
| kimi-k2.6 | flagship | 70.0% | 70% | 70% | 70% | 7268 | $0.02201 | 14281ms |

## Reading
- Seven open-weights models tied the Claude Opus control at 100% on single-turn structured driving.
- qwen3-coder-30b drove at $0.00044/run — ~100x cheaper than Claude ($0.044) for identical single-turn score.
- gemini-3.1-pro 94% (one decision miss). kimi-k2.6 70%: reasoning model emitted prose instead of bare JSON on trivial answer cases (harness needs JSON-mode/grammar for thinking models; not a capability ceiling).

## Honest caveat
Single-turn battery is SATURATED (8/10 models at exactly 100%) — it proves the floor (everyone clears the basic contract) but does NOT rank. Multi-turn (Stage 3) is the discriminating eval.
