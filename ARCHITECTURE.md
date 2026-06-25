# pm-harness Architecture

A PM-native harness: a coding/agent front-end whose kernel is Puppetmaster
orchestration, driven by swappable open-weights models, with a durable-state GUI.

This document is the single authoritative reference for how the system works and
why it is built this way. It consolidates the validated research (Stages 1-4)
and the product (`harness/`).

## 1. The thesis

Every mainstream agent harness (Cursor, Claude Code, Hermes) treats orchestration
as a tool the model calls, and runs a frontier model as the top-level narrator.
That narrator pays tokens to *talk about* what it will do before doing it.

pm-harness inverts this: **Puppetmaster orchestration is the kernel**, and a
cheap open-weights model is a swappable *driver* that emits structured intents,
not prose. The harness executes those intents in code. Two consequences:

- **No frontier narrator tax.** The model spends tokens only on decisions, not
  on narrating tool calls.
- **No vendor black box (optionally).** With self-hosted open weights the entire
  stack is inspectable; with a hosted open-weights provider it is merely cheap.
  These are different deployments of one architecture, not one claim.

## 2. The seam (Stage 1, proven live)

Puppetmaster's MCP tools and CLI are both thin transports over one engine:

```
MCP tools   ─┐
             ├─→  CLI `run`  ─→  Orchestrator(store).run(...)   ← the engine
CLI commands ─┘
```

A native harness deletes both transports and calls the engine in-process:

```python
from puppetmaster.store_factory import create_store
from puppetmaster.orchestrator import Orchestrator

store  = create_store("sqlite", state_dir)
result = Orchestrator(store).run(goal, roles=, worker_mode=, on_job_created=)
# RunResult(job, artifacts, summary, summary_path, recovered_tasks,
#           rerouted_tasks, mode)
```

`run()` blocks; live observation uses the store event layer
(`read_events_since` / `event_cursor` / `wait_for_events`). No Puppetmaster core
change was required.

## 3. The driver contract

The driver's entire job is to emit one `DriverIntent` per turn:

```
{ "action": "run_swarm" | "answer" | "stop",
  "goal": "<required for run_swarm>",
  "roles": ["explore", ...]?,          // optional subset
  "worker_mode": "subprocess"?,        // optional
  "rationale": "<one line>" }
```

- `run_swarm` -> the harness executes a Puppetmaster swarm and feeds the real
  artifacts back as the next turn.
- `answer` -> respond directly; no orchestration (the token-thesis decision:
  do not swarm trivia).
- `stop` -> the objective is met; terminate.

`pmharness/intent.py` is the pure contract: a strict validator plus a lenient
text->JSON parser (so "valid JSON" and "valid schema" stay separate metrics).

## 4. The product loop (`harness/session.py`)

```
prompt (+ optional images)
   │
   ├─ vision sidecar (if images): VLM transcribes image -> text, prepended
   │
   ▼
 driver.complete(context)  ──(invalid?)──> repair: re-prompt once, then fail clean
   │
   ▼  DriverIntent
   ├─ answer/stop -> emit final, terminate
   └─ run_swarm  -> Orchestrator.run() executes -> REAL artifacts fed back
                    (budget-bounded; over budget -> forced stop)
   ▼ (loop)
```

Every step is yielded as a `SessionEvent`
(`intent|executing|artifacts|final|error|vision`) so a GUI or CLI renders the
loop live. The driver is config (`HarnessConfig.driver`), swappable in one line.

### Intent repair (`harness/repair.py`)
Verbose reasoning models (e.g. Kimi) wrap JSON in prose. On an unparseable
intent the harness re-prompts ONCE with a strict correction; token accounting
accumulates so repair cost is visible. One retry is the ceiling -- a model that
still can't comply is genuinely unfit, surfaced honestly rather than looped.

## 5. Vision (sidecar, decoupled)

