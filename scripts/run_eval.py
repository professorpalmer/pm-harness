#!/usr/bin/env python3
"""pm-harness eval CLI.

Usage:
  python scripts/run_eval.py --drivers stub-oracle
  python scripts/run_eval.py --drivers stub-oracle kimi-k2 glm-4.6 gpt-frontier
  python scripts/run_eval.py --drivers all --no-execute

Offline default (stub-oracle) needs no keys. Real drivers read keys from env:
  MOONSHOT_API_KEY, ZAI_API_KEY, OPENAI_API_KEY.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pmharness.registry import REGISTRY, build
from pmharness.ledger import Ledger
from pmharness.runner import run_driver, new_run_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drivers", nargs="+", default=["stub-oracle"],
                    help="driver names or 'all'")
    ap.add_argument("--ledger", default=str(Path(__file__).resolve().parents[1] / "results" / "ledger.sqlite"))
    ap.add_argument("--no-execute", action="store_true",
                    help="skip executing swarm intents against Puppetmaster")
    ap.add_argument("--json", action="store_true", help="emit summary as JSON")
    args = ap.parse_args()

    names = list(REGISTRY) if args.drivers == ["all"] else args.drivers
    ledger = Ledger(args.ledger)
    run_id = new_run_id()

    for name in names:
        try:
            driver = build(name)
        except KeyError as e:
            print(f"skip {name}: {e}", file=sys.stderr)
            continue
        try:
            scores = run_driver(driver, ledger, run_id=run_id, execute=not args.no_execute)
        except Exception as e:
            print(f"driver {name} FAILED: {e!r}", file=sys.stderr)
            continue
        avg = round(sum(s.score for s in scores) / len(scores) * 100, 1) if scores else 0.0
        print(f"  {name:16s} mean_score={avg:5.1f}%  ({len(scores)} tasks)", file=sys.stderr)

    summary = ledger.summary(run_id)
    if args.json:
        print(json.dumps({"run_id": run_id, "summary": summary}, indent=2))
    else:
        print(f"\nRun {run_id}")
        hdr = f"{'model':16s} {'score':>7s} {'json':>6s} {'schema':>7s} {'action':>7s} {'tok_out':>8s} {'lat_ms':>7s}"
        print(hdr); print("-" * len(hdr))
        for r in summary:
            print(f"{r['model']:16s} {r['avg_score']:>6.1f}% {r['json_pct']:>5.0f}% "
                  f"{r['schema_pct']:>6.0f}% {r['action_pct']:>6.0f}% "
                  f"{r['tout'] or 0:>8d} {r['avg_latency'] or 0:>7.0f}")
    ledger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
