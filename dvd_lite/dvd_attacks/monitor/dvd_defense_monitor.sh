#!/bin/bash
# dvd_defense_monitor.sh - DVD 방어자 관점 공격 탐지 모니터링 시스템
# Purpose: 드론 시스템 내부에서 공격 패턴 탐지 및 실시간 모니터링

source "$(dirname "$0")/common/colors.sh"
source "$(dirname "$0")/common/utils.sh"

# 전역 변수
MONITOR_DURATION=60
LOG_DIR="/tmp/dvd_defense_logs"
ALERT_LOG="$LOG_DIR/security_alerts.log"
TRAFFIC_LOG="$LOG_DIR/network_traffic.log"

# 실제 MAVLink 포트들 (분석 결과 기반)
MAVLINK_PORTS=("14550" "5760")
MAVLINK_IPS=("10.13.0.2" "10.13.0.3" "10.13.0.4" "192.168.13.1" "192.168.13.14")

# 공격 탐지 카운터
declare -A ATTACK_COUNTERS
declare -A BASELINE_COUNTERS

print_defense_banner() {
    clear
    echo -e "${BOLD}${RED}============================================${NC}"
    echo -e "${BOLD}${RED}   DVD Fixed Defense Monitor             ${NC}"
    echo -e "${BOLD}${RED}============================================${NC}"
    echo -e "${BLUE}Target: Real MAVLink Traffic (Port 14550)${NC}"
    echo -e "${BLUE}Enhanced: Attack Pattern Detection${NC}"
    echo -e "${BLUE}Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo ""
}

setup_monitoring() {
    echo -e "${YELLOW}[*] Setting up enhanced monitoring...${NC}"
    
    mkdir -p "$LOG_DIR"
    echo "=== Enhanced Defense Monitor Started at $(date) ===" > "$ALERT_LOG"
    echo "=== Network Traffic Analysis Started at $(date) ===" > "$TRAFFIC_LOG"
    
    # 베이스라인 수집
    collect_accurate_baseline
    
    echo -e "${GREEN}[✓] Enhanced monitoring ready${NC}"
}

collect_accurate_baseline() {
    echo -e "${CYAN}[*] Collecting accurate baseline...${NC}"
    
    # MAVProxy 프로세스 상태
    local mavproxy_count=$(docker exec ground-control-station ps aux 2>/dev/null | grep mavproxy | grep -v grep | wc -l)
    BASELINE_COUNTERS["mavproxy_processes"]=$mavproxy_count
    
    # 14550 포트 연결 수
    local port_connections=$(docker exec ground-control-station netstat -an 2>/dev/null | grep 14550 | wc -l)
    BASELINE_COUNTERS["port_14550_connections"]=$port_connections
    
    # 네트워크 패킷 카운트
    local udp_packets=$(docker exec ground-control-station netstat -su 2>/dev/null | grep "packets received" | head -1 | awk '{print $1}')
    BASELINE_COUNTERS["udp_packets"]=${udp_packets:-0}
    
    echo -e "${GREEN}[✓] Baseline collected:${NC}"
    echo -e "${BLUE}    MAVProxy processes: ${BASELINE_COUNTERS[mavproxy_processes]}${NC}"
    echo -e "${BLUE}    Port 14550 connections: ${BASELINE_COUNTERS[port_14550_connections]}${NC}"
    echo -e "${BLUE}    UDP packets: ${BASELINE_COUNTERS[udp_packets]}${NC}"
    echo ""
}

