#!/usr/bin/env bash
# gps_coordinate_spoof.sh - GPS 좌표 스푸핑 공격
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
. "$SCRIPT_DIR/../00_env.sh"
. "$SCRIPT_DIR/../sh_core/lpc_core.sh" 2>/dev/null || true

ACT_NAME="gps_coordinate_spoof"
TARGETS_FILE="${TARGETS_FILE:-"$SCRIPT_DIR/../scenarios/targets.txt"}"

# GPS 스푸핑 설정
INTENSITY="${INTENSITY:-medium}"
SPOOF_MODE="${SPOOF_MODE:-drift}"  # drift, jump, circle
BASE_LAT="${BASE_LAT:-37.7749}"    # San Francisco
BASE_LON="${BASE_LON:-122.4194}"
BASE_ALT="${BASE_ALT:-100}"

# ---- GPS 좌표 스푸핑 공격 ----
do_act(){
  local target="${1:-drone_gps}"
  local phase; phase="$(current_phase 2>/dev/null || echo 'cruise')"
  
  # 강도별 스푸핑 정도 조정
  local drift_rate lat_offset lon_offset alt_offset
  case "$INTENSITY" in
    low)    drift_rate=0.1; lat_offset=$(awk "BEGIN {print rand()*0.001-0.0005}"); lon_offset=$(awk "BEGIN {print rand()*0.001-0.0005}"); alt_offset=$(awk "BEGIN {print rand()*2-1}") ;;
    medium) drift_rate=0.5; lat_offset=$(awk "BEGIN {print rand()*0.005-0.0025}"); lon_offset=$(awk "BEGIN {print rand()*0.005-0.0025}"); alt_offset=$(awk "BEGIN {print rand()*10-5}") ;;
    high)   drift_rate=1.0; lat_offset=$(awk "BEGIN {print rand()*0.01-0.005}"); lon_offset=$(awk "BEGIN {print rand()*0.01-0.005}"); alt_offset=$(awk "BEGIN {print rand()*20-10}") ;;
  esac
  
  # 스푸핑된 좌표 계산
  local spoofed_lat spoofed_lon spoofed_alt
  spoofed_lat=$(awk "BEGIN {printf \"%.6f\", $BASE_LAT + $lat_offset}")
  spoofed_lon=$(awk "BEGIN {printf \"%.6f\", $BASE_LON + $lon_offset}")
  spoofed_alt=$(awk "BEGIN {printf \"%.1f\", $BASE_ALT + $alt_offset}")
  
  # GPS 정확도 저하 시뮬레이션
  local accuracy_loss satellites_visible hdop
  case "$INTENSITY" in
    low)    accuracy_loss=1.5; satellites_visible=10; hdop=1.2 ;;
    medium) accuracy_loss=3.0; satellites_visible=7; hdop=2.5 ;;
    high)   accuracy_loss=5.0; satellites_visible=4; hdop=4.0 ;;
  esac
  
  local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  
  # GPS 스푸핑 시뮬레이션 (실제 환경에서는 SDR 사용)
  # 여기서는 로깅과 효과 시뮬레이션만 수행
  
  # 로그 기록
  echo "[$timestamp] [$ACT_NAME] phase=$phase target=$target intensity=$INTENSITY mode=$SPOOF_MODE lat=$spoofed_lat lon=$spoofed_lon alt=$spoofed_alt accuracy_loss=${accuracy_loss}m satellites=$satellites_visible hdop=$hdop drift_rate=$drift_rate" >> "$LPC_LOG_DIR/bus.log"
  
  # GPS 상태 파일 업데이트 (시뮬레이션용)
  local gps_status_file="$LPC_LOG_DIR/gps_spoof_status.csv"
  if [[ ! -f "$gps_status_file" ]]; then
    echo "timestamp,lat,lon,alt,accuracy_loss,satellites,hdop,spoofed" > "$gps_status_file"
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S'),$spoofed_lat,$spoofed_lon,$spoofed_alt,$accuracy_loss,$satellites_visible,$hdop,true" >> "$gps_status_file"
  
  return 0
}

main(){
  if command -v lpc_loop >/dev/null 2>&1; then
    lpc_loop do_act "$TARGETS_FILE"
  else
    # Fallback: 시간 기반 루프
    local duration="${DUR:-30}"
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    
    echo "[DEBUG] GPS 스푸핑 시작: ${duration}초 동안"
    
    while [[ $(date +%s) -lt $end_time ]]; do
      do_act
      sleep "${LPC_INTERVAL_MS:-3000}" | awk '{print $1/1000}' | xargs sleep 2>/dev/null || sleep 3
    done
    
    echo "[DEBUG] GPS 스푸핑 완료"
  fi
}

main "$@"