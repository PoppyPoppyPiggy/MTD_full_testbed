#!/usr/bin/env bash
# template_primitive.sh (safe stub; simulation-only)
set -euo pipefail

# 올바른 변수명과 경로 설정
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
. "$SCRIPT_DIR/../00_env.sh"
. "$SCRIPT_DIR/../sh_core/lpc_core.sh"

ACT_NAME="${ACT_NAME:-template_primitive}"
TARGETS_FILE="${TARGETS_FILE:-"$SCRIPT_DIR/../scenarios/targets.txt"}"

# ---- one-shot action (must be idempotent & quick) ----
do_act(){
  local target="${1:-}"
  local phase; phase="$(current_phase 2>/dev/null || echo 'cruise')"
  
  # 여기에 실제 상호작용 대신 안전한 스텁 로깅만 수행 (연구/시뮬 목적)
  local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$timestamp] [$ACT_NAME] phase=$phase target=${target:-none} status=executed" >> "$LPC_LOG_DIR/bus.log"
  
  # (예) MTD 이벤트 감지 시 훅 호출 (실제 환경에서는 syslog/파일/소켓 등으로 트리거)
  # on_ip_shuffle 2>/dev/null || true
  
  return 0
}

main(){
  lpc_loop do_act "$TARGETS_FILE" 2>/dev/null || {
    # lpc_loop가 없으면 fallback
    echo "[WARN] lpc_loop not found, using simple execution"
    do_act
  }
}

main "$@"