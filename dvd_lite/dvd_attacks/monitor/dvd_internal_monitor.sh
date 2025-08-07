#!/bin/bash
# dvd_internal_monitor.sh - DVD 컨테이너 내부 상태 및 로그 실시간 모니터링
# Purpose: 공격 시 컨테이너 내부 변화 및 로그 추적

source "$(dirname "$0")/common/colors.sh"
source "$(dirname "$0")/common/utils.sh"

# 전역 변수
MONITOR_DURATION=120
LOG_DIR="/tmp/dvd_internal_logs"
CONTAINERS=("flight-controller" "companion-computer" "ground-control-station" "simulator")

# 각 컨테이너별 로그 파일
declare -A CONTAINER_LOGS
declare -A BASELINE_STATS
declare -A CURRENT_STATS

print_internal_banner() {
    clear
    echo -e "${BOLD}${GREEN}============================================${NC}"
    echo -e "${BOLD}${GREEN}   DVD Internal Container Monitor         ${NC}"
    echo -e "${BOLD}${GREEN}============================================${NC}"
    echo -e "${BLUE}Purpose: Monitor internal container changes${NC}"
    echo -e "${BLUE}Scope: Logs, processes, files, network${NC}"
    echo -e "${BLUE}Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo ""
}

setup_internal_monitoring() {
    echo -e "${YELLOW}[*] Setting up internal container monitoring...${NC}"
    
    # 로그 디렉토리 생성
    mkdir -p "$LOG_DIR"
    
    # 각 컨테이너별 로그 파일 설정
    for container in "${CONTAINERS[@]}"; do
        CONTAINER_LOGS["${container}_docker"]="$LOG_DIR/${container}_docker.log"
        CONTAINER_LOGS["${container}_internal"]="$LOG_DIR/${container}_internal.log"
        CONTAINER_LOGS["${container}_mavlink"]="$LOG_DIR/${container}_mavlink.log"
        CONTAINER_LOGS["${container}_changes"]="$LOG_DIR/${container}_changes.log"
        
        # 로그 파일 초기화
        echo "=== $container Internal Monitor Started at $(date) ===" > "${CONTAINER_LOGS[${container}_internal]}"
        echo "=== $container Docker Logs Started at $(date) ===" > "${CONTAINER_LOGS[${container}_docker]}"
        echo "=== $container MAVLink Activity Started at $(date) ===" > "${CONTAINER_LOGS[${container}_mavlink]}"
        echo "=== $container System Changes Started at $(date) ===" > "${CONTAINER_LOGS[${container}_changes]}"
    done
    
    # 베이스라인 수집
    collect_internal_baseline
    
    echo -e "${GREEN}[✓] Internal monitoring setup completed${NC}"
}

collect_internal_baseline() {
    echo -e "${CYAN}[*] Collecting internal baseline metrics...${NC}"
    
    for container in "${CONTAINERS[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            echo -e "${BLUE}=== Baseline for $container ===${NC}"
            
            # 프로세스 수
            local process_count=$(docker exec "$container" ps aux 2>/dev/null | wc -l)
            BASELINE_STATS["${container}_processes"]=$process_count
            
            # 네트워크 연결 수
            local connection_count=$(docker exec "$container" netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
            BASELINE_STATS["${container}_connections"]=$connection_count
            
            # 메모리 사용량
            local memory_usage=$(docker stats --no-stream --format "{{.MemUsage}}" "$container" 2>/dev/null | cut -d'/' -f1)
            BASELINE_STATS["${container}_memory"]="$memory_usage"
            
            # CPU 사용률
            local cpu_usage=$(docker stats --no-stream --format "{{.CPUPerc}}" "$container" 2>/dev/null | sed 's/%//')
            BASELINE_STATS["${container}_cpu"]="$cpu_usage"
            
            # 특정 서비스 상태
            case $container in
                "ground-control-station")
                    local mavproxy_count=$(docker exec "$container" ps aux 2>/dev/null | grep mavproxy | grep -v grep | wc -l)
                    BASELINE_STATS["${container}_mavproxy"]=$mavproxy_count
                    ;;
                "flight-controller")
                    local ardupilot_count=$(docker exec "$container" ps aux 2>/dev/null | grep -i ardupilot | wc -l)
                    BASELINE_STATS["${container}_ardupilot"]=$ardupilot_count
                    ;;
                "simulator")
                    local gazebo_count=$(docker exec "$container" ps aux 2>/dev/null | grep gazebo | grep -v grep | wc -l)
                    BASELINE_STATS["${container}_gazebo"]=$gazebo_count
                    ;;
            esac
            
            echo -e "${GREEN}  Processes: $process_count, Connections: $connection_count${NC}"
            echo -e "${GREEN}  Memory: $memory_usage, CPU: $cpu_usage%${NC}"
        fi
    done
    echo ""
}

