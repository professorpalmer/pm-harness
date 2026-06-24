# pm-harness

Research rig for the question: **which LLMs can drive Puppetmaster as a native
harness layer?**

This is Stage 2 of the PM-native harness investigation. Stage 1 proved that a
native driver can call Puppetmaster's orchestration engine in-process (no MCP,
no CLI subprocess). Stage 2 measures **which models can actually do the
driving** -- emit valid structured orchestration intents and make the right
call about when to orchestrate vs. answer vs. stop.

Internal-first. stdlib-only rig (urllib + sqlite); Puppetmaster is the one real
dependency, installed editable from the local checkout.

## The thesis it tests

A PM-native harness deletes the frontier-model-as-narrator layer. Instead of a
model narrating "I'll now call puppetmaster_start_swarm" in prose (paying tokens
to talk), the driver model emits one compact JSON **DriverIntent** and the
harness executes it in code. The open question is empirical: can cheap
open-weights models (Kimi, GLM) hit that structured target reliably enough to
run the loop, and how close do they get to a frontier control?

## The seam (Stage 1, proven)

```
MCP tools   ─┐
             ├─→  CLI `run`  ─→  Orchestrator(store).run(...)   ← the real engine
CLI commands ┘                        ↑
                       pm-harness calls THIS directly
```

`Orchestrator(store).run(goal, roles=, specs=, worker_mode=, on_job_created=)
-> RunResult(job, artifacts, summary, summary_path, rerouted_tasks, mode)`.
`run()` blocks; live observation uses the store's event layer
(`read_events_since` / `event_cursor` / `wait_for_events`).

## Architecture

| Module | Role |
|--------|------|
| `pmharness/intent.py` | `DriverIntent` contract + strict validator + lenient text->JSON parser. The pure layer; no PM dependency. |
| `pmharness/bridge.py` | Executes a validated `run_swarm` intent against Puppetmaster's in-process Orchestrator (local adapter; deterministic, free). |
| `pmharness/drivers/` | `Driver` protocol. `StubDriver` (offline oracle / ceiling). `OpenAICompatDriver` (Kimi, GLM, OpenAI -- one driver, every OpenAI-compatible endpoint). |
| `pmharness/battery.py` | 10 labeled tasks across three buckets: swarm / answer / stop. |
| `pmharness/scoring.py` | Deterministic, no LLM-as-judge: json_valid, schema_valid, action_correct, executed_ok, composite score. |
| `pmharness/ledger.py` | Append-only SQLite record of every attempt. |
| `pmharness/runner.py` + `scripts/run_eval.py` | Run the battery per model, persist, print the table. |

## Design decision: driver eval vs. worker eval

The eval grades **driving**, not **working**. Swarm intents execute on
Puppetmaster's free **local adapter** so ground truth is deterministic and
key-free. "Is Kimi a good *worker*?" is a separate study (it would route Kimi
into the swarm itself). Conflating the two would poison the cost thesis, so the
rig keeps them apart by construction.

## Metrics

- **json_valid** -- driver output parsed to a JSON object at all
- **schema_valid** -- parsed object is a real `DriverIntent`
- **action_correct** -- decision matched the task's ground-truth label
- **executed_ok** -- for swarm cases, Puppetmaster returned >= 1 artifact
- **score** -- composite 0..1 (schema floor 0.40, decision 0.40, execution 0.20)
- plus tokens_out and latency per model (the cost-thesis columns)

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -e /path/to/Puppetmaster pytest
.venv/bin/python -m pytest -q                       # 20 tests, fully offline
.venv/bin/python scripts/run_eval.py --drivers stub-oracle      # offline, no keys

# Real drivers (keys from env):
export MOONSHOT_API_KEY=...   # Kimi
export ZAI_API_KEY=...        # GLM
export OPENAI_API_KEY=...     # frontier control
.venv/bin/python scripts/run_eval.py --drivers stub-oracle kimi-k2 glm-4.6 gpt-frontier
```

## Status

- Stage 1 (seam) proven; Stage 2 rig built and green end-to-end offline.
- `stub-oracle` scores 100% (the control ceiling) driving real Puppetmaster.
- Open-weights + frontier rows pending API keys.