The research found the only vision-capable open *driver* (Kimi) is also the
weakest driver. So the harness does NOT require driver vision. A cheap VLM
sidecar (`harness/vision.py`) transcribes an attached image to TEXT once; the
text is prepended to the driver context. Any text-only driver (glm-5.2,
deepseek, qwen) then "sees" the image through the transcription. The image is
processed once, never re-sent. Vision is a harness capability, like CodeGraph
context injection -- the driver only ever reasons over text.

## 6. Durable state (`harness/state.py`)

A read-only layer over Puppetmaster's `SwarmStore`: `list_jobs`,
`job_artifacts`, and the live event stream. This is what the GUI's right pane
renders. The Session writes (by driving the Orchestrator); DurableState reads.
Because state lives in Puppetmaster's store, job history persists across harness
restarts for free.

## 7. Surfaces

- **GUI** (`harness/server.py` + `harness/web/`): a stdlib HTTP + SSE server
  serving a three-pane dark UI (Cursor 3.0 / Hermes style): left nav + driver
  card + session jobs; center driver-loop conversation; right durable-state
  artifacts. Image upload (button + drag/drop), distinct error cards, inline
  vision events, history reload.
- **CLI** (`harness/cli.py`): `harness "<task>"` with --driver/--budget/--image/
  --json and exit codes (0 clean, 1 error, 2 forced). Same Session core.

## 8. The evaluation ladder (how the driver choice was justified)

The research is a separate package (`pmharness/`) that validated the driver
layer empirically. Each stage answered one question and exposed the next:

| Stage | Question | Result |
|-------|----------|--------|
| 1 | Does a clean in-process seam exist? | Yes -- driven live, no MCP/CLI. |
| 2 | Can cheap open weights emit valid intents single-turn? | 7 open models tied the Claude control at 100%; qwen at ~1/100th cost. Battery SATURATED (does not rank). |
| 3 | Can they drive a multi-turn loop? | Discriminating, but the spread was a HARNESS confound (thin artifacts starved careful models). |
| 3.5 | (de-confound) budget + substantive substrate | Claude 55%->100%; whole open field 100%, indistinguishable from frontier. Lesson: harness design is a lever on driver economy. |
| 4 | Rank via read-decide traps (inconclusive vs conclusive) | Discriminates competent-vs-lazy (offline lazy stub fails); frontier models genuinely read findings. Splitting the top tier needs the open-weights field on Stage 4 (pending key). |

**Default driver: glm-5.2** -- MIT, efficient (932 tok/run on the discriminating
eval), 100% quality. Swappable to any catalog model via config.

Results live in `results/STAGE*_RESULTS.md`. Every score is from real execution
against real Puppetmaster; an early false "30%" run (a masker-truncated API key)
was caught by the eval's own token instrumentation and never reported.

## 9. Package map

```
pmharness/        research rig (validates the driver layer)
  intent.py         DriverIntent contract + validator + parser
  bridge.py         intent -> Orchestrator.run -> normalized result
  drivers/          Driver protocol; OpenAICompat (Kimi/GLM/...), Anthropic, stubs
  registry.py       data-driven catalog.json (license, price, vision, tier)
  battery* / scoring* / runner* / episode*   the Stage 1-4 evals
  ledger.py         append-only SQLite results
harness/          the product
  session.py        the driver loop (Session, SessionEvent)
  repair.py         intent-repair retry
  vision.py         VLM sidecar (image -> text)
  state.py          DurableState (read layer over SwarmStore)
  config.py         HarnessConfig (swappable driver, budget, reach)
  server.py + web/  three-pane GUI (HTTP + SSE)
  cli.py            headless CLI
```

## 10. Non-goals (v1, internal-first)

- Not Cursor parity. Not a model-training pipeline. Not public.
- Vision sidecar uses a frontier VLM as a stand-in; swapping an open VLM
  (GLM-OCR / Kimi-VL / Qwen-VL) is a config change, not a redesign.
- The "no black box" enterprise claim requires self-hosted open weights; the
  hosted-provider path is the cheap-not-private deployment. Stated per audience.