monitor_docker_logs() {
    echo -e "${YELLOW}[*] Starting Docker logs monitoring...${NC}"
    
    for container in "${CONTAINERS[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            # Docker 로그 실시간 캡처
            timeout "$MONITOR_DURATION" docker logs -f --tail=20 "$container" 2>&1 | \
            while read line; do
                local timestamp=$(date '+%H:%M:%S')
                echo "[$timestamp] $line" >> "${CONTAINER_LOGS[${container}_docker]}"
                
                # 중요한 로그 실시간 출력
                if echo "$line" | grep -iE "(error|warning|mavlink|attack|fail|exception)" >/dev/null; then
                    echo -e "${RED}[$container] $timestamp: $line${NC}"
                fi
            done &
        fi
    done
}

monitor_internal_processes() {
    echo -e "${YELLOW}[*] Monitoring internal processes...${NC}"
    
    while [ ${CURRENT_STATS["monitoring_active"]:-1} -eq 1 ]; do
        for container in "${CONTAINERS[@]}"; do
            if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
                local timestamp=$(date '+%H:%M:%S')
                
                # 프로세스 변화 감지
                local current_processes=$(docker exec "$container" ps aux 2>/dev/null | wc -l)
                local baseline_processes=${BASELINE_STATS["${container}_processes"]:-0}
                
                if [ "$current_processes" -ne "$baseline_processes" ]; then
                    local change_msg="Process count changed: $baseline_processes -> $current_processes"
                    echo "[$timestamp] $change_msg" >> "${CONTAINER_LOGS[${container}_changes]}"
                    echo -e "${YELLOW}[$container] $change_msg${NC}"
                fi
                
                # 네트워크 연결 변화
                local current_connections=$(docker exec "$container" netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
                local baseline_connections=${BASELINE_STATS["${container}_connections"]:-0}
                
                if [ "$current_connections" -gt $((baseline_connections + 3)) ]; then
                    local change_msg="Network connections spike: $baseline_connections -> $current_connections"
                    echo "[$timestamp] $change_msg" >> "${CONTAINER_LOGS[${container}_changes]}"
                    echo -e "${RED}[$container] $change_msg${NC}"
                fi
                
                # 서비스별 특화 모니터링
                monitor_service_specific "$container" "$timestamp"
            fi
        done
        sleep 5
    done &
}

monitor_service_specific() {
    local container="$1"
    local timestamp="$2"
    
    case $container in
        "ground-control-station")
            # MAVProxy 상태 모니터링
            local current_mavproxy=$(docker exec "$container" ps aux 2>/dev/null | grep mavproxy | grep -v grep | wc -l)
            local baseline_mavproxy=${BASELINE_STATS["${container}_mavproxy"]:-0}
            
            if [ "$current_mavproxy" -ne "$baseline_mavproxy" ]; then
                local change_msg="MAVProxy process count changed: $baseline_mavproxy -> $current_mavproxy"
                echo "[$timestamp] $change_msg" >> "${CONTAINER_LOGS[${container}_changes]}"
                echo -e "${RED}[GCS] $change_msg${NC}"
            fi
            
            # MAVLink 포트 활동 모니터링
            local port_activity=$(docker exec "$container" netstat -an 2>/dev/null | grep 14550 | wc -l)
            if [ "$port_activity" -gt 0 ]; then
                echo "[$timestamp] MAVLink port 14550 activity detected" >> "${CONTAINER_LOGS[${container}_mavlink]}"
            fi
            ;;
            
        "companion-computer")
            # MAVLink Router 활동
            local router_activity=$(docker exec "$container" ps aux 2>/dev/null | grep -i mavlink | wc -l)
            echo "[$timestamp] MAVLink Router processes: $router_activity" >> "${CONTAINER_LOGS[${container}_mavlink]}"
            
            # 웹 서비스 상태 (포트 3000)
            local web_activity=$(docker exec "$container" netstat -an 2>/dev/null | grep 3000 | wc -l)
            if [ "$web_activity" -gt 0 ]; then
                echo "[$timestamp] Web service port 3000 active" >> "${CONTAINER_LOGS[${container}_internal]}"
            fi
            ;;
            
        "flight-controller")
            # ArduPilot SITL 프로세스
            local sitl_processes=$(docker exec "$container" ps aux 2>/dev/null | grep -i "sitl\|ardupilot" | wc -l)
            echo "[$timestamp] SITL/ArduPilot processes: $sitl_processes" >> "${CONTAINER_LOGS[${container}_internal]}"
            ;;
            
        "simulator")
            # Gazebo 시뮬레이터 상태
            local gazebo_cpu=$(docker exec "$container" ps -o pid,pcpu,comm 2>/dev/null | grep gazebo | head -1 | awk '{print $2}')
            echo "[$timestamp] Gazebo CPU usage: ${gazebo_cpu:-0}%" >> "${CONTAINER_LOGS[${container}_internal]}"
            
            # 웹 서버 상태 (포트 8000)
            local web_connections=$(docker exec "$container" netstat -an 2>/dev/null | grep 8000 | grep ESTABLISHED | wc -l)
            echo "[$timestamp] Web server connections: $web_connections" >> "${CONTAINER_LOGS[${container}_internal]}"
            ;;
    esac
}