monitor_real_mavlink_traffic() {
    echo -e "${YELLOW}[*] Starting real MAVLink traffic monitoring...${NC}"
    
    # 모든 MAVLink 포트 모니터링
    for port in "${MAVLINK_PORTS[@]}"; do
        timeout "$MONITOR_DURATION" tcpdump -i any -n port $port -c 200 2>/dev/null | while read line; do
            local timestamp=$(date '+%H:%M:%S')
            echo "$timestamp PORT_$port: $line" >> "$TRAFFIC_LOG"
            
            # 공격 패턴 즉시 분석
            analyze_packet_realtime "$line" "$port"
        done &
    done
    
    # Docker 네트워크 트래픽도 모니터링
    timeout "$MONITOR_DURATION" tcpdump -i docker0 -n 2>/dev/null | while read line; do
        if echo "$line" | grep -E "(14550|5760)" >/dev/null; then
            local timestamp=$(date '+%H:%M:%S')
            echo "$timestamp DOCKER: $line" >> "$TRAFFIC_LOG"
            analyze_packet_realtime "$line" "docker"
        fi
    done &
}

analyze_packet_realtime() {
    local packet="$1"
    local port="$2"
    local timestamp=$(date '+%H:%M:%S')
    
    # UDP 패킷 카운팅
    if echo "$packet" | grep -q "UDP"; then
        ATTACK_COUNTERS["udp_count"]=$((${ATTACK_COUNTERS[udp_count]:-0} + 1))
    fi
    
    # 특정 IP에서 온 패킷 카운팅
    for ip in "${MAVLINK_IPS[@]}"; do
        if echo "$packet" | grep -q "$ip"; then
            ATTACK_COUNTERS["ip_$ip"]=$((${ATTACK_COUNTERS["ip_$ip"]:-0} + 1))
            
            # 임계값 초과 시 알림
            if [ "${ATTACK_COUNTERS["ip_$ip"]}" -gt 5 ]; then
                log_security_alert "HIGH" "High traffic from $ip detected: ${ATTACK_COUNTERS["ip_$ip"]} packets"
            fi
        fi
    done
    
    # MAVLink 메시지 패턴 탐지
    if echo "$packet" | grep -E "(HEARTBEAT|ATTITUDE|GPS|BATTERY)" >/dev/null; then
        ATTACK_COUNTERS["mavlink_messages"]=$((${ATTACK_COUNTERS[mavlink_messages]:-0} + 1))
        
        if [ "${ATTACK_COUNTERS[mavlink_messages]}" -gt 10 ]; then
            log_security_alert "MEDIUM" "Unusual MAVLink message activity detected"
        fi
    fi
    
    # 빠른 연속 패킷 탐지 (스푸핑 징후)
    local current_second=$(date +%s)
    if [ "${ATTACK_COUNTERS[last_packet_time]:-0}" -eq "$current_second" ]; then
        ATTACK_COUNTERS["rapid_packets"]=$((${ATTACK_COUNTERS[rapid_packets]:-0} + 1))
        
        if [ "${ATTACK_COUNTERS[rapid_packets]}" -gt 3 ]; then
            log_security_alert "HIGH" "Rapid packet transmission detected - Possible spoofing attack"
        fi
    else
        ATTACK_COUNTERS["rapid_packets"]=0
    fi
    ATTACK_COUNTERS["last_packet_time"]=$current_second
}

monitor_service_health() {
    echo -e "${YELLOW}[*] Monitoring service health...${NC}"
    
    while [ ${ATTACK_COUNTERS["monitoring_active"]:-1} -eq 1 ]; do
        # MAVProxy 상태 체크
        local current_mavproxy=$(docker exec ground-control-station ps aux 2>/dev/null | grep mavproxy | grep -v grep | wc -l)
        local baseline_mavproxy=${BASELINE_COUNTERS["mavproxy_processes"]:-0}
        
        if [ "$current_mavproxy" -lt "$baseline_mavproxy" ]; then
            log_security_alert "CRITICAL" "MAVProxy service disrupted - DoS attack suspected"
        fi
        
        # 포트 상태 체크
        local current_port_conn=$(docker exec ground-control-station netstat -an 2>/dev/null | grep 14550 | wc -l)
        local baseline_port_conn=${BASELINE_COUNTERS["port_14550_connections"]:-0}
        
        if [ "$current_port_conn" -gt $((baseline_port_conn + 5)) ]; then
            log_security_alert "HIGH" "Abnormal connections to MAVLink port - Possible attack"
        fi
        
        # CPU 사용률 체크
        local cpu_usage=$(docker stats --no-stream --format "{{.CPUPerc}}" ground-control-station 2>/dev/null | sed 's/%//' | cut -d. -f1)
        
        if [ "${cpu_usage:-0}" -gt 50 ]; then
            log_security_alert "MEDIUM" "High CPU usage on GCS: ${cpu_usage}% - Resource attack possible"
        fi
        
        sleep 5
    done &
}

