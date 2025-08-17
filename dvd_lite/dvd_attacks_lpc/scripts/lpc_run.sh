#!/usr/bin/env bash
# lpc_run.sh — 베이스 실행기: 공격 n초 수행 → 타임라인/피처/ns-3/요약
set -euo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
ATT_OUT="$BASE/attack_output"
BUS="$ATT_OUT/bus.log"
TL="$ATT_OUT/effect_timeline.csv"
FEATS="$ATT_OUT/window_features.csv"
NS3="${NS3_ROOT:-$HOME/MTD/MTD_full_testbed/ns-3.45/ns-3-dev}"
NS3_MET="$ATT_OUT/ns3_metrics.csv"

DUR="${DUR:-20}"             # 전체 수행 시간(초)
WIN="${WIN:-6}"              # 피처 윈도우 단위(행 수)
INTERVAL_A="${INTERVAL_A:-200}"
INTERVAL_B="${INTERVAL_B:-250}"
BUDGET="${BUDGET:-30}"

MOD_A="${MOD_A:-modules/mavlink_param_drift.sh}"
MOD_B="${MOD_B:-modules/telemetry_trickle_jam.sh}"
INTENSITY="${INTENSITY:-mid}"  # trickle_jam intensity

mkdir -p "$ATT_OUT"
: > "$BUS"

echo "[run] duration=${DUR}s, budgets=${BUDGET}+${BUDGET}, intervals=${INTERVAL_A}/${INTERVAL_B}ms"
echo "[run] modules: A=$MOD_A, B=$MOD_B"

# --- launch modules (background, with clean window) ---
( cd "$BASE" && \
  LPC_WINDOW="" LPC_MAX_BUDGET="$BUDGET" LPC_INTERVAL_MS="$INTERVAL_A" "$MOD_A" ) & p1=$!
( cd "$BASE" && \
  LPC_WINDOW="" LPC_MAX_BUDGET="$BUDGET" LPC_INTERVAL_MS="$INTERVAL_B" INTENSITY="$INTENSITY" "$MOD_B" ) & p2=$!

trap 'echo; echo "[run] stopping..."; kill $p1 $p2 2>/dev/null || true' INT TERM

# --- pretty elapsed timer ---
start=$(date +%s)
while true; do
  now=$(date +%s); elapsed=$((now-start))
  printf "\r[run] elapsed: %02d:%02d / %02d:%02d  events=%-5s" \
    $((elapsed/60)) $((elapsed%60)) $((DUR/60)) $((DUR%60)) "$(wc -l < "$BUS")"
  if (( elapsed >= DUR )); then break; fi
  sleep 1
done
echo
kill $p1 $p2 2>/dev/null || true
wait 2>/dev/null || true

echo "[run] events written: $(wc -l < "$BUS")"
echo "[run] generating timeline..."
#python3 "$BASE/tools/gen_effects_timeline.py" "$BUS" "$TL" "$BASE/tools/effects_rules.json"
head -n 5 "$TL" || true

if [[ ! -s "$TL" || "$(wc -l < "$TL")" -le 1 ]]; then
  echo "[run] timeline empty — injecting mini sample"
  cat > "$TL" <<'CSV'
t_sec,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps
5,0,0,0,0,0
15,2,5,2,0,0
25,3,8,3,0,0
35,5,10,4,0,0
45,6,12,6,0,0
55,8,15,8,0,0
CSV
fi

echo "[run] building features..."
python3 "$BASE/tools/lpc_metrics.py" --timeline "$TL" --out "$FEATS" --win "$WIN"
echo "[run] feature head:"
head -n 5 "$FEATS" || true

echo "[run] ns-3 eval..."
cd "$NS3"
./ns3 run "scratch/drone_lpc_eval --timeline=$TL --out=$NS3_MET --simTime=60 --pktSize=512"
echo "[run] ns-3 metrics:"
column -t -s, "$NS3_MET" || true

echo
echo "[OK] done"
echo "  bus.log:              $BUS"
echo "  effect_timeline.csv:  $TL"
echo "  window_features.csv:  $FEATS"
echo "  ns3_metrics.csv:      $NS3_MET"
