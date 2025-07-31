#!/bin/bash
# run_reconnaissance.sh - Reconnaissance Attack Suite Runner
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/run_reconnaissance.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_SUITE="Reconnaissance Attack Suite"
LOG_FILE="$(get_log_dir)/reconnaissance_suite.log"
SCRIPT_DIR="$(dirname "$0")"

# 실제 존재하는 공격 도구 목록
declare -A ATTACK_TOOLS=(
    [1]="wifi_discovery.sh:WiFi Network Discovery:무선 네트워크 탐지 및 분석"
    [2]="drone_discovery.sh:Drone Network Discovery:드론 네트워크 및 호스트 발견"
    [3]="gcs_discovery.sh:Ground Control Station Discovery:지상제어소 탐지 및 분석"
    [4]="protocol_fingerprinting.sh:Protocol Fingerprinting:MAVLink 프로토콜 핑거프린팅"
    [5]="packet_sniffing.sh:Packet Sniffing:MAVLink 패킷 스니핑 및 분석"
    [6]="companion_computer_detection.sh:Companion Computer Detection:동반 컴퓨터 탐지"
    [7]="mavlink_discovery.sh:MAVLink Service Discovery:MAVLink 서비스 발견 및 열거"
    [8]="camera_discovery.sh:Camera Stream Discovery:카메라 스트림 탐지 및 접근"
)

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║              정찰 공격 도구 모음                 ║"
    echo "║          Reconnaissance Attack Suite             ║"
    echo "║                                                  ║"
    echo "║         드론 MTD 테스트베드 보안 평가 도구       ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

show_main_menu() {
    echo -e "${BLUE}=== 사용 가능한 정찰 공격 도구 ===${NC}"
    echo ""
    
    for key in $(printf '%s\n' "${!ATTACK_TOOLS[@]}" | sort -n); do
        IFS=':' read -r script title description <<< "${ATTACK_TOOLS[$key]}"
        
        # 파일 존재 여부 확인
        local script_path="$SCRIPT_DIR/$script"
        local status_icon=""
        if [[ -f "$script_path" ]]; then
            status_icon="${GREEN}✓${NC}"
        else
            status_icon="${RED}✗${NC}"
        fi
        
        printf "${YELLOW}%2d)${NC} %s ${GREEN}%-35s${NC} - %s\n" "$key" "$status_icon" "$title" "$description"
    done
    
    echo ""
    echo -e "${YELLOW} 9)${NC} ${CYAN}Run Full Reconnaissance Suite${NC}     - 모든 정찰 공격 순차 실행"
    echo -e "${YELLOW}10)${NC} ${CYAN}Custom Attack Sequence${NC}            - 사용자 정의 공격 시퀀스"
    echo -e "${YELLOW}11)${NC} ${CYAN}Show Attack Reports${NC}                - 공격 보고서 조회"
    echo -e "${YELLOW}12)${NC} ${CYAN}Clean Environment${NC}                  - 환경 정리 및 초기화"
    echo -e "${YELLOW} 0)${NC} ${RED}Exit${NC}                                - 프로그램 종료"
    echo ""
}

check_script_availability() {
    local script_path="$1"
    local script_name="$(basename "$script_path")"
    
    if [[ ! -f "$script_path" ]]; then
        log_error "Attack script not found: $script_name"
        echo -e "${YELLOW}파일이 존재하지 않습니다: $script_path${NC}"
        return 1
    fi
    
    if [[ ! -x "$script_path" ]]; then
        log_info "Making script executable: $script_name"
        chmod +x "$script_path" 2>/dev/null || {
            log_error "Cannot make script executable: $script_name"
            return 1
        }
    fi
    
    return 0
}

