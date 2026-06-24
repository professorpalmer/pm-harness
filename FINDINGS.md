# FINDINGS

## Stage 1 -- The PM-native driver seam (proven live)

**Result: no programmatic API needs building. It already exists and was driven
end-to-end in-process with zero MCP and zero CLI subprocess.**

### Layering
Puppetmaster's MCP tools and CLI are both thin transports over one engine:

- MCP `start_swarm` (`puppetmaster/mcp_server.py:2244`) builds `["run", goal,
  ...]` and shells out to the CLI via `start_cli(...)`.
- CLI `run` (`puppetmaster/cli.py:1894`) builds a store and calls
  `Orchestrator(store).run(...)`.
- `Orchestrator` (`puppetmaster/orchestrator.py:149`) is the real engine.

A native harness deletes both transports and calls the engine.

### The seam
```python
from puppetmaster.store_factory import create_store   # (backend, state_dir) -> SwarmStore
from puppetmaster.orchestrator import Orchestrator, RunResult

store  = create_store("sqlite", state_dir)
result = Orchestrator(store).run(
    goal, roles=None, specs=None,
    lease_seconds=5, worker_mode="subprocess",   # subprocess|inline|daemon
    on_job_created=callback,                      # fires when the job row exists
)
# RunResult(frozen): job, artifacts, summary, summary_path,
#                    recovered_tasks, rerouted_tasks, mode ("edit"|"analysis")
```

### Live proof
In-process temp SQLite store, local demo adapter: job ran to COMPLETE, the
`on_job_created` callback fired, 8 structured artifacts came back
(finding/decision/patch/risk/verification), stitched summary 1631 chars,
`store.list_artifacts()` re-read the same 8. The full driver loop --
start, follow, read structured state back -- works with no keys.

### Async question (resolved)
`Orchestrator.run()` is synchronous and blocks under every worker_mode
(`daemon` waits until settled). The live-observation seam is the store's event
layer: `read_events_since`, `event_cursor`, `wait_for_events` (push-style
long-poll), plus `list_jobs` / `list_artifacts` / `status_snapshot`. Harness
pattern: drive `run()` on a worker thread, observe via store events. No
architecture gap; no core change required.

### Implications for the MVP
1. The GUI is a thin read view over `SwarmStore` + the event stream.
2. The driver loop's contract is exact: emit a structured intent that maps to
   `Orchestrator.run` args; fold `RunResult.artifacts` back. That is the entire
   token-thesis mechanism, and it is concrete.
3. PM version in the dev checkout is 0.9.83 (confirmed via editable install),
   resolving the wiki's stale-0.9.19 note.

## Stage 2 -- The driver eval rig (built, green offline)

10-task labeled battery (swarm/answer/stop). Deterministic scoring, SQLite
ledger. `stub-oracle` control scores 100% driving real Puppetmaster. Open-
weights (Kimi, GLM) and frontier (OpenAI) rows are wired and pending keys.

Next data point: run the real drivers and record valid-call rate, decision
accuracy, tokens, and latency per model -- the first rows of the "ideal harness
model" research and the cost-thesis receipt.
