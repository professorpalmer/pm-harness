# AGENTS.md -- pm-harness

Internal-first research rig. Conventions:

- No emojis or decorative pictographs anywhere (code, docs, commits, output).
  Plain words only.
- stdlib-only for the rig itself (urllib, sqlite, dataclasses). Puppetmaster is
  the single real dependency, installed editable from the local checkout.
- The `pmharness/intent.py` layer must stay PM-free and pure so it unit-tests
  fast and hermetically. Execution coupling lives only in `bridge.py`.
- Scoring is deterministic -- no LLM-as-judge. Every metric must be a function
  of (labeled task, raw driver text, execution result).
- Driver eval measures driving, not working: swarm intents execute on
  Puppetmaster's free local adapter for deterministic ground truth.
- Tests before claiming done: `.venv/bin/python -m pytest -q`. The offline E2E
  test drives real Puppetmaster and must stay green with zero API keys.
- Never commit keys or `results/*.sqlite`.
