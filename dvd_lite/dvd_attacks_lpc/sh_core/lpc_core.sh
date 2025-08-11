#!/usr/bin/env bash
# lpc_core.sh (stable v1.2)
# 공통 LPC 코어: 타이밍/지터/백오프/윈도우/타깃회전 + MTD 훅 + 공용 루프
# 각 모듈에서:  . "$BASE/sh_core/lpc_core.sh"  후  lpc_loop <함수명> [targets_file]

set -euo pipefail

# ---- 환경 로드 (이 파일 기준 상대경로) ----
__LPC_DIR__="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
. "$__LPC_DIR__/../00_env.sh"      # LPC_LOG_DIR 등 환경

# ---- 프로필/페이즈 레이어 ----
. "$__LPC_DIR__/lpc_phase.sh"      # 미션 단계별 오버라이드 지원
[[ -n "${LPC_PROFILE:-}" && -f "$LPC_PROFILE" ]] && source "$LPC_PROFILE"   # 선택: 프로필 env 자동 로드

# ---- 기본 옵션 (환경변수로 오버라이드 가능) ----
LPC_DUTY=${LPC_DUTY:-0.10}                 # on 확률(0.0~1.0)
LPC_INTERVAL_MS=${LPC_INTERVAL_MS:-15000}  # 기본 주기(ms)
LPC_JITTER_PCT=${LPC_JITTER_PCT:-30}       # 주기 지터(%)
LPC_BACKOFF=${LPC_BACKOFF:-"exp"}          # none|linear|exp
LPC_MAX_BUDGET=${LPC_MAX_BUDGET:-120}      # 총 실행 횟수
LPC_STEP=${LPC_STEP:-0.02}                 # 모듈별 의미 상이
LPC_NOISE=${LPC_NOISE:-0.20}               # 라벨링/모의용
LPC_ROTATE_TARGETS=${LPC_ROTATE_TARGETS:-"roundrobin"}
LPC_WINDOW=${LPC_WINDOW:-""}               # "HH:MM-HH:MM" (비우면 항상 on)

# ---- 내부 상태 ----
LPC_BACKOFF_FACTOR=1
LPC_USED=0
LPC_STOP=0

log(){ printf "[%s] %s\n" "$(date '+%F %T')" "$*" >&2; }

# ---- 시간창 체크 ----
in_window(){
  [[ -z "$LPC_WINDOW" ]] && return 0
  local now start end
  now="$(date +%H:%M)"
  IFS='-' read -r start end <<<"$LPC_WINDOW"
  [[ "$now" > "$start" && "$now" < "$end" ]]
}

# ---- 다음 인터벌(ms): interval ± jitter, backoff 반영 ----
next_interval_ms(){
  local b j low high
  b=$(( LPC_INTERVAL_MS * LPC_BACKOFF_FACTOR ))
  j=$(( b * LPC_JITTER_PCT / 100 ))
  low=$(( b - j ))
  high=$(( b + j ))
  (( low < 200 )) && low=200
  (( high < low )) && high=$((low+1))
  if command -v shuf >/dev/null 2>&1; then
    shuf -i "${low}-${high}" -n1
  else
    awk -v lo="$low" -v hi="$high" 'BEGIN{srand(); print int(lo + rand()*(hi-lo+1))}'
  fi
}

# ---- 백오프 ----
apply_backoff(){
  case "$LPC_BACKOFF" in
    linear) LPC_BACKOFF_FACTOR=$(( LPC_BACKOFF_FACTOR + 1 )) ;;
    exp)    LPC_BACKOFF_FACTOR=$(( LPC_BACKOFF_FACTOR < 2 ? 2 : LPC_BACKOFF_FACTOR*2 )) ;;
    *)      ;;  # none
  esac
  log "BACKOFF x${LPC_BACKOFF_FACTOR}"
}

# ---- 듀티사이클(on/off) ----
duty_on(){
  # 선택: 고정 시드가 필요하면 LPC_SEED 사용
  if [[ -n "${LPC_SEED:-}" ]]; then
    awk -v p="$LPC_DUTY" -v s="$LPC_SEED" 'BEGIN{srand(s); print (rand()<p)?1:0}'
  else
    awk -v p="$LPC_DUTY" 'BEGIN{srand(); print (rand()<p)?1:0}'
  fi
}

# ---- 타깃 로테이션 ----
rotate_target(){
  local f="$1"
  [[ ! -s "$f" ]] && return 1
  case "$LPC_ROTATE_TARGETS" in
    roundrobin)
      head -n1 "$f"
      (tail -n +2 "$f"; head -n1 "$f") > "$f.tmp" && mv "$f.tmp" "$f"
      ;;
    random) shuf -n1 "$f" ;;
    *)      head -n1 "$f" ;;
  esac
}

# ---- MTD 이벤트 훅 (모듈에서 필요 시 오버라이드) ----
on_ip_shuffle(){ apply_backoff; }
on_service_migration(){ apply_backoff; }
on_port_shuffle(){ apply_backoff; }

# ---- 공용 루프 ----
lpc_loop(){
  local act="$1" targets_file="${2:-}"
  while [[ $LPC_STOP -eq 0 && $LPC_USED -lt $LPC_MAX_BUDGET ]]; do
    if ! in_window; then
      log "[LPC] waiting window=${LPC_WINDOW:-<none>} (sleep 30s)"
      sleep 30
      continue
    fi

    # 페이즈 파일에 따른 동적 오버라이드 적용
    apply_phase_overrides

    local ms; ms="$(next_interval_ms)"
    if [[ "$(duty_on)" == "1" ]]; then
      local tgt=""
      [[ -n "$targets_file" ]] && tgt="$(rotate_target "$targets_file" || true)"
      "$act" "$tgt"
      LPC_USED=$(( LPC_USED + 1 ))
    fi

    # ms -> 초(float)로 변환 후 sleep
    awk -v m="$ms" 'BEGIN{printf "%.3f\n", m/1000}' | { read -r sec; sleep "$sec"; }
  done
  log "STOP budget=${LPC_USED}/${LPC_MAX_BUDGET}"
}
