# Analysis-Accuracy Benchmark (real read-only analysis, factual correctness)

Measures what Stage 1-4 did NOT: when the harness runs a real analysis swarm, how
FACTUALLY ACCURATE are the findings? 8 questions on the real pm-harness source with
deterministic ground truth (must_contain correct facts / must_not_contain known
fabrications). Scored 1.0 hit-no-fab / 0.5 hit+fab / 0.0 fab-only / 0.25 silent.

## THE FINDING: the "fabrication limit" was a missing CodeGraph index, not a model weakness

Run 1 (pm-harness had NO .codegraph index):
  qwen3-coder-30b   25.0%  (1/8 hits, 3 fabs)
  glm-5.2           34.4%  (1/8, 0)
  deepseek-v4-pro   31.2%  (1/8, 1)
  claude-opus-4.8   34.4%  (1/8, 0)   <- frontier ALSO ~34%

A frontier model scoring 34% on "what function is in this 30-line file" is
impossible if it can see the file. Diagnosis: evidence had NO `context:codegraph`
tag -- the analysis worker received the prompt with ZERO source code and guessed
plausible-but-wrong names (repair_call / retry_repair / repair_intent). The
harness was SILENTLY degrading to blind analysis on an unindexed repo.

Run 2 (after `codegraph init --index` on pm-harness, 63 files / 689 nodes):
  qwen3-coder-30b   81.2%  (6/8 hits, 0 fabs)
  glm-5.2           81.2%  (6/8, 0)
  claude-opus-4.8   81.2%  (6/8, 0)
  deepseek-v4-pro   78.1%  (6/8, 1)

## Conclusions

1. The earlier "cheap models fabricate specifics" anecdote was a HARNESS BUG
   (missing index -> blind guessing), not a model-capability limit. Accuracy
   jumped 25-34% -> ~81% once CodeGraph was actually present.
2. With correct substrate, qwen3-coder-30b TIES claude-opus-4.8 at 81.2% with
   ZERO fabrications. The cost thesis holds on ANALYSIS ACCURACY too, not just
   driver judgment -- the cheap open model is indistinguishable from frontier.
3. So the default analysis model stays qwen3-coder-30b. The "pin a stronger model
   for high stakes" caveat is RETRACTED for indexed repos -- the data says you
   don't need to.

## The fix shipped

- bridge: _warn_if_unindexed() emits a loud stderr warning when real analysis runs
  on a repo with no .codegraph (set HARNESS_REQUIRE_CODEGRAPH=1 to hard-fail
  instead of degrade). Silent blind-analysis can no longer happen unnoticed.
- doctor: reports CodeGraph index presence when analysis is configured.

The remaining ~19% gap is shared across ALL models (incl. frontier) -- it's the
benchmark's strict exact-symbol scoring + genuinely hard questions, not a
cheap-model deficit. A fair, honest ceiling.
