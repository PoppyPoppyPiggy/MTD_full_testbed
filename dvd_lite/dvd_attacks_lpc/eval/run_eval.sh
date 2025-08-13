#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
NS3="${NS3_ROOT:-$HOME/MTD/MTD_full_testbed/ns-3.45/ns-3-dev}"
BUS="$BASE/attack_output/bus.log"
TL="$BASE/attack_output/effect_timeline.csv"
OUT="$BASE/attack_output/ns3_metrics.csv"

# 1) 타임라인 없거나 비면 생성 시도
if [[ ! -s "$TL" || "$(wc -l < "$TL")" -le 1 ]]; then
  echo "[eval] timeline empty → regenerating from bus.log"
  python3 "$BASE/tools/gen_effects_timeline.py" "$BUS" "$TL" "$BASE/tools/effects_rules.json" || true
fi

# 2) 그래도 비면 미니 샘플 투입(60초)
if [[ ! -s "$TL" || "$(wc -l < "$TL")" -le 1 ]]; then
  echo "[eval] injecting mini sample timeline"
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

# 3) ns-3 실행
cd "$NS3"
./ns3 run "scratch/drone_lpc_eval --timeline=$TL --out=$OUT --simTime=60 --pktSize=512"
echo "[ns-3] wrote: $OUT"
