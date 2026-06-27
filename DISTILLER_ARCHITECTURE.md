# Distiller architecture: programmatic vs agent-driven

Status: decision pending (Cary). Written 2026-06-27 after differential-testing
Marionette's self-learning against the Hermes reference implementation.

## The fork

Marionette and Hermes generate skills/rules from completed work in
fundamentally different ways. This is a genuine design fork worth deciding
deliberately rather than by accident.

### Marionette today: programmatic distiller

`harness/skill_distiller.py` fires automatically after a session
(`_maybe_auto_distill`), computes Jaccard token-similarity for dedup
(`DUP_THRESHOLD=0.6`) and auto-merge (`MERGE_THRESHOLD=0.7`), asks the driver
model for a `{name, description, body}` envelope, and gates the result to
`pending` for human approval.

- Pros: deterministic, testable without an LLM (fake-pilot unit + stress
  tests), fires on its own, explicit thresholds.
- Cons: the thresholds are tunable knobs that can be wrong. Stress testing
  found two real defects in them: an unbounded patch-slug growth crash, and an
  over-eager 0.6 merge that destructively merged distinct skills. Both fixed,
  but they are emblematic: programmatic similarity is a perpetual tuning
  surface.

### Hermes: agent-tool-driven

Hermes has NO programmatic distiller. There is no Jaccard, no threshold, no
auto-merge anywhere in its codebase. Instead:

- A system-prompt directive tells the agent: after a complex task (5+ tool
  calls, errors overcome, a corrected approach), call
  `skill_manage(action='create')` to save the approach as a reusable skill.
- The LLM itself is the judgment about what is skill-worthy and whether a new
  skill duplicates an existing one (it can read the skills list).
- `hermes_cli/curator.py` handles lifecycle only (pin/prune/archive).
  `tools/skill_usage.py` does automatic state transitions
  (active -> stale -> archived by idle days; pinned opts out).

- Pros: no threshold to tune, no dedup math to get wrong, the model's judgment
  is richer than token overlap. Simpler core.
- Cons: non-deterministic (depends on the model choosing to call the tool),
  harder to unit-test the "decide to create" step, relies on the system prompt
  being followed.

## What differential testing can and cannot cover

- CAN diff against Hermes: session-activity detection (tool-call counts, visible
  turn counts) -- `tests/test_differential_hermes.py` imports Hermes'
  `session_recap` as the oracle and asserts Marionette agrees. Validates the
  trigger that decides WHETHER a session did enough work to distill.
- CANNOT diff against Hermes: the dedup/merge logic itself -- Hermes has no
  equivalent. That logic is covered by stress/property tests
  (`tests/test_distiller_broaden.py`), not differential tests. Building a
  "compare merge output to Hermes" test would be fabricated rigor.

## Recommendation (not yet acted on)

The programmatic distiller is working and now hardened, so there is no urgency.
But the honest long-term call is likely a HYBRID:

1. Keep the programmatic trigger (auto-fire on hard-task / findings) -- it is
   the thing Hermes lacks and is genuinely useful (Hermes relies on the agent
   remembering to call the tool).
2. Replace the Jaccard dedup/merge with an LLM judgment call (give the model
   the candidate + the existing skills list, ask "is this new, a duplicate, or
   an update to skill X?") -- this removes the threshold-tuning surface that
   produced both stress-test bugs, matching Hermes' bet that the model is the
   better judge of similarity.
3. Keep the human-in-loop pending gate regardless -- both systems agree on
   this, and it is the right call for an anti-vibe-code ethos.

This is a redesign, not a bug fix. Deferred until Cary decides.
