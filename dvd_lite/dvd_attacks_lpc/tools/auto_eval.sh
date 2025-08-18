#!/usr/bin/env bash
# tools/auto_eval.sh
set -Eeuo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

source 00_env.sh

OUT_DIR="$BASE_DIR/attack_output"
RULES="${EFFECTS_RULES:-$BASE_DIR/tools/effects_rules.json}"
TIMELINE="$OUT_DIR/effect_timeline.csv"
BUS="$OUT_DIR/bus.log"

mkdir -p "$OUT_DIR"

echo "[auto_eval] 1) 타임라인 생성"
if [[ ! -s "$BUS" ]]; then
  echo "[WARN] bus.log가 비었습니다. 스모크 이벤트를 5개 삽입합니다."
  for i in $(seq 0 4); do
    printf '[%s] [telemetry_trickle_jam] level=high phase=run\n' \
      "$(date -u -d "@$(( $(date -u +%s) + i*3 ))" +%FT%TZ)" >> "$BUS"
  done
fi

python3 "$BASE_DIR/tools/gen_effects_timeline.py" "$BUS" -o "$TIMELINE" --rules "$RULES"
rows=$(wc -l < "$TIMELINE" || echo 0)
echo "[auto_eval] timeline rows=$rows"
if [[ "$rows" -le 1 ]]; then
  echo "[ERROR] 타임라인이 비어 있습니다. 룰/버스로그를 확인하세요." >&2
  exit 2
fi

echo "[auto_eval] 2) 윈도우 피처 산출(win=${WIN:-3}, stride=${STRIDE:-1})"
python3 "$BASE_DIR/tools/lpc_metrics_cli.py" "$TIMELINE" \
  -o "$OUT_DIR/window_features.csv" --win "${WIN:-3}" --stride "${STRIDE:-1}"

echo "[auto_eval] 3) ns-3 평가 + NetAnim"
ANIM_OUT="${ANIM_OUT:-$OUT_DIR/netanim.xml}" \
SIM_TIME="${SIM_TIME:-90}" PKT_SIZE="${PKT_SIZE:-512}" \
NS3_BUILD_MODE="${NS3_BUILD_MODE:-once}" \
bash "$BASE_DIR/scripts/run_ns3_eval.sh"

echo "[auto_eval] done:"
ls -lh "$OUT_DIR"/{effect_timeline.csv,window_features.csv,ns3_metrics.csv,netanim.xml} 2>/dev/null || true