execute_single_attack() {
    local attack_number="$1"
    
    if [[ -z "${ATTACK_TOOLS[$attack_number]}" ]]; then
        log_error "Invalid attack number: $attack_number"
        return 1
    fi
    
    IFS=':' read -r script title description <<< "${ATTACK_TOOLS[$attack_number]}"
    local script_path="$SCRIPT_DIR/$script"
    
    # 스크립트 가용성 확인
    if ! check_script_availability "$script_path"; then
        return 1
    fi
    
    log_info "Starting attack: $title"
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  실행 중: $title${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    
    local start_time=$(start_timer)
    
    # 공격 실행
    if bash "$script_path"; then
        local duration=$(end_timer "$start_time")
        log_success "Attack completed successfully in $duration"
        echo ""
        echo -e "${GREEN}[✓] $title - SUCCESS (Duration: $duration)${NC}"
        
        # 로그에 기록
        echo "$(date): $title - SUCCESS - Duration: $duration" >> "$LOG_FILE"
        return 0
    else
        local duration=$(end_timer "$start_time")
        log_error "Attack failed after $duration"
        echo ""
        echo -e "${RED}[✗] $title - FAILED (Duration: $duration)${NC}"
        
        # 로그에 기록
        echo "$(date): $title - FAILED - Duration: $duration" >> "$LOG_FILE"
        return 1
    fi
}

run_full_reconnaissance() {
    log_info "Starting full reconnaissance attack suite..."
    
    # 사용 가능한 공격만 필터링
    local available_attacks=()
    for key in $(printf '%s\n' "${!ATTACK_TOOLS[@]}" | sort -n); do
        IFS=':' read -r script title description <<< "${ATTACK_TOOLS[$key]}"
        local script_path="$SCRIPT_DIR/$script"
        
        if [[ -f "$script_path" ]]; then
            available_attacks+=("$key")
        else
            log_warning "Skipping unavailable attack: $title"
        fi
    done
    
    local total_attacks=${#available_attacks[@]}
    
    if [[ $total_attacks -eq 0 ]]; then
        log_error "No available attack scripts found"
        return 1
    fi
    
    local successful_attacks=0
    local failed_attacks=0
    local start_time=$(start_timer)
    
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           전체 정찰 공격 실행                    ║${NC}"
    echo -e "${CYAN}║         Full Reconnaissance Execution           ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BLUE}사용 가능한 공격 ($total_attacks개):${NC}"
    for key in "${available_attacks[@]}"; do
        IFS=':' read -r script title description <<< "${ATTACK_TOOLS[$key]}"
        echo -e "  $key. $title"
    done
    echo ""
    
    echo -e "${YELLOW}[?] 전체 정찰 공격을 시작하시겠습니까? (y/N)${NC}"
    read -n 1 confirm
    echo ""
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Full reconnaissance cancelled by user"
        return 0
    fi
    
    local attack_count=0
    for key in "${available_attacks[@]}"; do
        ((attack_count++))
        
        echo ""
        echo -e "${BLUE}╔═════════════════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║ Attack $attack_count/$total_attacks: ${ATTACK_TOOLS[$key]%%:*}${NC}"
        echo -e "${BLUE}╚═════════════════════════════════════════════════════════════════════════════════════╝${NC}"
        
        if execute_single_attack "$key"; then
            ((successful_attacks++))
        else
            ((failed_attacks++))
            
            echo ""
            echo -e "${YELLOW}[?] 공격이 실패했습니다. 계속 진행하시겠습니까? (Y/n)${NC}"
            read -n 1 continue_on_failure
            echo ""
            
            if [[ "$continue_on_failure" =~ ^[Nn]$ ]]; then
                log_warning "Full reconnaissance stopped due to failure"
                break
            fi
        fi
        
        # 다음 공격 전 잠시 대기
        if [[ $attack_count -lt $total_attacks ]]; then
            echo ""
            echo -e "${CYAN}다음 공격까지 5초 대기...${NC}"
            sleep 5
        fi
    done
    
    local total_duration=$(end_timer "$start_time")
    
    # 최종 결과 요약
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║              전체 공격 결과 요약                 ║${NC}"
    echo -e "${CYAN}║           Full Attack Results Summary            ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}총 실행 시간:${NC} $total_duration"
    echo -e "${GREEN}성공한 공격:${NC} $successful_attacks/$total_attacks"
    echo -e "${RED}실패한 공격:${NC} $failed_attacks/$total_attacks"
    
    if [[ $successful_attacks -eq $total_attacks ]]; then
        echo -e "${GREEN}[✓] 모든 정찰 공격이 성공적으로 완료되었습니다${NC}"
        log_success "Full reconnaissance suite completed successfully"
    else
        echo -e "${YELLOW}[!] 일부 공격이 실패했습니다. 로그를 확인하세요${NC}"
        log_warning "Some attacks in reconnaissance suite failed"
    fi
    
    echo ""
    echo -e "${CYAN}상세 로그:${NC} $LOG_FILE"
    echo -e "${CYAN}보고서 위치:${NC} $(get_report_dir)"
}

run_custom_sequence() {
    log_info "Starting custom attack sequence..."
    
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           사용자 정의 공격 시퀀스                ║${NC}"
    echo -e "${CYAN}║          Custom Attack Sequence                 ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BLUE}사용 가능한 공격:${NC}"
    local available_count=0
    for key in $(printf '%s\n' "${!ATTACK_TOOLS[@]}" | sort -n); do
        IFS=':' read -r script title description <<< "${ATTACK_TOOLS[$key]}"
        local script_path="$SCRIPT_DIR/$script"
        
        if [[ -f "$script_path" ]]; then
            echo -e "  ${GREEN}$key. $title${NC}"
            ((available_count++))
        else
            echo -e "  ${RED}$key. $title (사용 불가)${NC}"
        fi
    done
    echo ""
    
    if [[ $available_count -eq 0 ]]; then
        log_error "No available attack scripts found"
        return 1
    fi
    
    echo -e "${YELLOW}실행할 공격 번호를 순서대로 입력하세요 (공백으로 구분):${NC}"
    echo -e "${GRAY}예: 1 4 5${NC}"
    read -r sequence
    
    if [[ -z "$sequence" ]]; then
        log_warning "No attacks selected"
        return 1
    fi
    
    local attack_list=($sequence)
    local total_attacks=${#attack_list[@]}
    
    echo ""
    echo -e "${BLUE}선택된 공격 시퀀스:${NC}"
    local valid_attacks=0
    for i in "${!attack_list[@]}"; do
        local attack_num="${attack_list[$i]}"
        if [[ -n "${ATTACK_TOOLS[$attack_num]}" ]]; then
            IFS=':' read -r script title description <<< "${ATTACK_TOOLS[$attack_num]}"
            local script_path="$SCRIPT_DIR/$script"
            
            if [[ -f "$script_path" ]]; then
                echo -e "  $((i+1)). ${GREEN}$title${NC}"
                ((valid_attacks++))
            else
                echo -e "  $((i+1)). ${RED}$title (파일 없음)${NC}"
            fi
        else
            echo -e "  $((i+1)). ${RED}Invalid attack: $attack_num${NC}"
        fi
    done
    
    if [[ $valid_attacks -eq 0 ]]; then
        log_error "No valid attacks in sequence"
        return 1
    fi
    
    echo ""
    echo -e "${YELLOW}[?] 이 시퀀스를 실행하시겠습니까? (y/N)${NC}"
    read -n 1 confirm
    echo ""
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Custom sequence cancelled by user"
        return 0
    fi
    
    local successful_attacks=0
    local failed_attacks=0
    local start_time=$(start_timer)
    
    for i in "${!attack_list[@]}"; do
        local attack_num="${attack_list[$i]}"
        
        # 유효성 검사
        if [[ -z "${ATTACK_TOOLS[$attack_num]}" ]]; then
            echo -e "${RED}[!] Skipping invalid attack number: $attack_num${NC}"
            continue
        fi
        
        IFS=':' read -r script title description <<< "${ATTACK_TOOLS[$attack_num]}"
        local script_path="$SCRIPT_DIR/$script"
        
        if [[ ! -f "$script_path" ]]; then
            echo -e "${RED}[!] Skipping unavailable attack: $title${NC}"
            continue
        fi
        
        echo ""
        echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║ Custom Attack $((i+1))/$total_attacks: $title${NC}"
        echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════════════════════╝${NC}"
        
        if execute_single_attack "$attack_num"; then
            ((successful_attacks++))
        else
            ((failed_attacks++))
        fi
        
        # 다음 공격 전 대기 (마지막 공격이 아닌 경우)
        if [[ $((i+1)) -lt $total_attacks ]]; then
            echo ""
            echo -e "${CYAN}다음 공격까지 3초 대기...${NC}"
            sleep 3
        fi
    done
    
    local total_duration=$(end_timer "$start_time")
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║            사용자 정의 공격 결과                 ║${NC}"
    echo -e "${CYAN}║           Custom Attack Results                  ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}총 실행 시간:${NC} $total_duration"
    echo -e "${GREEN}성공한 공격:${NC} $successful_attacks/$valid_attacks"
    echo -e "${RED}실패한 공격:${NC} $failed_attacks/$valid_attacks"
}

show_attack_reports() {
    log_info "Showing attack reports..."
    
    local report_dir="$(get_report_dir)"
    local log_dir="$(get_log_dir)"
    
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                공격 보고서 조회                  ║${NC}"
    echo -e "${CYAN}║              Attack Reports View                 ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BLUE}보고서 디렉토리:${NC} $report_dir"
    echo -e "${BLUE}로그 디렉토리:${NC} $log_dir"
    echo ""
    
    # 디렉토리 존재 확인
    if [[ ! -d "$report_dir" ]]; then
        mkdir -p "$report_dir"
        echo -e "${YELLOW}보고서 디렉토리가 생성되었습니다.${NC}"
    fi
    
    if [[ ! -d "$log_dir" ]]; then
        mkdir -p "$log_dir"
        echo -e "${YELLOW}로그 디렉토리가 생성되었습니다.${NC}"
    fi
    
    # 최근 보고서 파일들 표시
    echo -e "${YELLOW}최근 보고서 파일:${NC}"
    local report_files=$(find "$report_dir" "$log_dir" -name "*report*.txt" -type f -mtime -7 2>/dev/null | head -10)
    
    if [[ -n "$report_files" ]]; then
        echo "$report_files" | while read -r file; do
            local file_date=$(stat -c %y "$file" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1)
            local file_size=$(stat -c %s "$file" 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "unknown")
            echo -e "  └─ $(basename "$file") (${file_date}, ${file_size})"
        done
    else
        echo -e "  └─ ${GRAY}보고서 파일이 없습니다.${NC}"
    fi
    
    echo ""
    echo -e "${YELLOW}최근 로그 파일:${NC}"
    local log_files=$(find "$log_dir" -name "*.log" -type f -mtime -7 2>/dev/null | head -10)
    
    if [[ -n "$log_files" ]]; then
        echo "$log_files" | while read -r file; do
            local file_date=$(stat -c %y "$file" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1)
            local file_size=$(stat -c %s "$file" 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "unknown")
            echo -e "  └─ $(basename "$file") (${file_date}, ${file_size})"
        done
    else
        echo -e "  └─ ${GRAY}로그 파일이 없습니다.${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}명령어 예시:${NC}"
    echo -e "  보고서 보기: ${GRAY}ls -la $report_dir/${NC}"
    echo -e "  로그 보기:   ${GRAY}tail -f $log_dir/*.log${NC}"
    echo -e "  전체 로그:   ${GRAY}cat $LOG_FILE${NC}"
}

clean_environment() {
    log_info "Cleaning attack environment..."
    
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                환경 정리                         ║${NC}"
    echo -e "${CYAN}║            Environment Cleanup                   ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}[?] 다음 항목들이 정리됩니다:${NC}"
    echo "  - 임시 파일 및 캐시 (/tmp/*_attack_*, /tmp/*_scan_*)"
    echo "  - 실행 중인 공격 프로세스 (airodump-ng, aireplay-ng, tshark)"
    echo "  - 네트워크 인터페이스 복구"
    echo "  - 오래된 로그 파일 정리 (7일 이상)"
    echo ""
    echo -e "${YELLOW}계속하시겠습니까? (y/N)${NC}"
    read -n 1 confirm
    echo ""
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Environment cleanup cancelled"
        return 0
    fi
    
    # 환경 정리 실행
    echo -e "${BLUE}정리 중...${NC}"
    
    # 임시 파일 정리
    find /tmp -name "*_attack_*" -type f -mtime +0 -delete 2>/dev/null && echo "  ✓ 공격 임시 파일 정리"
    find /tmp -name "*_scan_*" -type f -mtime +0 -delete 2>/dev/null && echo "  ✓ 스캔 임시 파일 정리"
    find /tmp -name "*_capture_*" -type f -mtime +0 -delete 2>/dev/null && echo "  ✓ 캡처 임시 파일 정리"
    
    # 프로세스 정리
    pkill -f "airodump-ng" 2>/dev/null && echo "  ✓ airodump-ng 프로세스 종료"
    pkill -f "aireplay-ng" 2>/dev/null && echo "  ✓ aireplay-ng 프로세스 종료"
    pkill -f "tshark" 2>/dev/null && echo "  ✓ tshark 프로세스 종료"
    
    # 네트워크 인터페이스 복구
    local wifi_interface=$(iwconfig 2>/dev/null | awk '/IEEE 802.11/ {print $1; exit}')
    if [[ -n "$wifi_interface" ]]; then
        sudo iwconfig "$wifi_interface" mode managed 2>/dev/null && echo "  ✓ WiFi 인터페이스 복구"
        sudo systemctl restart NetworkManager 2>/dev/null && echo "  ✓ NetworkManager 재시작"
    fi
    
    # 로그 파일 압축 (선택적)
    local log_dir="$(get_log_dir)"
    if [[ -d "$log_dir" ]]; then
        echo ""
        echo -e "${YELLOW}[?] 로그 파일을 압축하시겠습니까? (y/N)${NC}"
        read -n 1 compress_logs
        echo ""
        
        if [[ "$compress_logs" =~ ^[Yy]$ ]]; then
            local archive_name="reconnaissance_logs_$(date +%Y%m%d_%H%M%S).tar.gz"
            tar -czf "$log_dir/$archive_name" -C "$log_dir" --exclude="*.tar.gz" . 2>/dev/null
            if [[ $? -eq 0 ]]; then
                log_success "Logs compressed to: $archive_name"
            else
                log_warning "Failed to compress logs"
            fi
        fi
    fi
    
    log_success "Environment cleanup completed"
}

main() {
    print_banner
    
    # 초기 설정
    log_info "Initializing reconnaissance attack suite..."
    
    # 로그 파일 초기화
    echo "Session started: $(date)" >> "$LOG_FILE"
    echo "User: $(whoami)" >> "$LOG_FILE" 
    echo "System: $(uname -a)" >> "$LOG_FILE"
    echo "Working Directory: $(pwd)" >> "$LOG_FILE"
    echo "Available Scripts:" >> "$LOG_FILE"
    
    # 사용 가능한 스크립트 체크 및 로그 기록
    for key in $(printf '%s\n' "${!ATTACK_TOOLS[@]}" | sort -n); do
        IFS=':' read -r script title description <<< "${ATTACK_TOOLS[$key]}"
        local script_path="$SCRIPT_DIR/$script"
        if [[ -f "$script_path" ]]; then
            echo "  ✓ $script" >> "$LOG_FILE"
        else
            echo "  ✗ $script (missing)" >> "$LOG_FILE"
        fi
    done
    echo "================================" >> "$LOG_FILE"
    
    while true; do
        show_main_menu
        echo -n "선택하세요 [0-12]: "
        read -r choice
        echo ""
        
        case "$choice" in
            [1-8])
                execute_single_attack "$choice"
                ;;
            9)
                run_full_reconnaissance
                ;;
            10)
                run_custom_sequence
                ;;
            11)
                show_attack_reports
                ;;
            12)
                clean_environment
                ;;
            0)
                log_info "Exiting reconnaissance attack suite..."
                echo "Session ended: $(date)" >> "$LOG_FILE"
                echo -e "${GREEN}공격 도구를 안전하게 종료합니다.${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}잘못된 선택입니다. 0-12 사이의 숫자를 입력하세요.${NC}"
                ;;
        esac
        
        echo ""
        echo -e "${GRAY}계속하려면 Enter를 누르세요...${NC}"
        read -r
        clear
    done
}

# Signal handlers
trap 'echo -e "\n${RED}Suite interrupted${NC}"; clean_environment; exit 1' INT TERM

# 스크립트 실행 권한 확인
if [[ ! -x "$0" ]]; then
    chmod +x "$0" 2>/dev/null
fi

# 공통 유틸리티 파일 존재 여부 확인
if [[ ! -f "$(dirname "$0")/../common/colors.sh" ]] || [[ ! -f "$(dirname "$0")/../common/utils.sh" ]]; then
    echo -e "\033[1;31m[ERROR]\033[0m Required common files not found!"
    echo "Please ensure the following files exist:"
    echo "  - $(dirname "$0")/../common/colors.sh"
    echo "  - $(dirname "$0")/../common/utils.sh"
    exit 1
fi

# 메인 함수 실행
main "$@"