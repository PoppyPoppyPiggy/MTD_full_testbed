#!/bin/bash

# =============================================================================
# DVD Attack Framework - Utility Functions Module
# =============================================================================
# 파일: dvd_lite/dvd_attacks/common/utils.sh
# 목적: 공격 스크립트용 유틸리티 함수들
# 작성자: MTD Testbed Team
# =============================================================================

# colors.sh 모듈 로드 확인
if [ -z "$RED" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/colors.sh"
fi

# =============================================================================
# 전역 변수 설정
# =============================================================================

# 기본 경로 설정
BASE_DIR="/home/kali/MTD/MTD_full_testbed"
LOG_BASE_DIR="$BASE_DIR/attack_logs"
OUTPUT_BASE_DIR="$BASE_DIR/attack_output"
TEMP_DIR="/tmp/dvd_attacks"
CONFIG_DIR="$BASE_DIR/configs"

# 로그 레벨 설정
LOG_LEVEL_DEBUG=0
LOG_LEVEL_INFO=1
LOG_LEVEL_WARNING=2
LOG_LEVEL_ERROR=3
CURRENT_LOG_LEVEL=$LOG_LEVEL_INFO

# 공격 상태 코드
ATTACK_SUCCESS=0
ATTACK_FAILED=1
ATTACK_PARTIAL=2
ATTACK_TIMEOUT=3

# 네트워크 설정
DEFAULT_TARGET_NETWORK="192.168.13.0/24"
DEFAULT_MAVLINK_PORT="14550"
DEFAULT_TELEMETRY_PORT="5760"
DEFAULT_VIDEO_PORT="5600"

# =============================================================================
# 로깅 함수들
# =============================================================================

# 로그 레벨 체크
should_log() {
    local level="$1"
    [ "$level" -ge "$CURRENT_LOG_LEVEL" ]
}

# 로그 메시지 포맷
format_log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local pid=$$
    echo "[$timestamp] [PID:$pid] [$level] $message"
}

# 디버그 로그
log_debug() {
    local message="$1"
    if should_log $LOG_LEVEL_DEBUG; then
        format_log_message "DEBUG" "$message" >> "$LOG_FILE"
        [ "$VERBOSE" = "true" ] && print_info "[DEBUG] $message"
    fi
}

# 정보 로그
log_info() {
    local message="$1"
    if should_log $LOG_LEVEL_INFO; then
        format_log_message "INFO" "$message" >> "$LOG_FILE"
        print_info "$message"
    fi
}

# 경고 로그
log_warning() {
    local message="$1"
    if should_log $LOG_LEVEL_WARNING; then
        format_log_message "WARNING" "$message" >> "$LOG_FILE"
        print_warning "$message"
    fi
}

# 오류 로그
log_error() {
    local message="$1"
    if should_log $LOG_LEVEL_ERROR; then
        format_log_message "ERROR" "$message" >> "$LOG_FILE"
        print_error "$message"
    fi
}

# 성공 로그
log_success() {
    local message="$1"
    format_log_message "SUCCESS" "$message" >> "$LOG_FILE"
    print_success "$message"
}

# =============================================================================
# 파일 및 디렉토리 관리 함수들
# =============================================================================

# 디렉토리 생성 및 확인
ensure_directory() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir" || {
            log_error "Failed to create directory: $dir"
            return 1
        }
        log_debug "Created directory: $dir"
    fi
    return 0
}

# 로그 디렉토리 초기화
init_log_directories() {
    local tactics=("reconnaissance" "protocol_tampering" "denial_of_service" "injection" "exfiltration" "firmware_attacks" "master_logs")
    
    for tactic in "${tactics[@]}"; do
        ensure_directory "$LOG_BASE_DIR/$tactic"
        ensure_directory "$OUTPUT_BASE_DIR/$tactic"
    done
    
    ensure_directory "$TEMP_DIR"
    return 0
}

# 임시 파일 생성
create_temp_file() {
    local prefix="$1"
    local suffix="$2"
    local temp_file="$TEMP_DIR/${prefix}_$(date +%s)_$$${suffix}"
    touch "$temp_file" || {
        log_error "Failed to create temp file: $temp_file"
        return 1
    }
    echo "$temp_file"
}

