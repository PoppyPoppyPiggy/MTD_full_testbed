#!/usr/bin/env bash
# 사용법:
#  scripts/scenario_lpc_mtd_probe.sh wifi_slow_scan high
#  scripts/scenario_lpc_mtd_probe.sh <attack_name> <level>
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$BASE/00_env.sh" ] && . "$BASE/00_env.sh" || true
. "$BASE/00_env_ext.sh"

ATTACK="${1:-wifi_slow_scan}"
LEVEL="${2:-high}"

# 0) 감시기 켜기(백그라운드) — 내부 상태 시계열
if ! pgrep -f "monitors/dvd_watch.sh" >/dev/null; then
  nohup "$BASE/monitors/dvd_watch.sh" >/dev/null 2>&1 &
fi

# 1) 공격(모듈이 있으면 호출, 없으면 기존 런너 사용)
if [ -x "$BASE/modules/attacks/${ATTACK}.sh" ]; then
  "$BASE/modules/attacks/${ATTACK}.sh" "$LEVEL"
else
  # 프로젝트의 기존 attack 실행기가 있을 경우 여기를 맞춰 호출
  if [ -x "$BASE/attackctl/run_attack.sh" ]; then
    "$BASE/attackctl/run_attack.sh" "$ATTACK" "$LEVEL"
  else
    echo "Attack runner not found for $ATTACK/$LEVEL" >&2; exit 2
  fi
fi

# 2) MTD 단계(예: 포트 셔플)
"$BASE/modules/mtd/mtd_port_shuffle.sh"

# 3) Probe(스냅샷 1회)
"$BASE/modules/probe/probe_dvd_status.sh"

# 4) 타임라인 생성(bus.log → effect_timeline.csv)
python3 "$BASE/tools/gen_effects_timeline.py" \
  "$BUS_LOG" -o "$TIMELINE_CSV" --rules "$BASE/tools/effects_rules.json"

# 5) ns-3 재현 및 메트릭 추출
"$NS3_BIN" run "scratch/$NS3_SCRATCH --timeline=$TIMELINE_CSV --simTime=30" \
  --disable-warnings || true

# 6) 완료 안내
echo "[scenario] done. timeline=$TIMELINE_CSV  ns3_metrics=$NS3_METRICS  bus_dvd=$BUS_DVD_LOG"
