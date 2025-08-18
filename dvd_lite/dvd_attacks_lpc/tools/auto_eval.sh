#!/usr/bin/env bash
set -Eeuo pipefail
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"; [[ -f 00_env.sh ]] && source 00_env.sh || true

OUT="$BASE_DIR/attack_output"; RULES="${EFFECTS_RULES:-$BASE_DIR/tools/effects_rules.json}"
BUS="$OUT/bus.log"; TIMELINE="$OUT/effect_timeline.csv"

mkdir -p "$OUT"
echo "[auto_eval] 1) timeline"
if [[ ! -s "$BUS" ]]; then
  echo "[auto_eval] bus.log empty -> smoke events"
  for i in $(seq 0 4); do
    printf '[%s] [telemetry_trickle_jam] level=high phase=run\n' "$(date -u -d "@$(( $(date -u +%s) + i*2 ))" +%FT%TZ)" >> "$BUS"
  done
fi
python3 tools/gen_effects_timeline.py "$BUS" -o "$TIMELINE" --rules "$RULES"
rows=$(wc -l < "$TIMELINE" || echo 0); echo "[auto_eval] rows=$rows"
[[ "$rows" -le 1 ]] && { echo "[auto_eval] empty timeline"; exit 2; }

echo "[auto_eval] 2) windows"
python3 tools/lpc_metrics_cli.py "$TIMELINE" -o "$OUT/window_features.csv" --win "${WIN:-3}" --stride "${STRIDE:-1}"

echo "[auto_eval] 3) ns-3 + NetAnim"
AUTO_SIM_TIME=1 ANIM_OUT="$OUT/netanim.xml" NS3_BUILD_MODE="${NS3_BUILD_MODE:-once}" bash scripts/run_ns3_eval.sh

echo "[auto_eval] done"; ls -lh "$OUT"/{effect_timeline.csv,window_features.csv,ns3_metrics.csv,netanim.xml} 2>/dev/null || true
