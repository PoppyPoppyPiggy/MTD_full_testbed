#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../00_env.sh"

# LPC 옵션(프리셋/라인오버라이드로 덮어쓰기)
LPC_DUTY=${LPC_DUTY:-0.10}; LPC_INTERVAL_MS=${LPC_INTERVAL_MS:-15000}
LPC_JITTER_PCT=${LPC_JITTER_PCT:-30}; LPC_BACKOFF=${LPC_BACKOFF:-"exp"}
LPC_MAX_BUDGET=${LPC_MAX_BUDGET:-120}; LPC_STEP=${LPC_STEP:-0.02}
LPC_NOISE=${LPC_NOISE:-0.2}; LPC_ROTATE_TARGETS=${LPC_ROTATE_TARGETS:-"roundrobin"}
LPC_WINDOW=${LPC_WINDOW:-""}

LPC_BACKOFF_FACTOR=1; LPC_USED=0; LPC_STOP=0
log(){ printf "[%s] %s\n" "$(date '+%F %T')" "$*" >&2; }

in_window(){ [[ -z "$LPC_WINDOW" ]] && return 0; local n s e; n=$(date +%H:%M); IFS=- read -r s e <<<"$LPC_WINDOW"; [[ "$n" > "$s" && "$n" < "$e" ]]; }
next_interval_ms(){ local b=$((LPC_INTERVAL_MS*LPC_BACKOFF_FACTOR)) j=$((b*LPC_JITTER_PCT/100)); shuf -i "$((b-j))-$((b+j))" -n1; }
apply_backoff(){ case "$LPC_BACKOFF" in linear) ((LPC_BACKOFF_FACTOR++));; exp) ((LPC_BACKOFF_FACTOR=LPC_BACKOFF_FACTOR<2?2:LPC_BACKOFF_FACTOR*2));; esac; log "BACKOFF x$LPC_BACKOFF_FACTOR"; }

duty_on(){ python3 - "$LPC_DUTY" <<'PY';import sys,random;print("1" if random.random()<float(sys.argv[1]) else "0");PY }
rotate_target(){ local f="$1"; [[ ! -s "$f" ]] && return 1; case "$LPC_ROTATE_TARGETS" in roundrobin) head -n1 "$f"; (tail -n +2 "$f"; head -n1 "$f")> "$f.tmp"&&mv "$f.tmp" "$f";; random) shuf -n1 "$f";; *) head -n1 "$f";; esac; }

# MTD 이벤트 훅
on_ip_shuffle(){ apply_backoff; }
on_service_migration(){ apply_backoff; }
on_port_shuffle(){ apply_backoff; }

lpc_loop(){ local act="$1" targets="${2:-}"; while [[ $LPC_STOP -eq 0 && $LPC_USED -lt $LPC_MAX_BUDGET ]]; do
  in_window || { sleep 30; continue; }
  local ms; ms=$(next_interval_ms)
  if [[ "$(duty_on)" == "1" ]]; then
    local tgt=""; [[ -n "$targets" ]] && tgt=$(rotate_target "$targets" || true)
    "$act" "$tgt"; ((LPC_USED++))
  fi
  sleep "$(awk -v m="$ms" 'BEGIN{printf "%.3f\n", m/1000}')"
done; log "STOP budget=$LPC_USED/$LPC_MAX_BUDGET"; }
