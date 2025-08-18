#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/attack_output"
mkdir -p "$OUT"

# 1) 호스트 게이트웨이 IP (Docker bridge)
HOST_GW="$(ip route | awk '/default/ {print $3; exit}')"
export BUS_HOST="${BUS_HOST:-$HOST_GW}"
export BUS_PORT="${BUS_PORT:-5566}"

# 2) Aggregator (백그라운드)
echo "[*] starting bus aggregator on $BUS_HOST:$BUS_PORT"
python3 "$ROOT/interface/dvd_bus_aggregator.py" & 
BUS_PID=$!

cleanup(){ kill $BUS_PID 2>/dev/null || true; }
trap cleanup EXIT

# 3) DVD 컨테이너 목록(필요한 것만 골라서)
TARGETS=(${DVD_TARGETS:-"flight-controller simulator ground-control-station"})
for C in "${TARGETS[@]}"; do
  echo "[*] launching agent in container: $C"
  docker exec -d "$C" bash -lc \
    "export BUS_HOST=$BUS_HOST BUS_PORT=$BUS_PORT MAVLINK_ENDPOINT=\${MAVLINK_ENDPOINT:-udp:0.0.0.0:14550}; \
     python3 /workspace/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/interface/dvd_telemetry_agent.py" \
    || echo "[!] skip $C (not running?)"
done

# 4) 공격 실행(네가 쓰는 기존 실행 로직/시나리오 유지)
SCENARIO="${SCENARIO:-scenarios/S_lpc_multi.pipeline}"
WIN="${WIN:-3}" STRIDE="${STRIDE:-1}" SIM_TIME="${SIM_TIME:-60}" PKT_SIZE="${PKT_SIZE:-512}"
NS3_BUILD_MODE="${NS3_BUILD_MODE:-once}"

echo "[*] running LPC pipeline (scenario=$SCENARIO)"
bash "$ROOT/scripts/lpc_run.sh"

# 5) NetAnim
echo "[*] ns-3 + NetAnim export"
ANIM_OUT="$OUT/netanim.xml" NS3_BUILD_MODE=skip bash "$ROOT/scripts/run_ns3_eval.sh"
echo "[OK] open NetAnim and load: $ANIM_OUT"
