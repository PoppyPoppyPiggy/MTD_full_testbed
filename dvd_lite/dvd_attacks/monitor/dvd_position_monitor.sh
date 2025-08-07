#!/bin/bash
# dvd_optimized_position_monitor.sh - 최적화된 DVD 위치정보 모니터링
# Purpose: 중요한 이벤트만 출력하는 효율적인 GPS 모니터링

source "$(dirname "$0")/common/colors.sh"
source "$(dirname "$0")/common/utils.sh"

# 전역 변수
MONITOR_DURATION=120
LOG_DIR="/tmp/dvd_position_logs"
POSITION_LOG="$LOG_DIR/position_tracking.log"
GPS_LOG="$LOG_DIR/gps_data.log"
ALERT_LOG="$LOG_DIR/gps_alerts.log"

# 위치 데이터 저장
declare -A POSITION_DATA
declare -A GPS_STATS

# 출력 제어
LAST_COORD_OUTPUT_TIME=0
COORD_OUTPUT_INTERVAL=5  # 5초마다 좌표 출력
LAST_CHANGE_OUTPUT_TIME=0
CHANGE_OUTPUT_INTERVAL=3  # 3초마다 변화 출력

print_position_banner() {
    clear
    echo -e "${BOLD}${CYAN}============================================${NC}"
    echo -e "${BOLD}${CYAN}   DVD Optimized Position Monitor         ${NC}"
    echo -e "${BOLD}${CYAN}============================================${NC}"
    echo -e "${BLUE}Purpose: Smart GPS spoofing detection${NC}"
    echo -e "${BLUE}Features: Filtered output, key events only${NC}"
    echo -e "${BLUE}Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo ""
}

setup_monitoring() {
    echo -e "${YELLOW}[*] Setting up optimized position monitoring...${NC}"
    
    mkdir -p "$LOG_DIR"
    
    # 로그 파일 초기화
    echo "=== Optimized Position Tracking Started at $(date) ===" > "$POSITION_LOG"
    echo "=== GPS Data Analysis Started at $(date) ===" > "$GPS_LOG"
    echo "=== GPS Security Alerts Started at $(date) ===" > "$ALERT_LOG"
    
    # 초기 통계
    GPS_STATS["total_messages"]=0
    GPS_STATS["significant_changes"]=0
    GPS_STATS["spoofing_events"]=0
    GPS_STATS["last_coordinate"]=""
    GPS_STATS["baseline_established"]=0
    
    echo -e "${GREEN}[✓] Optimized monitoring setup completed${NC}"
}

should_output_coordinate() {
    local current_time=$(date +%s)
    if [ $((current_time - LAST_COORD_OUTPUT_TIME)) -ge $COORD_OUTPUT_INTERVAL ]; then
        LAST_COORD_OUTPUT_TIME=$current_time
        return 0
    fi
    return 1
}

should_output_change() {
    local current_time=$(date +%s)
    if [ $((current_time - LAST_CHANGE_OUTPUT_TIME)) -ge $CHANGE_OUTPUT_INTERVAL ]; then
        LAST_CHANGE_OUTPUT_TIME=$current_time
        return 0
    fi
    return 1
}