monitor_mavlink_activity() {
    echo -e "${YELLOW}[*] Monitoring MAVLink protocol activity...${NC}"
    
    # MAVLink 메시지 패턴 감지
    timeout "$MONITOR_DURATION" tcpdump -i any -n port 14550 -A 2>/dev/null | \
    while read line; do
        local timestamp=$(date '+%H:%M:%S')
        
        # MAVLink 메시지 유형 감지
        if echo "$line" | grep -E "HEARTBEAT|ATTITUDE|GPS|BATTERY" >/dev/null; then
            local message_type=$(echo "$line" | grep -oE "HEARTBEAT|ATTITUDE|GPS|BATTERY" | head -1)
            
            # 각 컨테이너의 MAVLink 로그에 기록
            for container in "${CONTAINERS[@]}"; do
                if [[ "$container" == "ground-control-station" || "$container" == "companion-computer" ]]; then
                    echo "[$timestamp] MAVLink $message_type message detected" >> "${CONTAINER_LOGS[${container}_mavlink]}"
                fi
            done
            
            # 실시간 출력
            echo -e "${CYAN}[MAVLink] $timestamp: $message_type message${NC}"
        fi
        
        # 공격 패턴 의심 트래픽
        if echo "$line" | grep -E "10\.13\.0\.[2-4].*14550" >/dev/null; then
            echo "[$timestamp] Suspicious MAVLink traffic: $line" >> "${CONTAINER_LOGS[ground-control-station_mavlink]}"
            echo -e "${RED}[ALERT] Suspicious MAVLink traffic detected${NC}"
        fi
    done &
}

show_real_time_dashboard() {
    echo -e "${YELLOW}[*] Starting real-time dashboard...${NC}"
    
    while [ ${CURRENT_STATS["monitoring_active"]:-1} -eq 1 ]; do
        sleep 15
        
        # 화면 업데이트
        echo -e "\n${BOLD}${CYAN}=== Real-time Container Status ===${NC}"
        
        for container in "${CONTAINERS[@]}"; do
            if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
                # 현재 상태 수집
                local current_processes=$(docker exec "$container" ps aux 2>/dev/null | wc -l)
                local current_connections=$(docker exec "$container" netstat -an 2>/dev/null | grep ESTABLISHED | wc -l)
                local current_memory=$(docker stats --no-stream --format "{{.MemUsage}}" "$container" 2>/dev/null | cut -d'/' -f1)
                local current_cpu=$(docker stats --no-stream --format "{{.CPUPerc}}" "$container" 2>/dev/null)
                
                # 베이스라인과 비교
                local baseline_processes=${BASELINE_STATS["${container}_processes"]:-0}
                local baseline_connections=${BASELINE_STATS["${container}_connections"]:-0}
                
                local process_diff=$((current_processes - baseline_processes))
                local connection_diff=$((current_connections - baseline_connections))
                
                # 상태 표시
                echo -e "${BLUE}[$container]${NC}"
                echo -e "  Processes: $current_processes (${process_diff:+$process_diff})"
                echo -e "  Connections: $current_connections (${connection_diff:+$connection_diff})"
                echo -e "  Memory: $current_memory, CPU: $current_cpu"
                
                # 변화 감지 알림
                if [ "$process_diff" -ne 0 ] || [ "$connection_diff" -gt 2 ]; then
                    echo -e "${YELLOW}  ⚠️  Changes detected!${NC}"
                fi
            fi
        done
        
        # 최근 중요 로그 표시
        echo -e "\n${BOLD}${YELLOW}=== Recent Important Events ===${NC}"
        
        # 최근 변화 로그
        for container in "${CONTAINERS[@]}"; do
            local change_log="${CONTAINER_LOGS[${container}_changes]}"
            if [ -f "$change_log" ]; then
                local recent_changes=$(tail -3 "$change_log" 2>/dev/null | grep -v "Started at")
                if [ -n "$recent_changes" ]; then
                    echo -e "${RED}[$container Changes]${NC}"
                    echo "$recent_changes" | sed 's/^/  /'
                fi
            fi
        done
        
        # 최근 MAVLink 활동
        local mavlink_log="${CONTAINER_LOGS[ground-control-station_mavlink]}"
        if [ -f "$mavlink_log" ]; then
            local recent_mavlink=$(tail -2 "$mavlink_log" 2>/dev/null | grep -v "Started at")
            if [ -n "$recent_mavlink" ]; then
                echo -e "${CYAN}[MAVLink Activity]${NC}"
                echo "$recent_mavlink" | sed 's/^/  /'
            fi
        fi
    done &
}