# 파일 크기 확인
get_file_size() {
    local file="$1"
    if [ -f "$file" ]; then
        stat -c%s "$file"
    else
        echo "0"
    fi
}

# 파일 백업
backup_file() {
    local file="$1"
    local backup_dir="$2"
    
    if [ -f "$file" ]; then
        local filename=$(basename "$file")
        local backup_path="$backup_dir/${filename}.backup.$(date +%s)"
        ensure_directory "$backup_dir"
        cp "$file" "$backup_path" && log_debug "Backup created: $backup_path"
    fi
}

# =============================================================================
# IOC (Indicators of Compromise) 관리 함수들
# =============================================================================

# IOC 파일 생성
create_ioc_file() {
    local attack_name="$1"
    local ioc_file="$TEMP_DIR/${attack_name}_iocs_$(date +%s).txt"
    
    cat > "$ioc_file" << EOF
# DVD Attack Framework - IOC Collection
# Attack: $attack_name
# Timestamp: $(date '+%Y-%m-%d %H:%M:%S')
# Format: TIMESTAMP:TYPE:VALUE:CONFIDENCE:DESCRIPTION
EOF
    
    echo "$ioc_file"
}

# IOC 추가
add_ioc() {
    local ioc_file="$1"
    local ioc_entry="$2"
    local timestamp=$(date +%s)
    
    if [ -n "$ioc_entry" ]; then
        echo "$timestamp:$ioc_entry" >> "$ioc_file"
        log_debug "IOC added: $ioc_entry"
    fi
}

# IOC 추가 (상세 정보)
add_detailed_ioc() {
    local ioc_file="$1"
    local ioc_type="$2"
    local ioc_value="$3"
    local confidence="$4"
    local description="$5"
    
    local timestamp=$(date +%s)
    local ioc_entry="$ioc_type:$ioc_value:$confidence:$description"
    echo "$timestamp:$ioc_entry" >> "$ioc_file"
    log_debug "Detailed IOC added: $ioc_entry"
}

# IOC 파일 처리
process_iocs() {
    local ioc_file="$1"
    local output_format="$2" # json, csv, xml
    
    if [ ! -f "$ioc_file" ]; then
        log_error "IOC file not found: $ioc_file"
        return 1
    fi
    
    local ioc_count=$(grep -v '^#' "$ioc_file" | wc -l)
    log_info "Processing $ioc_count IOCs from $ioc_file"
    
    case "$output_format" in
        "json")
            convert_iocs_to_json "$ioc_file"
            ;;
        "csv")
            convert_iocs_to_csv "$ioc_file"
            ;;
        *)
            log_warning "Unsupported IOC format: $output_format"
            ;;
    esac
}

# IOC를 JSON으로 변환
convert_iocs_to_json() {
    local ioc_file="$1"
    local json_file="${ioc_file%.*}.json"
    
    python3 << EOF
import json
import sys
from datetime import datetime

iocs = []
with open('$ioc_file', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            parts = line.split(':', 4)
            if len(parts) >= 2:
                ioc = {
                    'timestamp': parts[0],
                    'type': parts[1] if len(parts) > 1 else 'unknown',
                    'value': parts[2] if len(parts) > 2 else '',
                    'confidence': int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 50,
                    'description': parts[4] if len(parts) > 4 else ''
                }
                iocs.append(ioc)

with open('$json_file', 'w') as f:
    json.dump({'iocs': iocs, 'count': len(iocs)}, f, indent=2)

print('$json_file')
EOF
}

# =============================================================================
# JSON 결과 생성 함수들
# =============================================================================

# 공격 결과 JSON 생성
generate_attack_json() {
    local attack_name="$1"
    local status="$2"
    local ioc_file="$3"
    local additional_data="$4"
    
    local json_file="$OUTPUT_BASE_DIR/$(basename $(dirname $ioc_file))/${attack_name}_report_$(date +%s).json"
    ensure_directory "$(dirname "$json_file")"
    
    local ioc_count=0
    if [ -f "$ioc_file" ]; then
        ioc_count=$(grep -v '^#' "$ioc_file" | wc -l)
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - ${START_TIME:-$end_time}))
    
    cat > "$json_file" << EOF
{
  "attack_metadata": {
    "attack_name": "$attack_name",
    "status": "$status",
    "start_time": "${START_TIME:-$end_time}",
    "end_time": "$end_time",
    "duration_seconds": $duration,
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "framework_version": "1.0.0",
    "environment": "simulation"
  },
  "execution_info": {
    "script_path": "${BASH_SOURCE[1]:-unknown}",
    "working_directory": "$(pwd)",
    "user": "$(whoami)",
    "hostname": "$(hostname)",
    "pid": $$
  },
  "results": {
    "ioc_count": $ioc_count,
    "ioc_file": "$ioc_file",
    "log_file": "${LOG_FILE:-none}",
    "success": $([ "$status" = "success" ] && echo "true" || echo "false")
  }
EOF

    if [ -n "$additional_data" ]; then
        echo "  ,$additional_data" >> "$json_file"
    fi
    
    echo "}" >> "$json_file"
    
    log_info "Attack report generated: $json_file"
    echo "$json_file"
}

