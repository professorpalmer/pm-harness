# Stage 3.5 Results -- Budget-Aware Multi-Turn (LIVE)

Fixes the Stage 3 confound: (1) substantive findings substrate fed after each swarm (gold-fixture, labeled scaffolding -- real PM still executes), (2) explicit orchestration budget in the system prompt, (3) vague/explicit prompt variants. Sharper scorer penalizes budget overrun AND premature stop.

| Model | Score | terminate | budget-ok | efficient | tok_out | latency |
|-------|-------|-----------|-----------|-----------|---------|---------|
| stub-oracle-v2 | 100.0% | 100% | 100% | 100% | 169 | 0ms |
| gemini-frontier | 100.0% | 100% | 100% | 100% | 647 | 5855ms |
| claude-frontier | 100.0% | 100% | 100% | 100% | 929 | 2871ms |

## The result: Stage 3's spread was a HARNESS CONFOUND, now confirmed

claude-opus-4-8 went 55% (Stage 3) -> 100% (Stage 3.5). The loop-burn vanished the moment it had (a) a substantive findings digest to react to and (b) an explicit budget signal. It terminated correctly on all 8 episodes incl. both vague variants, within budget every time. Gemini likewise 100%.

Interpretation: Claude was never a bad driver -- Stage 3's thin demo-artifact substrate was starving it, and a careful model correctly kept digging under a broken signal. The confound flagged in Stage 3 is now empirically confirmed.

## Architectural lesson (pro-thesis)

Driving quality is as much about HARNESS feedback design + budget signaling as model choice. A well-designed harness (substantive artifacts + explicit budget) makes even frontier models behave economically. The orchestration layer's design is a lever on cost/behavior -- a point IN FAVOR of a purpose-built PM-native harness, not just model selection.

## Honest limit -> Stage 4

At 100% across the board, this V2 battery is now SATURATED for frontier models. It successfully de-confounded (proved harness > model for the Stage 3 spread) but does not yet RANK strong drivers. Next discriminating axis: harder multi-swarm episodes (budget 3+, min_swarms 2: investigate -> narrow -> conclude) and genuine traps (stop-early-correct vs premature). That is Stage 4.
