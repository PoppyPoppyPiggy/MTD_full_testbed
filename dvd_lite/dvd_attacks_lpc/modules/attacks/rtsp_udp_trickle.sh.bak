#!/usr/bin/env bash
set -o pipefail
BASE="$(cd "$(dirname "$0")/../.." && pwd)"
source "$BASE/scripts/lib/log.sh"

LEVEL="${1:-low}"
KEY="rtsp_udp_trickle"
ROLE="companion"; SERVICE="rtsp"

# 타깃 해석
TJSON="$(python3 "$BASE/modules/attacks/resolve_target.py" "$BASE/modules/attacks/targets/targets.yml" "$ROLE" "$SERVICE")"
HOST="$(echo "$TJSON" | jq -r .ip)"
PORT="$(echo "$TJSON" | jq -r .port)"

# 프로파일에서 레벨별 파라미터(pps,duration,payload)
PROFILE="$BASE/modules/attacks/lpc_profiles/attacks_lpc.json"
PPS=$(jq -r ".attacks[\"${KEY}\"].levels[\"${LEVEL}\"].pps" "$PROFILE")
DUR=$(jq -r ".attacks[\"${KEY}\"].levels[\"${LEVEL}\"].duration_s" "$PROFILE")
PAY=$(jq -r ".attacks[\"${KEY}\"].levels[\"${LEVEL}\"].payload" "$PROFILE")

bus_attack_start "key=${KEY} level=${LEVEL} role=${ROLE} host=${HOST} port=${PORT}"

# flow_hint는 helpers가 BUS_DVD_LOG로 기록
python3 "$BASE/modules/attacks/helpers/udp_trickle.py" \
  --host "$HOST" --port "$PORT" --pps "$PPS" --duration "$DUR" --payload "$PAY" \
  --flowlog "$BUS_DVD_LOG" \
  | jq -c --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" --arg key "$KEY" --arg lvl "$LEVEL" \
       '{ts:$ts,evt:"attack_stat",key:$key,level:$lvl,detail:.}' >> "$BUS_DVD_LOG"

bus_attack_end "key=${KEY} level=${LEVEL} role=${ROLE}"
