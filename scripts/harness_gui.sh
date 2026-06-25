#!/usr/bin/env bash
# Launch the PM-Native Harness GUI. Default driver glm-5.2 needs OPENROUTER_API_KEY.
# For a no-key demo: HARNESS_DRIVER=stub-oracle-v2 ./scripts/harness_gui.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${1:-8799}"
exec .venv/bin/python -m harness.server "$PORT"
