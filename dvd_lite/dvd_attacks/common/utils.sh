#!/bin/bash
# DVD Common Utils - 공통 유틸리티 함수

# 공통 변수
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACK_BASE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_BASE_DIR="/home/kali/MTD/MTD_full_testbed/attack_logs"
IOC_BASE_DIR="/tmp"
PID_DIR="/home/kali/MTD/MTD_full_testbed/pids"

# 필수 도구 확인
check_required_tools() {
    local tools=("$@")
    local missing_tools=()
    
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "다음 도구들이 필요합니다: ${missing_tools[*]}"
        log_info "설치 명령: sudo apt update && sudo apt install ${missing_tools[*]}"
        return 1
    fi
    
    return 0
}

# 네트워크 연결 확인
check_network_connectivity() {
    local target_ip="$1"
    local target_port="$2"
    
    if timeout 5 bash -c "echo >/dev/tcp/$target_ip/$target_port" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# IOC 파일 생성
create_ioc_file() {
    local attack_name="$1"
    local ioc_file="$IOC_BASE_DIR/${attack_name}_iocs.txt"
    
    echo "# IOC 파일: $attack_name" > "$ioc_file"
    echo "# 생성 시간: $(date)" >> "$ioc_file"
    echo "ATTACK_START:${attack_name}_$(date +%s)" >> "$ioc_file"
    
    echo "$ioc_file"
}

# IOC 추가
add_ioc() {
    local ioc_file="$1"
    local ioc_entry="$2"
    
    echo "$ioc_entry" >> "$ioc_file"
}

# 프로세스 PID 저장
save_pid() {
    local process_name="$1"
    local pid="$2"
    
    echo "$pid" > "$PID_DIR/${process_name}.pid"
}

# 프로세스 PID 로드
load_pid() {
    local process_name="$1"
    local pid_file="$PID_DIR/${process_name}.pid"
    
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    else
        echo ""
    fi
}

# 공격 결과 JSON 생성
generate_attack_json() {
    local attack_name="$1"
    local status="$2"
    local ioc_file="$3"
    local output_file="/home/kali/MTD/MTD_full_testbed/attack_output/${attack_name}_$(date +%Y%m%d_%H%M%S).json"
    
    local ioc_count=0
    if [ -f "$ioc_file" ]; then
        ioc_count=$(wc -l < "$ioc_file")
    fi
    
    cat > "$output_file" << EOF
{
    "attack_name": "$attack_name",
    "timestamp": "$(date -Iseconds)",
    "status": "$status",
    "ioc_file": "$ioc_file",
    "ioc_count": $ioc_count,
    "execution_time": "$(date +%s)",
    "target_info": {
        "type": "simulation",
        "environment": "testbed"
    }
}
EOF
    
    echo "$output_file"
}

# 시뮬레이션 대기 (랜덤 시간)
simulation_wait() {
    local min_seconds="${1:-1}"
    local max_seconds="${2:-5}"
    local wait_time=$((RANDOM % (max_seconds - min_seconds + 1) + min_seconds))
    
    sleep "$wait_time"
}

# DVD 서비스 확인
check_dvd_services() {
    local services_found=0
    
    # MAVLink 포트 확인
    if netstat -tuln 2>/dev/null | grep -q ":14550\|:5760"; then
        log_info "MAVLink 서비스 감지됨"
        services_found=$((services_found + 1))
    fi
    
    # HTTP 서비스 확인
    if netstat -tuln 2>/dev/null | grep -q ":8080\|:80"; then
        log_info "HTTP 서비스 감지됨"
        services_found=$((services_found + 1))
    fi
    
    # SSH 서비스 확인
    if netstat -tuln 2>/dev/null | grep -q ":22"; then
        log_info "SSH 서비스 감지됨"
        services_found=$((services_found + 1))
    fi
    
    return $services_found
}
