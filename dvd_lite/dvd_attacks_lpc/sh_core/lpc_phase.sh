#!/usr/bin/env bash
# lpc_phase.sh (phase fallback hardened)
set -euo pipefail
PHASE_FILE="${LPC_PHASE_FILE:-}"

current_phase(){
  if [[ -n "${LPC_PHASE:-}" ]]; then echo "$LPC_PHASE"; return 0; fi
  [[ -n "$PHASE_FILE" && -s "$PHASE_FILE" ]] || { echo "cruise"; return 0; }
  local now_s=${LPC_T0_S:-0}; (( now_s==0 )) && now_s=$(( $(date +%s) % 86400 ))
  local s e p
  while IFS=, read -r s e p; do
    [[ -z "${s:-}" || -z "${e:-}" || -z "${p:-}" ]] && continue
    if (( now_s >= s && now_s < e )); then echo "$p"; return 0; fi
  done < <(tail -n +2 "$PHASE_FILE" || cat "$PHASE_FILE")
  echo "cruise"
}
