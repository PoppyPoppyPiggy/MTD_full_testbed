#!/usr/bin/env bash
set -euo pipefail

# 프로젝트 루트의 공통 env 로드
BASE="$(cd "$(dirname "$0")/../.." && pwd)"
source "$BASE/00_env_ext.sh"

ROLE="${1:-gcs}"
SERVICE="${2:-mavlink}"
# 옵션 파싱
COUNT=40
INTV=0.03
for a in "${@:3}"; do
  [[ "$a" == --count=* ]] && COUNT="${a#--count=}"
  [[ "$a" == --interval=* ]] && INTV="${a#--interval=}"
done

# 타깃 해석
TJSON="$(python3 "$BASE/modules/attacks/resolve_target.py" \
  "$BASE/modules/attacks/targets/targets.yml" "$ROLE" "$SERVICE")"

HOST="$(echo "$TJSON" | jq -r .ip)"
PORT="$(echo "$TJSON" | jq -r .port)"

# UDP 패킷 발사
python3 "$BASE/tools/send_udp.py" --host "$HOST" --port "$PORT" \
  --count "$COUNT" --interval "$INTV" --payload "lpctest"