check_attack_indicators() {
    echo -e "${YELLOW}[*] Checking attack indicators...${NC}"
    
    while [ ${ATTACK_COUNTERS["monitoring_active"]:-1} -eq 1 ]; do
        # 패킷 비율 분석
        local total_udp=${ATTACK_COUNTERS[udp_count]:-0}
        local baseline_udp=${BASELINE_COUNTERS[udp_packets]:-0}
        
        if [ "$total_udp" -gt $((baseline_udp + 20)) ]; then
            log_security_alert "HIGH" "UDP traffic spike detected: $total_udp packets (baseline: $baseline_udp)"
        fi
        
        # IP별 트래픽 분석
        for ip in "${MAVLINK_IPS[@]}"; do
            local ip_count=${ATTACK_COUNTERS["ip_$ip"]:-0}
            if [ "$ip_count" -gt 15 ]; then
                log_security_alert "HIGH" "Suspicious activity from $ip: $ip_count packets"
            fi
        done
        
        # MAVLink 메시지 폭증 체크
        local mavlink_count=${ATTACK_COUNTERS[mavlink_messages]:-0}
        if [ "$mavlink_count" -gt 30 ]; then
            log_security_alert "CRITICAL" "MAVLink message flood detected: $mavlink_count messages"
        fi
        
        sleep 3
    done &
}

log_security_alert() {
    local severity="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    local color_code
    case "$severity" in
        "CRITICAL") color_code="${BOLD}${RED}" ;;
        "HIGH") color_code="${RED}" ;;
        "MEDIUM") color_code="${YELLOW}" ;;
        "LOW") color_code="${BLUE}" ;;
        *) color_code="${WHITE}" ;;
    esac
    
    # 실시간 콘솔 출력
    echo -e "${color_code}[${severity}] ${timestamp}: ${message}${NC}"
    
    # 로그 파일 기록
    echo "${timestamp} [${severity}] ${message}" >> "$ALERT_LOG"
    
    # 공격 탐지 카운터 업데이트
    ATTACK_COUNTERS["alert_${severity,,}"]=$((${ATTACK_COUNTERS["alert_${severity,,}"]:-0} + 1))
}

show_real_time_stats() {
    while [ ${ATTACK_COUNTERS["monitoring_active"]:-1} -eq 1 ]; do
        sleep 10
        
        echo -e "\n${CYAN}=== Real-time Statistics ===${NC}"
        echo -e "${BLUE}UDP Packets: ${ATTACK_COUNTERS[udp_count]:-0}${NC}"
        echo -e "${BLUE}MAVLink Messages: ${ATTACK_COUNTERS[mavlink_messages]:-0}${NC}"
        echo -e "${BLUE}Rapid Packets: ${ATTACK_COUNTERS[rapid_packets]:-0}${NC}"
        
        # Top 활성 IP들
        echo -e "${BLUE}Active IPs:${NC}"
        for ip in "${MAVLINK_IPS[@]}"; do
            local count=${ATTACK_COUNTERS["ip_$ip"]:-0}
            if [ "$count" -gt 0 ]; then
                echo -e "${BLUE}  $ip: $count packets${NC}"
            fi
        done
        
        # 알림 카운트
        local critical=${ATTACK_COUNTERS[alert_critical]:-0}
        local high=${ATTACK_COUNTERS[alert_high]:-0}
        local medium=${ATTACK_COUNTERS[alert_medium]:-0}
        
        if [ $((critical + high + medium)) -gt 0 ]; then
            echo -e "${RED}Alerts: Critical($critical), High($high), Medium($medium)${NC}"
        fi
        echo ""
    done &
}