is_significant_change() {
    local old_coords="$1"
    local new_coords="$2"
    
    # 좌표 값 추출
    local old_first=$(echo "$old_coords" | awk '{print $1}')
    local new_first=$(echo "$new_coords" | awk '{print $1}')
    
    # 변화량 계산
    local change=$(python3 -c "
try:
    old = float('$old_first')
    new = float('$new_first')
    diff = abs(new - old)
    # 0.001 이상 변화하면 significant
    print('1' if diff > 0.001 else '0')
except:
    print('0')
" 2>/dev/null || echo "0")
    
    [ "$change" = "1" ]
}

monitor_smart_gps() {
    echo -e "${YELLOW}[*] Starting smart GPS monitoring...${NC}"
    
    # 스마트 MAVLink GPS 분석
    timeout "$MONITOR_DURATION" tcpdump -i any -n -A port 14550 2>/dev/null | \
    while read line; do
        local timestamp=$(date '+%H:%M:%S')
        local epoch_time=$(date +%s)
        
        # GPS 관련 메시지 카운팅 (로그만)
        if echo "$line" | grep -iE "(gps|position|location)" >/dev/null; then
            GPS_STATS["total_messages"]=$((${GPS_STATS[total_messages]} + 1))
            echo "[$timestamp] GPS message #${GPS_STATS[total_messages]}" >> "$GPS_LOG"
        fi
        
        # 좌표 패턴 탐지
        local coords=$(echo "$line" | grep -oE "[0-9]{1,3}\.[0-9]{4,}" | head -2)
        
        if [ -n "$coords" ]; then
            local coord_line=$(echo "$coords" | tr '\n' ' ')
            
            # 모든 좌표는 로그에 기록
            echo "[$timestamp] Coordinates: $coord_line" >> "$GPS_LOG"
            
            # 화면 출력은 제한적으로
            if should_output_coordinate; then
                echo -e "${CYAN}[COORDS] $timestamp: $coord_line${NC}"
            fi
            
            # 베이스라인 설정 (처음 10개 메시지)
            if [ "${GPS_STATS[baseline_established]}" -eq 0 ] && [ "${GPS_STATS[total_messages]}" -gt 10 ]; then
                GPS_STATS["baseline_coordinate"]="$coord_line"
                GPS_STATS["baseline_established"]=1
                echo -e "${BLUE}[BASELINE] GPS baseline established: $coord_line${NC}"
                echo "[$timestamp] GPS baseline established: $coord_line" >> "$ALERT_LOG"
            fi
            
            # 의미있는 좌표 변화만 감지
            if [ -n "${GPS_STATS[last_coordinate]}" ] && [ "${GPS_STATS[last_coordinate]}" != "$coord_line" ]; then
                if is_significant_change "${GPS_STATS[last_coordinate]}" "$coord_line"; then
                    GPS_STATS["significant_changes"]=$((${GPS_STATS[significant_changes]} + 1))
                    
                    # 변화 출력 제어
                    if should_output_change; then
                        echo -e "${YELLOW}[CHANGE] Significant coordinate change detected${NC}"
                        echo "[$timestamp] Significant change: ${GPS_STATS[last_coordinate]} -> $coord_line" >> "$ALERT_LOG"
                    fi
                    
                    echo "[$timestamp] Coordinate change: ${GPS_STATS[last_coordinate]} -> $coord_line" >> "$POSITION_LOG"
                fi
            fi
            
            GPS_STATS["last_coordinate"]="$coord_line"
            
            # 스푸핑 탐지 (항상 즉시 출력)
            detect_spoofing_attack "$coord_line" "$timestamp"
        fi
        
        # 특정 MAVLink 스푸핑 좌표 탐지
        if echo "$line" | grep -E "(473566100|854619300)" >/dev/null; then
            GPS_STATS["spoofing_events"]=$((${GPS_STATS[spoofing_events]} + 1))
            echo "[$timestamp] MAVLINK SPOOFING: Spoofing coordinates in MAVLink packet" >> "$ALERT_LOG"
            echo -e "${BOLD}${RED}[SPOOFING] $timestamp: MAVLink GPS spoofing detected!${NC}"
        fi
    done &
}

detect_spoofing_attack() {
    local coordinates="$1"
    local timestamp="$2"
    
    # 알려진 스푸핑 패턴들
    local spoofing_patterns=(
        "47.35"     # GPS 스크립트 latitude
        "85.46"     # GPS 스크립트 longitude  
        "47.3566"   # 정확한 패턴
        "85.4619"   # 정확한 패턴
    )
    
    for pattern in "${spoofing_patterns[@]}"; do
        if echo "$coordinates" | grep -q "$pattern"; then
            GPS_STATS["spoofing_events"]=$((${GPS_STATS[spoofing_events]} + 1))
            echo "[$timestamp] SPOOFING DETECTED: Pattern '$pattern' found in coordinates: $coordinates" >> "$ALERT_LOG"
            echo -e "${BOLD}${RED}[SPOOFED] $timestamp: GPS spoofing pattern '$pattern' detected!${NC}"
            return
        fi
    done
    
    # 베이스라인과 큰 차이 탐지 (1도 이상)
    if [ "${GPS_STATS[baseline_established]}" -eq 1 ]; then
        local baseline_coord=${GPS_STATS[baseline_coordinate]}
        local baseline_first=$(echo "$baseline_coord" | awk '{print $1}')
        local current_first=$(echo "$coordinates" | awk '{print $1}')
        
        local coord_diff=$(python3 -c "
try:
    baseline = float('$baseline_first')
    current = float('$current_first')
    diff = abs(current - baseline)
    print(f'{diff:.6f}')
except:
    print('0.0')
" 2>/dev/null || echo "0.0")
        
        # 1도 이상 차이나면 스푸핑 의심
        if [ -n "$coord_diff" ] && [ "$(echo "$coord_diff > 1.0" | bc 2>/dev/null || echo 0)" = "1" ]; then
            echo "[$timestamp] SUSPICIOUS JUMP: ${coord_diff}° jump from baseline" >> "$ALERT_LOG"
            echo -e "${RED}[SUSPICIOUS] $timestamp: Large coordinate jump (${coord_diff}°)${NC}"
        fi
    fi
}

analyze_attack_patterns() {
    echo -e "${YELLOW}[*] Starting attack pattern analysis...${NC}"
    
    while [ ${POSITION_DATA["monitoring_active"]:-1} -eq 1 ]; do
        local timestamp=$(date '+%H:%M:%S')
        
        # 1분마다 분석
        sleep 60
        
        if [ -f "$GPS_LOG" ]; then
            # 최근 1분간 메시지 수
            local current_minute=$(date '+%H:%M')
            local recent_count=$(grep "$current_minute" "$GPS_LOG" 2>/dev/null | wc -l)
            
            # 고빈도 공격 탐지 (분당 100개 초과)
            if [ "$recent_count" -gt 100 ]; then
                echo "[$timestamp] HIGH FREQUENCY ATTACK: $recent_count messages/minute" >> "$ALERT_LOG"
                echo -e "${RED}[ATTACK] High frequency GPS attack: $recent_count messages/minute${NC}"
            fi
            
            # 전체 통계 업데이트
            local total_msg=${GPS_STATS[total_messages]:-0}
            local sig_changes=${GPS_STATS[significant_changes]:-0}
            local spoofing_events=${GPS_STATS[spoofing_events]:-0}
            
            echo "[$timestamp] Stats: Total=$total_msg, Changes=$sig_changes, Spoofing=$spoofing_events" >> "$POSITION_LOG"
        fi
    done &
}

show_status_dashboard() {
    echo -e "${YELLOW}[*] Starting status dashboard (30s intervals)...${NC}"
    
    while [ ${POSITION_DATA["monitoring_active"]:-1} -eq 1 ]; do
        sleep 30
        
        echo -e "\n${BOLD}${CYAN}=== GPS Security Status Dashboard ===${NC}"
        
        # 주요 통계
        local total_msg=${GPS_STATS[total_messages]:-0}
        local sig_changes=${GPS_STATS[significant_changes]:-0}
        local spoofing_events=${GPS_STATS[spoofing_events]:-0}
        local last_coord=${GPS_STATS[last_coordinate]:-"N/A"}
        
        echo -e "${GREEN}GPS Activity Summary:${NC}"
        echo -e "  Total Messages: $total_msg"
        echo -e "  Significant Changes: $sig_changes"
        echo -e "  Current Position: $last_coord"
        
        # 보안 상태
        if [ "$spoofing_events" -gt 0 ]; then
            echo -e "${BOLD}${RED}  🚨 SECURITY ALERT: $spoofing_events spoofing events detected!${NC}"
        else
            echo -e "${BLUE}  ✅ Security Status: Normal${NC}"
        fi
        
        # 최근 보안 이벤트
        if [ -f "$ALERT_LOG" ]; then
            local recent_alerts=$(tail -2 "$ALERT_LOG" 2>/dev/null | grep -v "Started at")
            if [ -n "$recent_alerts" ]; then
                echo -e "${YELLOW}Recent Security Events:${NC}"
                echo "$recent_alerts" | sed 's/^/  /'
            fi
        fi
        
        # 활동 수준
        local current_minute=$(date '+%H:%M')
        local current_activity=$(grep "$current_minute" "$GPS_LOG" 2>/dev/null | wc -l)
        
        if [ "$current_activity" -gt 50 ]; then
            echo -e "${RED}  ⚠️  High Activity: $current_activity messages this minute${NC}"
        else
            echo -e "${CYAN}  📊 Activity Level: $current_activity messages/minute${NC}"
        fi
    done &
}

generate_security_report() {
    echo -e "${CYAN}[*] Generating GPS security report...${NC}"
    
    local report_file="$LOG_DIR/gps_security_report_$(date +%Y%m%d_%H%M%S).txt"
    
    local total_msg=${GPS_STATS[total_messages]:-0}
    local sig_changes=${GPS_STATS[significant_changes]:-0}
    local spoofing_events=${GPS_STATS[spoofing_events]:-0}
    
    cat > "$report_file" << EOF
=== DVD GPS Security Monitoring Report ===
Generated: $(date)
Monitoring Duration: $MONITOR_DURATION seconds

=== GPS Activity Analysis ===
Total GPS Messages Processed: $total_msg
Significant Position Changes: $sig_changes  
Baseline Established: $([ "${GPS_STATS[baseline_established]}" = "1" ] && echo "Yes" || echo "No")
Final Position: ${GPS_STATS[last_coordinate]:-N/A}

=== Security Assessment ===
EOF
    
    if [ "$spoofing_events" -gt 0 ]; then
        cat >> "$report_file" << EOF
SECURITY STATUS: ⚠️  ATTACK DETECTED
Attack Type: GPS Spoofing
Events Detected: $spoofing_events
Confidence Level: HIGH
Risk Assessment: Active GPS manipulation detected

Recommended Actions:
1. Verify drone GPS integrity
2. Switch to backup navigation systems
3. Investigate attack source
4. Implement GPS authentication
EOF
    else
        cat >> "$report_file" << EOF
SECURITY STATUS: ✅ SECURE
Attack Type: None detected
Risk Assessment: Normal GPS operation
Confidence Level: No threats identified

System Status: GPS signals appear authentic
EOF
    fi
    
    cat >> "$report_file" << EOF

=== Log Files ===
Detailed GPS Data: $GPS_LOG
Position Changes: $POSITION_LOG
Security Alerts: $ALERT_LOG

=== Technical Details ===
Message Processing Rate: $([ "$total_msg" -gt 0 ] && echo "scale=2; $total_msg / ($MONITOR_DURATION / 60)" | bc 2>/dev/null || echo "0") messages/minute
Change Detection Rate: $([ "$sig_changes" -gt 0 ] && [ "$total_msg" -gt 0 ] && echo "scale=2; $sig_changes * 100 / $total_msg" | bc 2>/dev/null || echo "0")%
EOF
    
    echo -e "${GREEN}[✓] GPS security report generated: $report_file${NC}"
}

cleanup_monitoring() {
    echo -e "${YELLOW}[*] Cleaning up optimized monitoring...${NC}"
    
    POSITION_DATA["monitoring_active"]=0
    
    # 백그라운드 프로세스 정리
    pkill -f "tcpdump.*14550" 2>/dev/null
    
    echo -e "${GREEN}[✓] Optimized monitoring cleanup completed${NC}"
}

main() {
    print_position_banner
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[!] Root privileges required${NC}"
        exit 1
    fi
    
    # bc 패키지 확인
    if ! command -v bc >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Installing bc package...${NC}"
        apt-get update -qq && apt-get install -y bc >/dev/null 2>&1
    fi
    
    # 모니터링 기간 설정
    MONITOR_DURATION=${1:-120}
    
    # 신호 핸들러
    trap cleanup_monitoring SIGINT SIGTERM
    
    # 모니터링 시작
    setup_monitoring
    
    # 모니터링 활성화
    POSITION_DATA["monitoring_active"]=1
    
    # 최적화된 모니터링 시작
    monitor_smart_gps
    analyze_attack_patterns
    show_status_dashboard
    
    echo -e "${GREEN}[✓] Optimized GPS monitoring active!${NC}"
    echo -e "${YELLOW}[*] Monitoring for $MONITOR_DURATION seconds...${NC}"
    echo -e "${BLUE}[*] Output optimized: Key events only${NC}"
    echo -e "${BLUE}[*] Will detect GPS spoofing coordinates: 47.35*, 85.46*${NC}"
    echo -e "${CYAN}[*] Full logs saved to: $LOG_DIR${NC}"
    echo ""
    
    # 대기
    sleep "$MONITOR_DURATION"
    
    # 모니터링 비활성화
    POSITION_DATA["monitoring_active"]=0
    sleep 3
    
    # 보고서 생성
    generate_security_report
    
    # 정리
    cleanup_monitoring
    
    echo -e "\n${BOLD}${GREEN}[✓] GPS Security Monitoring Completed${NC}"
    
    # 최종 결과 요약
    local spoofing_events=${GPS_STATS[spoofing_events]:-0}
    if [ "$spoofing_events" -gt 0 ]; then
        echo -e "${BOLD}${RED}🚨 RESULT: GPS SPOOFING ATTACK DETECTED ($spoofing_events events)${NC}"
    else
        echo -e "${BOLD}${GREEN}✅ RESULT: No GPS spoofing detected - System secure${NC}"
    fi
}

main "$@"