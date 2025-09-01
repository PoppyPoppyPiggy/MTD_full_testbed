#!/usr/bin/env bash
set -Eeuo pipefail

: "${ATK_DIR:?ATK_DIR not set}"
: "${SIM_TIME:=60}"
: "${TIMELINE_DT:=0.1}"

BUS_BASE="${ATK_DIR}/attack_output/bus.log"
BUS_MTD="${ATK_DIR}/attack_output/bus_mtd.log"  # 있으면 사용
TL_BASE="${ATK_DIR}/attack_output/effect_timeline.baseline.csv"
TL_MTD="${ATK_DIR}/attack_output/effect_timeline.mtd.csv"
RULES="${ATK_DIR}/tools/effects_rules.json"
GEN="${ATK_DIR}/tools/gen_effects_timeline.py"

mkdir -p "${ATK_DIR}/attack_output"

mk_zero_timeline() {
  local out="$1"
  local sim="$2"
  local dt="$3"
  python3 - "$out" "$sim" "$dt" <<'PY'
import sys,math
out,sim,dt=sys.argv[1],float(sys.argv[2]),float(sys.argv[3])
with open(out,"w") as f:
    f.write("t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps\n")
    n=int(math.floor(sim/dt))+1
    for i in range(n+1):
        t=round(i*dt,6)
        f.write(f"{t},0,0,0,0,0\n")
PY
}

gen_from_bus() {
  local bus="$1"; local out="$2"
  if [[ -s "$GEN" && -s "$bus" ]]; then
    if [[ -s "$RULES" ]]; then
      python3 "$GEN" "$bus" -o "$out" --dt "$TIMELINE_DT" --rules "$RULES" || mk_zero_timeline "$out" "$SIM_TIME" "$TIMELINE_DT"
    else
      python3 "$GEN" "$bus" -o "$out" --dt "$TIMELINE_DT" || mk_zero_timeline "$out" "$SIM_TIME" "$TIMELINE_DT"
    fi
  else
    mk_zero_timeline "$out" "$SIM_TIME" "$TIMELINE_DT"
  fi
}

echo "[gen_timelines] baseline -> ${TL_BASE}"
gen_from_bus "$BUS_BASE" "$TL_BASE"
if [[ -s "$BUS_MTD" ]]; then
  echo "[gen_timelines] mtd      -> ${TL_MTD} (from bus_mtd.log)"
  gen_from_bus "$BUS_MTD" "$TL_MTD"
else
  echo "[gen_timelines] mtd      -> ${TL_MTD} (fallback=baseline)"
  cp -f "$TL_BASE" "$TL_MTD"
fi

# 헤더 검증
head -n1 "$TL_BASE" | grep -q "t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps"
head -n1 "$TL_MTD"  | grep -q "t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps"
echo "[gen_timelines] done."