cleanup_monitoring() {
    echo -e "${YELLOW}[*] Cleaning up monitoring...${NC}"
    
    ATTACK_COUNTERS["monitoring_active"]=0
    
    # 네트워크 모니터링 프로세스 종료
    pkill -f "tcpdump.*14550" 2>/dev/null
    pkill -f "tcpdump.*5760" 2>/dev/null
    pkill -f "tcpdump.*docker0" 2>/dev/null
    
    echo -e "${GREEN}[✓] Cleanup completed${NC}"
}

generate_final_report() {
    echo -e "${CYAN}[*] Generating final attack detection report...${NC}"
    
    local total_alerts=$((${ATTACK_COUNTERS[alert_critical]:-0} + ${ATTACK_COUNTERS[alert_high]:-0} + ${ATTACK_COUNTERS[alert_medium]:-0}))
    
    echo -e "\n${BOLD}${GREEN}=== ATTACK DETECTION SUMMARY ===${NC}"
    
    if [ "$total_alerts" -gt 0 ]; then
        echo -e "${RED}🚨 ATTACKS DETECTED!${NC}"
        echo -e "${RED}  Critical Alerts: ${ATTACK_COUNTERS[alert_critical]:-0}${NC}"
        echo -e "${RED}  High Alerts: ${ATTACK_COUNTERS[alert_high]:-0}${NC}"
        echo -e "${YELLOW}  Medium Alerts: ${ATTACK_COUNTERS[alert_medium]:-0}${NC}"
        
        echo -e "\n${YELLOW}🔍 Traffic Analysis:${NC}"
        echo -e "${BLUE}  Total UDP packets: ${ATTACK_COUNTERS[udp_count]:-0}${NC}"
        echo -e "${BLUE}  MAVLink messages: ${ATTACK_COUNTERS[mavlink_messages]:-0}${NC}"
        echo -e "${BLUE}  Rapid packet bursts: ${ATTACK_COUNTERS[rapid_packets]:-0}${NC}"
        
        echo -e "\n${YELLOW}📊 Source Analysis:${NC}"
        for ip in "${MAVLINK_IPS[@]}"; do
            local count=${ATTACK_COUNTERS["ip_$ip"]:-0}
            if [ "$count" -gt 0 ]; then
                echo -e "${BLUE}  $ip: $count packets${NC}"
            fi
        done
    else
        echo -e "${GREEN}✅ No security threats detected${NC}"
    fi
    
    echo -e "\n${CYAN}📁 Log files:${NC}"
    echo -e "${BLUE}  Alerts: $ALERT_LOG${NC}"
    echo -e "${BLUE}  Traffic: $TRAFFIC_LOG${NC}"
}

main() {
    print_defense_banner
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[!] Root privileges required for network monitoring${NC}"
        exit 1
    fi
    
    # 모니터링 기간 설정
    MONITOR_DURATION=${1:-60}
    
    # 신호 핸들러
    trap cleanup_monitoring SIGINT SIGTERM
    
    # 모니터링 시작
    setup_monitoring
    
    # 모니터링 활성화
    ATTACK_COUNTERS["monitoring_active"]=1
    
    # 각종 모니터링 시작
    monitor_real_mavlink_traffic
    monitor_service_health
    check_attack_indicators
    show_real_time_stats
    
    echo -e "${GREEN}[✓] Enhanced monitoring active - watching for attacks!${NC}"
    echo -e "${YELLOW}[*] Monitoring for $MONITOR_DURATION seconds...${NC}"
    echo -e "${BLUE}[*] Try running attacks now to see real-time detection${NC}"
    echo ""
    
    # 대기
    sleep "$MONITOR_DURATION"
    
    # 모니터링 비활성화
    ATTACK_COUNTERS["monitoring_active"]=0
    sleep 2
    
    # 최종 보고서
    generate_final_report
    
    # 정리
    cleanup_monitoring
    
    echo -e "\n${BOLD}${GREEN}[✓] Enhanced Defense Monitoring Completed${NC}"
}

main "$@"