generate_internal_report() {
    echo -e "${CYAN}[*] Generating internal monitoring report...${NC}"
    
    local report_file="$LOG_DIR/internal_monitoring_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
=== DVD Internal Container Monitoring Report ===
Generated: $(date)
Monitoring Duration: $MONITOR_DURATION seconds

=== Container Status Summary ===
EOF
    
    for container in "${CONTAINERS[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            echo "" >> "$report_file"
            echo "[$container]" >> "$report_file"
            
            # 베이스라인 vs 현재 비교
            local baseline_processes=${BASELINE_STATS["${container}_processes"]:-0}
            local current_processes=$(docker exec "$container" ps aux 2>/dev/null | wc -l)
            
            echo "  Processes: $baseline_processes -> $current_processes" >> "$report_file"
            
            # 변화 로그 요약
            local change_log="${CONTAINER_LOGS[${container}_changes]}"
            if [ -f "$change_log" ]; then
                local change_count=$(grep -c "changed" "$change_log" 2>/dev/null || echo 0)
                echo "  Changes detected: $change_count" >> "$report_file"
            fi
            
            # 로그 파일 위치
            echo "  Logs: ${CONTAINER_LOGS[${container}_docker]}" >> "$report_file"
            echo "  Changes: ${CONTAINER_LOGS[${container}_changes]}" >> "$report_file"
        fi
    done
    
    echo "" >> "$report_file"
    echo "=== Log File Locations ===" >> "$report_file"
    echo "Report Directory: $LOG_DIR" >> "$report_file"
    
    echo -e "${GREEN}[✓] Internal report generated: $report_file${NC}"
}

cleanup_internal_monitoring() {
    echo -e "${YELLOW}[*] Cleaning up internal monitoring...${NC}"
    
    CURRENT_STATS["monitoring_active"]=0
    
    # 백그라운드 프로세스 정리
    pkill -f "docker logs -f" 2>/dev/null
    pkill -f "tcpdump.*14550" 2>/dev/null
    
    echo -e "${GREEN}[✓] Internal monitoring cleanup completed${NC}"
}

main() {
    print_internal_banner
    
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[!] Root privileges required for network monitoring${NC}"
        exit 1
    fi
    
    # 모니터링 기간 설정
    MONITOR_DURATION=${1:-120}
    
    # 신호 핸들러
    trap cleanup_internal_monitoring SIGINT SIGTERM
    
    # 모니터링 시작
    setup_internal_monitoring
    
    # 모니터링 활성화
    CURRENT_STATS["monitoring_active"]=1
    
    # 각종 모니터링 시작
    monitor_docker_logs
    monitor_internal_processes
    monitor_mavlink_activity
    show_real_time_dashboard
    
    echo -e "${GREEN}[✓] Internal container monitoring active!${NC}"
    echo -e "${YELLOW}[*] Monitoring for $MONITOR_DURATION seconds...${NC}"
    echo -e "${BLUE}[*] Run attacks now to see internal changes${NC}"
    echo -e "${CYAN}[*] Logs being saved to: $LOG_DIR${NC}"
    echo ""
    
    # 대기
    sleep "$MONITOR_DURATION"
    
    # 모니터링 비활성화
    CURRENT_STATS["monitoring_active"]=0
    sleep 3
    
    # 보고서 생성
    generate_internal_report
    
    # 정리
    cleanup_internal_monitoring
    
    echo -e "\n${BOLD}${GREEN}[✓] Internal Container Monitoring Completed${NC}"
    echo -e "${YELLOW}[*] Check detailed logs in: $LOG_DIR${NC}"
    echo -e "${YELLOW}[*] Docker logs, process changes, and MAVLink activity captured${NC}"
}

main "$@"