# =============================================================================
# 네트워크 유틸리티 함수들
# =============================================================================

# IP 주소 유효성 검사
is_valid_ip() {
    local ip="$1"
    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        IFS='.' read -ra ADDR <<< "$ip"
        for i in "${ADDR[@]}"; do
            if [ "$i" -gt 255 ]; then
                return 1
            fi
        done
        return 0
    fi
    return 1
}

# 포트 유효성 검사
is_valid_port() {
    local port="$1"
    if [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]; then
        return 0
    fi
    return 1
}

# 네트워크 인터페이스 확인
get_active_interface() {
    ip route | grep default | awk '{print $5}' | head -n1
}

# 기본 게이트웨이 확인
get_default_gateway() {
    ip route | grep default | awk '{print $3}' | head -n1
}

# 로컬 IP 주소 확인
get_local_ip() {
    local interface="${1:-$(get_active_interface)}"
    ip addr show "$interface" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1
}

# =============================================================================
# 시스템 정보 수집 함수들
# =============================================================================

# 시스템 아키텍처 확인
get_system_arch() {
    uname -m
}

# OS 정보 확인
get_os_info() {
    if [ -f /etc/os-release ]; then
        grep '^PRETTY_NAME=' /etc/os-release | cut -d'"' -f2
    else
        uname -s
    fi
}

# 메모리 사용량 확인
get_memory_usage() {
    free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2}'
}

# CPU 사용량 확인
get_cpu_usage() {
    top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}'
}

# 디스크 사용량 확인
get_disk_usage() {
    df -h / | awk 'NR==2{print $5}'
}

# =============================================================================
# 프로세스 관리 함수들
# =============================================================================

# 백그라운드 프로세스 시작
start_background_process() {
    local command="$1"
    local pid_file="$2"
    
    nohup $command > /dev/null 2>&1 &
    local pid=$!
    echo "$pid" > "$pid_file"
    log_debug "Started background process: $command (PID: $pid)"
    echo "$pid"
}

# 프로세스 종료
kill_process() {
    local pid="$1"
    local timeout="${2:-10}"
    
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        
        local count=0
        while kill -0 "$pid" 2>/dev/null && [ "$count" -lt "$timeout" ]; do
            sleep 1
            count=$((count + 1))
        done
        
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            log_warning "Force killed process: $pid"
        else
            log_info "Process terminated: $pid"
        fi
    fi
}

# PID 파일에서 프로세스 종료
kill_process_by_pid_file() {
    local pid_file="$1"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        kill_process "$pid"
        rm -f "$pid_file"
    fi
}

# =============================================================================
# 안전성 검사 함수들
# =============================================================================

# root 권한 확인
check_root_privileges() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script requires root privileges"
        print_error "Please run with sudo: sudo $0"
        return 1
    fi
    return 0
}

# 필수 도구 확인
check_required_tools() {
    local -a required_tools=("$@")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        print_error "Please install: ${missing_tools[*]}"
        return 1
    fi
    
    log_debug "All required tools available: ${required_tools[*]}"
    return 0
}

