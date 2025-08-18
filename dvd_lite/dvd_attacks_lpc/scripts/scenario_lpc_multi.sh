#!/usr/bin/env bash
set -Eeuo pipefail
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"
: "${MTD_DEV_MODE:=1}"; export MTD_DEV_MODE
[[ -f 00_env.sh ]] && source 00_env.sh || true

OUT_DIR="$BASE_DIR/attack_output"; mkdir -p "$OUT_DIR"
ATTACK_DURATION="${ATTACK_DURATION:-60}"
OVERLAP_DELAY="${OVERLAP_DELAY:-15}"

ts(){ date -u +"%Y-%m-%dT%H:%M:%SZ"; }
bus(){ echo "[$(ts)] [$1] $2" >> "$OUT_DIR/bus.log"; }

run_mod(){
  local mod="$1" inten="$2" dur="$3"
  if [[ ! -x "$BASE_DIR/modules/$mod" ]]; then echo "[WARN] missing modules/$mod"; return 1; fi
  bus "scenario" "start module=$mod intensity=$inten dur=${dur}s"
  DUR="$dur" INTENSITY="$inten" "$BASE_DIR/modules/$mod" >> "$OUT_DIR/bus.log" 2>>"$OUT_DIR/bus.log" & echo $!
}

PIDS=(); trap 'for p in "${PIDS[@]:-}"; do kill $p 2>/dev/null || true; done' EXIT INT TERM

echo "=== LPC multi-attack start ==="; bus "scenario" "begin"
PID1=$(run_mod "wifi_slow_scan.sh" "low" "$ATTACK_DURATION") || true; [[ $PID1 ]] && PIDS+=("$PID1")
sleep "$OVERLAP_DELAY"
PID2=$(run_mod "telemetry_trickle_jam.sh" "low" "$ATTACK_DURATION") || true; [[ $PID2 ]] && PIDS+=("$PID2")
sleep "$OVERLAP_DELAY"
PID3=$(run_mod "mavlink_param_drift.sh" "medium" "$ATTACK_DURATION") || true; [[ $PID3 ]] && PIDS+=("$PID3")
sleep "$OVERLAP_DELAY"
PID4=$(run_mod "gps_slow_spoof.sh" "medium" "$ATTACK_DURATION") || true; [[ $PID4 ]] && PIDS+=("$PID4")
for p in "${PIDS[@]:-}"; do wait "$p" || true; done
bus "scenario" "end"; echo "=== LPC multi-attack end ==="

bash "$BASE_DIR/tools/auto_eval.sh"
