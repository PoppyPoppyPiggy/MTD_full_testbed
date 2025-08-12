#!/usr/bin/env bash
# lpc_phase.sh (robust)
# - CSV: phase,start_ms,end_ms,KEY=VAL,KEY=VAL,...
# - 이 파일은 함수만 제공한다. 소스 시 즉시 실행/파싱 금지(set -u 안전).
set -euo pipefail

# 기준 시각(T0) 고정
if [[ -z "${LPC_T0_MS:-}" ]]; then
  export LPC_T0_MS="$(date +%s%3N)"
fi

_now_ms(){ date +%s%3N; }
_since_ms(){ echo $(( $(_now_ms) - LPC_T0_MS )); }

# CSV 1행 건너뛰고(#,빈줄 무시) 현재 ms에 해당하는 라인의 KEY=VAL 들을 export
lpc_phase_apply() {
  local csv="${LPC_PHASE_FILE:-}"
  [[ -z "$csv" || ! -s "$csv" ]] && return 0

  local now_ms="${1:-$(_since_ms)}"
  local IFS=,
  # read 최대 16열까지 파싱(필요 시 늘리면 됨)
  while read -r c_phase c_s c_e c4 c5 c6 c7 c8 c9 c10 c11 c12 c13 c14 c15 c16 || true; do
    # 헤더/주석/빈줄 스킵
    [[ -z "${c_phase:-}" ]] && continue
    [[ "${c_phase,,}" == "phase" ]] && continue
    [[ "${c_phase:0:1}" == "#" ]] && continue

    local s="${c_s:-0}" e="${c_e:-0}"
    # 숫자 가드
    [[ "$now_ms" -ge "$s" && "$now_ms" -lt "$e" ]] || continue

    # 4열 이후 KEY=VAL 토큰들 export
    for tok in "${c4:-}" "${c5:-}" "${c6:-}" "${c7:-}" "${c8:-}" "${c9:-}" "${c10:-}" "${c11:-}" "${c12:-}" "${c13:-}" "${c14:-}" "${c15:-}" "${c16:-}"; do
      [[ -z "$tok" ]] && continue
      # KEY=VAL 형태만 허용
      if [[ "$tok" =~ ^[A-Za-z_][A-Za-z0-9_]*=.+$ ]]; then
        # shellcheck disable=SC2163
        export "$tok"
      fi
    done
    return 0  # 매칭 1건만 적용
  done < <(grep -vE '^\s*#' "$csv" | sed '/^\s*$/d')
}

export -f lpc_phase_apply
