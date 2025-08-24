#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"

SCN_FILE="${1:-scripts/scenario.pipeline.yaml}"
NS3ROOT="${NS3ROOT:-$HOME/MTD/MTD_full_testbed/ns-3.45/ns-3-dev}"
RUN_NS3="${RUN_NS3:-1}"
RUNS="${RUNS:-}"

mkdir -p attack_output
touch attack_output/bus.log attack_output/run.log
sudo -v || true

if [[ -n "${RUNS}" ]]; then
  python3 tools/scenario_runner.py --file "$SCN_FILE" --ns3root "$NS3ROOT" --run-ns3 "$RUN_NS3" --runs "$RUNS"
else
  python3 tools/scenario_runner.py --file "$SCN_FILE" --ns3root "$NS3ROOT" --run-ns3 "$RUN_NS3"
fi
