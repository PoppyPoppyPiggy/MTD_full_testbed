#!/usr/bin/env bash
# lpc_core.sh (stable+phase-apply)
set -euo pipefail

__LPC_DIR__="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
. "$__LPC_DIR__/../00_env.sh"

. "$__LPC_DIR__/lpc_phase.sh"   # lpc_phase_apply() 제공
[[ -n "${LPC_PROFILE:-}" && -f "$LPC_PROFILE" ]] && source "$LPC_PROFILE"

# ---- 기본 옵션 ----
LPC_DUTY=${LPC_DUTY:-0.10}
LPC_INTERVAL_MS=${LPC_INTERVAL_MS:-15000}
LPC_JITTER_PCT=${LPC_JITTER_PCT:-30}
LPC_BACKOFF=${LPC_BACKOFF:-"exp"}
LPC_MAX_BUDGET=${LPC_MAX_BUDGET:-120}
LPC_STEP=${LPC_STEP:-0.02}
LPC_NOISE=${LPC_NOISE:-0.20}
LPC_ROTATE_TARGETS=${LPC_ROTATE_TARGETS:-"roundrobin"}
LPC_WINDOW=${LPC_WINDOW:-""}

LPC_BACKOFF_FACTOR=1
LPC_USED=0
LPC_STOP=0

log(){ printf "[%s] %s\n" "$(date '+%F %T')" "$*" >&2; }

in_window(){
  [[ -z "$LPC_WINDOW" ]] && return 0
  local now start end
  now="$(date +%H:%M)"
  IFS='-' read -r start end <<<"$LPC_WINDOW"
  [[ "$now" > "$start" && "$now" < "$end" ]]
}

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

apply_backoff(){
  case "$LPC_BACKOFF" in
    linear) LPC_BACKOFF_FACTOR=$(( LPC_BACKOFF_FACTOR + 1 )) ;;
    exp)    LPC_BACKOFF_FACTOR=$(( LPC_BACKOFF_FACTOR < 2 ? 2 : LPC_BACKOFF_FACTOR*2 )) ;;
    *)      ;;
  esac
  log "BACKOFF x${LPC_BACKOFF_FACTOR}"
}

duty_on(){ awk -v p="$LPC_DUTY" 'BEGIN{srand(); print (rand()<p)?1:0}'; }

rotate_target(){
  local f="$1"
  [[ ! -s "$f" ]] && return 1
  case "$LPC_ROTATE_TARGETS" in
    roundrobin) head -n1 "$f"; (tail -n +2 "$f"; head -n1 "$f") > "$f.tmp" && mv "$f.tmp" "$f" ;;
    random)     shuf -n1 "$f" ;;
    *)          head -n1 "$f" ;;
  esac
}

on_ip_shuffle(){ apply_backoff; }
on_service_migration(){ apply_backoff; }
on_port_shuffle(){ apply_backoff; }

lpc_loop(){
  local act="$1" targets_file="${2:-}"
  while [[ $LPC_STOP -eq 0 && $LPC_USED -lt $LPC_MAX_BUDGET ]]; do
    # ★ 페이즈 적용(있을 때만)
    lpc_phase_apply || true

    if ! in_window; then
      log "[LPC] waiting window=${LPC_WINDOW:-<none>} (sleep 30s)"
      sleep 30
      continue
    fi

    local ms; ms="$(next_interval_ms)"
    if [[ "$(duty_on)" == "1" ]]; then
      local tgt=""
      [[ -n "$targets_file" ]] && tgt="$(rotate_target "$targets_file" || true)"
      "$act" "$tgt"
      LPC_USED=$(( LPC_USED + 1 ))
    fi

    awk -v m="$ms" 'BEGIN{printf "%.3f\n", m/1000}' | { read -r sec; sleep "$sec"; }
  done
  log "STOP budget=${LPC_USED}/${LPC_MAX_BUDGET}"
}