# 타겟 네트워크 접근성 확인
check_target_connectivity() {
    local target="$1"
    local port="$2"
    local timeout="${3:-5}"
    
    if [ -n "$port" ]; then
        timeout "$timeout" bash -c "echo >/dev/tcp/$target/$port" 2>/dev/null
    else
        ping -c 1 -W "$timeout" "$target" >/dev/null 2>&1
    fi
}

# =============================================================================
# 시뮬레이션 함수들
# =============================================================================

# 시뮬레이션 모드 확인
is_simulation_mode() {
    [ "${SIMULATION_MODE:-true}" = "true" ]
}

# 시뮬레이션 대기 (랜덤 시간)
simulation_wait() {
    local min_time="${1:-1}"
    local max_time="${2:-5}"
    
    if is_simulation_mode; then
        local wait_time=$((min_time + RANDOM % (max_time - min_time + 1)))
        log_debug "Simulation wait: ${wait_time}s"
        
        for ((i=0; i<wait_time; i++)); do
            printf "${GRAY}.${NC}"
            sleep 1
        done
        echo ""
    fi
}

# 시뮬레이션 성공/실패 결정
simulation_result() {
    local success_rate="${1:-80}" # 기본 80% 성공률
    
    if is_simulation_mode; then
        local random=$((RANDOM % 100))
        [ "$random" -lt "$success_rate" ]
    else
        # 실제 모드에서는 항상 true 반환 (실제 결과에 의존)
        return 0
    fi
}

# =============================================================================
# 설정 관리 함수들
# =============================================================================

# 설정 파일 읽기
load_config() {
    local config_file="$1"
    
    if [ -f "$config_file" ]; then
        source "$config_file"
        log_debug "Configuration loaded: $config_file"
    else
        log_warning "Configuration file not found: $config_file"
        return 1
    fi
}

# 기본 설정 생성
create_default_config() {
    local config_file="$1"
    ensure_directory "$(dirname "$config_file")"
    
    cat > "$config_file" << EOF
# DVD Attack Framework Configuration
# Generated on $(date)

# Target Configuration
TARGET_NETWORK="$DEFAULT_TARGET_NETWORK"
MAVLINK_PORT="$DEFAULT_MAVLINK_PORT"
TELEMETRY_PORT="$DEFAULT_TELEMETRY_PORT"
VIDEO_PORT="$DEFAULT_VIDEO_PORT"

# Attack Configuration
SIMULATION_MODE="true"
ATTACK_TIMEOUT="300"
MAX_RETRIES="3"

# Logging Configuration
LOG_LEVEL="$CURRENT_LOG_LEVEL"
VERBOSE="false"

# Output Configuration
GENERATE_JSON="true"
GENERATE_CSV="false"
CLEANUP_TEMP_FILES="true"
EOF
    
    log_info "Default configuration created: $config_file"
}

# =============================================================================
# 초기화 및 정리 함수들
# =============================================================================

# 스크립트 초기화
initialize_attack_script() {
    local script_name="$1"
    
    # 전역 변수 설정
    export START_TIME=$(date +%s)
    export SCRIPT_NAME="$script_name"
    export SCRIPT_PID=$$
    
    # 로그 디렉토리 초기화
    init_log_directories
    
    # 신호 핸들러 설정
    trap cleanup_and_exit EXIT INT TERM
    
    log_info "Attack script initialized: $script_name"
}

# 정리 및 종료
cleanup_and_exit() {
    local exit_code=${1:-0}
    
    log_info "Cleaning up attack script: $SCRIPT_NAME"
    
    # 임시 파일 정리 (옵션)
    if [ "${CLEANUP_TEMP_FILES:-true}" = "true" ]; then
        find "$TEMP_DIR" -name "*_$$_*" -type f -delete 2>/dev/null
    fi
    
    # 백그라운드 프로세스 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    log_info "Script execution completed with exit code: $exit_code"
    exit "$exit_code"
}

# 스크립트 마지막에 정리 함수 자동 등록
# trap cleanup_and_exit EXIT INT TERM