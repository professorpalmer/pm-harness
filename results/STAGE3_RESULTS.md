# Stage 3 Results — Multi-Turn Driving Eval (LIVE)

4 episodes. Driver acts -> Puppetmaster executes -> artifacts fed back -> driver decides next step -> terminate or turn-guard (max 6). Trajectory scoring: terminated / correct terminal action / efficient (swarm count in range) / all-valid / grounded.

| Model | Score | terminate | action | efficient | valid | tok_out | latency |
|-------|-------|-----------|--------|-----------|-------|---------|---------|
| stub-oracle-mt | 100.0% | 100% | 100% | 100% | 100% | 82 | 0ms |
| gemini-frontier | 77.5% | 75% | 75% | 75% | 100% | 805 | 13693ms |
| claude-frontier | 55.0% | 50% | 50% | 50% | 100% | 1841 | 9637ms |

## Key finding

Multi-turn DISCRIMINATES where single-turn SATURATED. The differentiator is TERMINATION + EFFICIENCY (knowing when to stop), not JSON validity (100% across the board).

Counter-intuitive: claude-opus-4-8 (perfect 100% single-turn) scored WORST multi-turn (55%) -- on two 'investigate' episodes it never terminated, running the swarm 6x (turn guard) instead of investigating once and concluding. Gemini did this on 1 of 2. The instinct under a vague 'investigate' prompt is to keep going -- exactly the loop-burn failure mode a PM-native harness must defend against, and now measurable.

## Honest confound (Stage 3.5 to address)

Absolute scores are sensitive to HARNESS DESIGN, not just model capability: the local-adapter swarm returns DEMO artifacts (thin), so a careful model legitimately keeps digging. valid=100% everywhere confirms nobody broke the contract; they differed on judgment under this specific loop. Before these scores RANK models definitively, Stage 3.5 must: feed real findings substrate, add an explicit turn/cost budget signal, and vary prompts. The eval mechanism is proven; the absolute leaderboard needs a richer substrate.
