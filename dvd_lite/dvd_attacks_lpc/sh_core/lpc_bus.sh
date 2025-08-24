#!/usr/bin/env bash
# LPC bus helper (epoch-ms timestamps + safe date formatting)
set -euo pipefail

# 스크립트 기준 루트(셸 중립)
BASE="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]-$0}")/.." && pwd)"
. "$BASE/00_env.sh"

# epoch milliseconds (GNU date 없을 때 python 폴백)
_ts() {
  if ts=$(date +%s%3N 2>/dev/null) && [[ "$ts" =~ ^[0-9]+$ ]]; then
    echo "$ts"
  else
    python3 - <<'PY'
import time
print(int(time.time()*1000))
PY
  fi
}

# 한 줄 포맷: <epoch_ms>\t<tag>\tmode=.. actor=.. k=v ...
_bus_line() {
  printf "%s\t%s\tmode=%s actor=%s %s\n" \
    "$(_ts)" "$1" "${LPC_MODE:-SIM}" "${LPC_ACTOR:-attacker}" "$2"
}

bus_emit()   { _bus_line "$1" "$2" >> "$LPC_LOG_DIR/bus.log"; }
# ns-3 변환용: loss_pct=.. delay_ms=.. jitter_ms=.. dup_pct=.. rate_limit_mbps=..
effect_emit(){ bus_emit "effect" "$*"; }

# 사람이 보는 실행 로그(날짜 포맷은 반드시 인용)
log(){ echo "[$(date "+%F %T")] $*" | tee -a "$LPC_LOG_DIR/run.log"; }
