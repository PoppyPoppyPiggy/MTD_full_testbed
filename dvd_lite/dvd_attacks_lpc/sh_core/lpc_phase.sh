#!/usr/bin/env bash
# 미션 단계(Phase)별로 LPC 파라미터를 오버라이드하는 경량 레이어
# 사용: lpc_core.sh에서 source 후, 매 루프마다 apply_phase_overrides 호출

set -euo pipefail
LPC_PHASE_FILE=${LPC_PHASE_FILE:-""}

# PHASE 파일 포맷 (csv-ish):
# start_ms,end_ms,KEY=VAL KEY=VAL ...
# 예: 0,60000,LPC_DUTY=0.04 LPC_INTERVAL_MS=30000
#     60000,180000,LPC_DUTY=0.07 LPC_INTERVAL_MS=15000 LPC_STEP=0.02

apply_phase_overrides() {
  [[ -z "$LPC_PHASE_FILE" || ! -f "$LPC_PHASE_FILE" ]] && return 0
  local now_ms delta start_ms end_ms kv
  # 시작 시각(프로세스 기준) 고정
  if [[ -z "${__LPC_T0_MS__:-}" ]]; then
    __LPC_T0_MS__="$(date +%s%3N)"
  fi
  now_ms="$(date +%s%3N)"
  delta=$(( now_ms - __LPC_T0_MS__ ))

  while IFS=, read -r start_ms end_ms kv; do
    [[ -z "$start_ms" || "$start_ms" =~ ^# ]] && continue
    if (( delta >= start_ms && delta < end_ms )); then
      # kv는 공백 구분 KEY=VAL ...
      eval "$kv"
      break
    fi
  done < "$LPC_PHASE_FILE"
}
