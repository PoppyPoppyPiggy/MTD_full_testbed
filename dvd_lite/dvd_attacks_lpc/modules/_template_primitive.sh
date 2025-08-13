#!/usr/bin/env bash
# _template_primitive.sh  (safe stub; simulation-only)
set -euo pipefail
__DIR__="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
. "$__DIR__/../00_env.sh"
. "$__DIR__/../sh_core/lpc_core.sh"

ACT_NAME="${ACT_NAME:-template_primitive}"
TARGETS_FILE="${TARGETS_FILE:-"$__DIR__/../scenarios/targets.txt"}"

# ---- one-shot action (must be idempotent & quick) ----
_do_act(){
  local target="${1:-}"
  local phase; phase="$(current_phase)"
  # 여기에 실제 상호작용 대신 안전한 스텁 로깅만 수행 (연구/시뮬 목적)
  echo "$(date +%s),act=$ACT_NAME,phase=$phase,target=${target:-none}" >> "$LPC_LOG_DIR/bus.log"
  # (예) MTD 이벤트 감지 시 훅 호출 (실제 환경에서는 syslog/파일/소켓 등으로 트리거)
  # on_ip_shuffle
  return 0
}

main(){
  lpc_loop _do_act "$TARGETS_FILE"
}
main "$@"
