#!/usr/bin/env bash
set -o pipefail
BASE="$(cd "$(dirname "$0")/../.." && pwd)"
source "$BASE/scripts/lib/log.sh"

LEVEL="${1:-low}"
KEY="mavlink_statustext_noise"

# 시작 로그
bus_attack_start "key=${KEY} level=${LEVEL}"

# 실행
if python3 "$BASE/modules/attacks/lpc_runner.py" "$KEY" "$LEVEL" 2>&1; then
  bus_attack_end "key=${KEY} level=${LEVEL}"
else
  # 실패도 남김
  bus_attack_end "key=${KEY} level=${LEVEL} status=error"
  bus_dvd_json "{\"ts\":\"$(_log_now_ts)\",\"evt\":\"attack_error\",\"key\":\"${KEY}\",\"level\":\"${LEVEL}\"}"
  exit 1
fi
