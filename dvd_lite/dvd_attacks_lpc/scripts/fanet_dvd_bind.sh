#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/attack_output"; mkdir -p "$OUT"

HOST_GW="$(ip route | awk '/default/ {print $3; exit}')"
export BUS_HOST="${BUS_HOST:-$HOST_GW}"; export BUS_PORT="${BUS_PORT:-5566}"

# Aggregator on host
python3 "$ROOT/interface/dvd_bus_aggregator.py" & BUS_PID=$!
trap 'kill $BUS_PID 2>/dev/null || true' EXIT

# Launch agent inside candidate containers
TARGETS=(${DVD_TARGETS:-"flight-controller simulator ground-control-station"})
for C in "${TARGETS[@]}"; do
  docker exec -d "$C" bash -lc \
    "export BUS_HOST=$BUS_HOST BUS_PORT=$BUS_PORT MAVLINK_ENDPOINT=\${MAVLINK_ENDPOINT:-udp:0.0.0.0:14550}; \
     python3 /workspace/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/interface/dvd_telemetry_agent.py" || echo "[skip] $C"
done

# Run attack scenario + evaluate
bash "$ROOT/scripts/scenario_lpc_multi.sh"
