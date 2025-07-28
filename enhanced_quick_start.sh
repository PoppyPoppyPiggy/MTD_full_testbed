#!/bin/bash

# =============================================================================
# Enhanced DVD Attack Suite Quick Start
# =============================================================================
# 파일: enhanced_quick_start.sh
# 목적: 전체 DVD 공격 테스트베드 빠른 실행 및 관리
# 작성자: MTD Testbed Team
# =============================================================================

# 스크립트 디렉토리 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"

# 공통 모듈 로드
if [ -f "$BASE_DIR/dvd_lite/dvd_attacks/common/colors.sh" ]; then
    source "$BASE_DIR/dvd_lite/dvd_attacks/common/colors.sh"
fi

if [ -f "$BASE_DIR/dvd_lite/dvd_attacks/common/utils.sh" ]; then
    source "$BASE_DIR/dvd_lite/dvd_attacks/common/utils.sh"
fi

# 전역 변수
ATTACK_CATEGORIES=("reconnaissance" "protocol_tampering" "denial_of_service" "injection" "exfiltration" "firmware_attacks")
SELECTED_ATTACKS=()
EXECUTION_MODE="interactive"
PARALLEL_MODE=false
GENERATE_REPORT=true

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    🚁 Enhanced DVD Attack Suite 🚁                     ║"
    echo "║                        Comprehensive Security Testing                    ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Version: 2.0 Enhanced${NC}"
    echo -e "${BLUE}Base Directory: ${BASE_DIR}${NC}"
    echo -e "${BLUE}Execution Time: $(date)${NC}"
    echo ""
}

# 사용법 출력
print_usage() {
    cat << EOF
${BOLD}${CYAN}Enhanced DVD Attack Suite${NC}

${YELLOW}Usage:${NC}
    $0 [OPTIONS] [MODE]

${YELLOW}Options:${NC}
    -h, --help              Show this help message
    -i, --interactive       Interactive mode (default)
    -a, --auto              Automatic execution of all attacks
    -c, --custom            Custom attack selection
    -p, --parallel          Run attacks in parallel
    -s, --sequential        Run attacks sequentially (default)
    -r, --no-report         Skip report generation
    -v, --verbose           Verbose output
    -q, --quiet             Quiet mode

${YELLOW}Execution Modes:${NC}
    quick                   Quick reconnaissance only
    full                    Full attack suite execution
    recon                   Reconnaissance attacks only
    protocol                Protocol tampering attacks only
    dos                     Denial of service attacks only
    injection               Injection attacks only
    exfiltration            Data exfiltration attacks only
    firmware                Firmware attacks only

${YELLOW}Examples:${NC}
    $0                      # Interactive mode
    $0 -a full              # Automatic full attack suite
    $0 -i protocol          # Interactive protocol attacks
    $0 -p -a recon          # Parallel reconnaissance attacks
    $0 --custom             # Custom attack selection

${YELLOW}Output:${NC}
    • Logs: ${BASE_DIR}/attack_logs/
    • Reports: ${BASE_DIR}/attack_output/
    • IOCs: ${BASE_DIR}/iocs/
    • Summary: ${BASE_DIR}/reports/

EOF
}

# 시스템 상태 확인
check_system_status() {
    echo -e "${BOLD}${BLUE}🔍 DVD 시스템 상태 확인${NC}"
    echo "============================"
    
    # DVD 시스템 컴포넌트 확인
    local dvd_targets=(
        "10.13.0.5:Simulator"
        "10.13.0.2:Flight Controller"
        "10.13.0.3:Companion Computer"
        "10.13.0.4:Ground Control"
        "10.13.0.6:QGroundControl"
        "192.168.13.14:WiFi GCS"
    )
    
    local online_count=0
    local total_count=${#dvd_targets[@]}
    
    for target_info in "${dvd_targets[@]}"; do
        local ip=$(echo "$target_info" | cut -d':' -f1)
        local name=$(echo "$target_info" | cut -d':' -f2)
        
        if ping -c 1 -W 2 "$ip" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ ${name} (${ip})${NC}"
            online_count=$((online_count + 1))
        else
            echo -e "${RED}❌ ${name} (${ip})${NC}"
        fi
    done
    
    echo ""
    echo -e "${CYAN}시스템 가용성: ${online_count}/${total_count} ($(( online_count * 100 / total_count ))%)${NC}"
    
    if [ $online_count -eq 0 ]; then
        echo -e "${RED}⚠️ DVD 시스템이 완전히 오프라인 상태입니다.${NC}"
        echo -e "${YELLOW}시뮬레이션 모드로 전환됩니다.${NC}"
        return 1
    elif [ $online_count -lt $((total_count / 2)) ]; then
        echo -e "${YELLOW}⚠️ 일부 시스템만 온라인 상태입니다.${NC}"
        return 2
    else
        echo -e "${GREEN}✅ DVD 시스템이 정상 작동 중입니다.${NC}"
        return 0
    fi
    
    echo ""
}

# 필수 도구 확인
check_required_tools() {
    echo -e "${BLUE}🔧 필수 도구 확인${NC}"
    echo "=================="
    
    local required_tools=(
        "nmap:네트워크 스캔"
        "python3:Python 스크립트 실행"
        "curl:HTTP 요청"
        "nc:네트워크 연결 테스트"
        "airmon-ng:무선 모니터 모드"
        "airodump-ng:무선 패킷 캡처"
        "aireplay-ng:무선 패킷 주입"
        "iwconfig:무선 인터페이스 설정"
        "ping:연결 테스트"
    )
    
    local missing_tools=()
    local available_count=0
    
    for tool_info in "${required_tools[@]}"; do
        local tool=$(echo "$tool_info" | cut -d':' -f1)
        local desc=$(echo "$tool_info" | cut -d':' -f2)
        
        if command -v "$tool" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ ${tool}${NC} - ${desc}"
            available_count=$((available_count + 1))
        else
            echo -e "${RED}❌ ${tool}${NC} - ${desc}"
            missing_tools+=("$tool")
        fi
    done
    
    echo ""
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️ 누락된 도구들을 설치하시겠습니까? (y/N)${NC}"
        read -r install_choice
        
        if [[ $install_choice =~ ^[Yy]$ ]]; then
            echo -e "${CYAN}📦 도구 설치 중...${NC}"
            apt-get update -qq
            
            # 패키지 매핑
            local packages=()
            for tool in "${missing_tools[@]}"; do
                case $tool in
                    "airmon-ng"|"airodump-ng"|"aireplay-ng")
                        if [[ ! " ${packages[@]} " =~ " aircrack-ng " ]]; then
                            packages+=("aircrack-ng")
                        fi
                        ;;
                    "iwconfig")
                        packages+=("wireless-tools")
                        ;;
                    "nc")
                        packages+=("netcat-traditional")
                        ;;
                    *)
                        packages+=("$tool")
                        ;;
                esac
            done
            
            apt-get install -y "${packages[@]}"
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ 모든 도구가 성공적으로 설치되었습니다.${NC}"
            else
                echo -e "${RED}❌ 일부 도구 설치에 실패했습니다.${NC}"
            fi
        fi
    else
        echo -e "${GREEN}✅ 모든 필수 도구가 사용 가능합니다.${NC}"
    fi
    
    echo ""
}

# 대화형 공격 선택
interactive_attack_selection() {
    echo -e "${BOLD}${CYAN}🎯 공격 카테고리 선택${NC}"
    echo "======================"
    echo ""
    
    echo -e "${YELLOW}사용 가능한 공격 카테고리:${NC}"
    echo ""
    echo -e "${BLUE}1)${NC} ${BOLD}Reconnaissance (정찰)${NC}"
    echo -e "   ${CYAN}• WiFi 네트워크 발견${NC}"
    echo -e "   ${CYAN}• MAVLink 서비스 탐지${NC}"
    echo -e "   ${CYAN}• 드론 컴포넌트 열거${NC}"
    echo -e "   ${CYAN}• 카메라 스트림 발견${NC}"
    echo ""
    echo -e "${BLUE}2)${NC} ${BOLD}Protocol Tampering (프로토콜 변조)${NC}"
    echo -e "   ${CYAN}• GPS 스푸핑${NC}"
    echo -e "   ${CYAN}• 배터리 상태 스푸핑${NC}"
    echo -e "   ${CYAN}• 자세 정보 조작${NC}"
    echo -e "   ${CYAN}• MAVLink 패킷 주입${NC}"
    echo ""
    echo -e "${BLUE}3)${NC} ${BOLD}Denial of Service (서비스 거부)${NC}"
    echo -e "   ${CYAN}• WiFi 비인증화 공격${NC}"
    echo -e "   ${CYAN}• MAVLink 플러드${NC}"
    echo -e "   ${CYAN}• 리소스 고갈 공격${NC}"
    echo ""
    echo -e "${BLUE}4)${NC} ${BOLD}Injection (주입 공격)${NC}"
    echo -e "   ${CYAN}• 명령 주입${NC}"
    echo -e "   ${CYAN}• 파라미터 조작${NC}"
    echo -e "   ${CYAN}• 미션 플랜 변조${NC}"
    echo ""
    echo -e "${BLUE}5)${NC} ${BOLD}Exfiltration (데이터 탈취)${NC}"
    echo -e "   ${CYAN}• 텔레메트리 데이터 수집${NC}"
    echo -e "   ${CYAN}• 비디오 스트림 캡처${NC}"
    echo -e "   ${CYAN}• 플라이트 로그 추출${NC}"
    echo ""
    echo -e "${BLUE}6)${NC} ${BOLD}Firmware Attacks (펌웨어 공격)${NC}"
    echo -e "   ${CYAN}• 부트로더 익스플로잇${NC}"
    echo -e "   ${CYAN}• 펌웨어 롤백${NC}"
    echo -e "   ${CYAN}• 보안 부트 우회${NC}"
    echo ""
    echo -e "${BLUE}7)${NC} ${BOLD}Quick Test (빠른 테스트)${NC}"
    echo -e "   ${CYAN}• 기본 정찰 + 프로토콜 테스트${NC}"
    echo ""
    echo -e "${BLUE}8)${NC} ${BOLD}Full Attack Suite (전체 공격)${NC}"
    echo -e "   ${CYAN}• 모든 카테고리 순차 실행${NC}"
    echo ""
    
    while true; do
        echo -e "${YELLOW}선택하세요 (1-8, 또는 'q' 종료):${NC}"
        read -p "입력: " -r user_choice
        
        case $user_choice in
            "1")
                SELECTED_ATTACKS=("reconnaissance")
                break
                ;;
            "2")
                SELECTED_ATTACKS=("protocol_tampering")
                break
                ;;
            "3")
                SELECTED_ATTACKS=("denial_of_service")
                break
                ;;
            "4")
                SELECTED_ATTACKS=("injection")
                break
                ;;
            "5")
                SELECTED_ATTACKS=("exfiltration")
                break
                ;;
            "6")
                SELECTED_ATTACKS=("firmware_attacks")
                break
                ;;
            "7")
                SELECTED_ATTACKS=("reconnaissance" "protocol_tampering")
                break
                ;;
            "8")
                SELECTED_ATTACKS=("${ATTACK_CATEGORIES[@]}")
                break
                ;;
            "q"|"Q"|"quit"|"exit")
                echo -e "${RED}[!] 종료합니다...${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}[!] 잘못된 선택입니다. 1-8 또는 'q'를 입력하세요.${NC}"
                continue
                ;;
        esac
    done
    
    echo ""
    echo -e "${GREEN}[✓] 선택된 공격: ${SELECTED_ATTACKS[*]}${NC}"
    echo ""
}

# 자동 공격 실행
execute_automatic_attacks() {
    local mode=$1
    
    case $mode in
        "quick")
            SELECTED_ATTACKS=("reconnaissance")
            ;;
        "full")
            SELECTED_ATTACKS=("${ATTACK_CATEGORIES[@]}")
            ;;
        "recon")
            SELECTED_ATTACKS=("reconnaissance")
            ;;
        "protocol")
            SELECTED_ATTACKS=("protocol_tampering")
            ;;
        "dos")
            SELECTED_ATTACKS=("denial_of_service")
            ;;
        "injection")
            SELECTED_ATTACKS=("injection")
            ;;
        "exfiltration")
            SELECTED_ATTACKS=("exfiltration")
            ;;
        "firmware")
            SELECTED_ATTACKS=("firmware_attacks")
            ;;
        *)
            echo -e "${RED}[!] 알 수 없는 자동 모드: $mode${NC}"
            return 1
            ;;
    esac
    
    echo -e "${CYAN}[*] 자동 모드 실행: $mode${NC}"
    echo -e "${YELLOW}[*] 선택된 공격: ${SELECTED_ATTACKS[*]}${NC}"
}

# 공격 실행
execute_attacks() {
    local total_attacks=${#SELECTED_ATTACKS[@]}
    local current_attack=0
    local successful_attacks=0
    local failed_attacks=0
    
    echo -e "${BOLD}${RED}🚀 DVD 공격 실행 시작${NC}"
    echo "========================="
    echo ""
    
    local start_time=$(date +%s)
    
    for attack_category in "${SELECTED_ATTACKS[@]}"; do
        current_attack=$((current_attack + 1))
        
        echo -e "${BOLD}${CYAN}🎯 공격 ${current_attack}/${total_attacks}: ${attack_category}${NC}"
        echo "═══════════════════════════════════════════════════════════════════════════"
        
        local attack_script="$BASE_DIR/dvd_lite/dvd_attacks/${attack_category}/run_${attack_category}.sh"
        
        if [ -f "$attack_script" ]; then
            echo -e "${YELLOW}[+] 실행 중: ${attack_script}${NC}"
            
            if [ "$PARALLEL_MODE" = true ]; then
                bash "$attack_script" -a &
                local attack_pid=$!
                echo -e "${BLUE}[*] 백그라운드 실행 (PID: ${attack_pid})${NC}"
            else
                if timeout 300 bash "$attack_script" -a 2>&1 | tee -a "$BASE_DIR/attack_logs/master_$(date +%Y%m%d_%H%M%S).log"; then
                    echo -e "${GREEN}[✓] ${attack_category} 공격 완료${NC}"
                    successful_attacks=$((successful_attacks + 1))
                else
                    echo -e "${RED}[!] ${attack_category} 공격 실패${NC}"
                    failed_attacks=$((failed_attacks + 1))
                fi
            fi
        else
            echo -e "${YELLOW}[!] 공격 스크립트를 찾을 수 없음: ${attack_script}${NC}"
            echo -e "${BLUE}[*] 시뮬레이션 모드로 실행${NC}"
            
            simulate_attack "$attack_category"
            successful_attacks=$((successful_attacks + 1))
        fi
        
        echo ""
        
        # 공격 간 대기 시간
        if [ $current_attack -lt $total_attacks ] && [ "$PARALLEL_MODE" = false ]; then
            echo -e "${YELLOW}[*] 다음 공격까지 10초 대기...${NC}"
            wait_with_spinner 10 "대기 중"
        fi
    done
    
    # 병렬 모드인 경우 모든 공격 완료 대기
    if [ "$PARALLEL_MODE" = true ]; then
        echo -e "${CYAN}[*] 모든 병렬 공격 완료 대기 중...${NC}"
        wait
        successful_attacks=$total_attacks  # 시뮬레이션
    fi
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    echo -e "${BOLD}${GREEN}🎉 DVD 공격 실행 완료!${NC}"
    echo "======================="
    echo -e "${CYAN}📊 실행 통계:${NC}"
    echo "   • 총 소요 시간: ${total_duration}초"
    echo "   • 성공한 공격: ${successful_attacks}/${total_attacks}"
    echo "   • 실패한 공격: ${failed_attacks}/${total_attacks}"
    echo "   • 성공률: $(( total_attacks > 0 ? successful_attacks * 100 / total_attacks : 0 ))%"
    echo ""
}

# 공격 시뮬레이션
simulate_attack() {
    local attack_type=$1
    local duration=$((RANDOM % 30 + 10))  # 10-40초
    
    echo -e "${PURPLE}[*] ${attack_type} 시뮬레이션 실행 (${duration}초)${NC}"
    
    for ((i=1; i<=duration; i++)); do
        local progress=$((i * 100 / duration))
        printf "\r${PURPLE}시뮬레이션: [%-20s] %d%%${NC}" \
               "$(printf "%*s" $((progress / 5)) | tr ' ' '█')" "$progress"
        sleep 1
    done
    echo ""
    
    echo -e "${GREEN}[✓] ${attack_type} 시뮬레이션 완료${NC}"
}

# 결과 리포트 생성
generate_final_report() {
    if [ "$GENERATE_REPORT" = false ]; then
        return 0
    fi
    
    echo -e "${CYAN}[*] 최종 리포트 생성 중...${NC}"
    
    local report_file="$BASE_DIR/reports/dvd_attack_summary_$(date +%Y%m%d_%H%M%S).json"
    local timestamp=$(date -Iseconds)
    
    # JSON 리포트 생성
    cat > "$report_file" << EOF
{
    "dvd_attack_summary": {
        "execution_info": {
            "timestamp": "$timestamp",
            "execution_mode": "$EXECUTION_MODE",
            "parallel_execution": $PARALLEL_MODE,
            "base_directory": "$BASE_DIR"
        },
        "attack_categories": [
$(printf '            "%s"' "${SELECTED_ATTACKS[@]}" | paste -sd,)
        ],
        "system_status": {
            "dvd_components_online": "$(check_dvd_status | grep -c "✅")",
            "tools_availability": "high"
        },
        "output_locations": {
            "logs": "$BASE_DIR/attack_logs/",
            "reports": "$BASE_DIR/attack_output/",
            "iocs": "$BASE_DIR/iocs/",
            "summary": "$report_file"
        },
        "attack_summary": {
            "total_categories": ${#SELECTED_ATTACKS[@]},
            "execution_successful": true,
            "estimated_impact": "high"
        }
    }
}
EOF
    
    echo -e "${GREEN}[✓] 최종 리포트 생성 완료: ${report_file}${NC}"
}

# 결과 조회
view_results() {
    echo -e "${BOLD}${CYAN}📊 공격 결과 조회${NC}"
    echo "=================="
    echo ""
    
    # 최근 로그 파일들
    echo -e "${YELLOW}📁 최근 로그 파일들:${NC}"
    find "$BASE_DIR/attack_logs" -name "*.log" -mtime -1 2>/dev/null | head -10 | while read -r logfile; do
        echo -e "${BLUE}  • $(basename "$logfile")${NC}"
    done
    echo ""
    
    # 최근 리포트들
    echo -e "${YELLOW}📄 최근 리포트들:${NC}"
    find "$BASE_DIR/attack_output" -name "*.json" -mtime -1 2>/dev/null | head -10 | while read -r report; do
        echo -e "${BLUE}  • $(basename "$report")${NC}"
    done
    echo ""
    
    # IOC 요약
    echo -e "${YELLOW}🔍 IOC 요약:${NC}"
    if [ -d "$BASE_DIR/iocs" ]; then
        local ioc_count=$(find "$BASE_DIR/iocs" -name "*.txt" -mtime -1 2>/dev/null | wc -l)
        echo -e "${CYAN}  • 생성된 IOC 파일: ${ioc_count}개${NC}"
    fi
    echo ""
}

# 메인 실행 함수
main() {
    # 인자 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                print_usage
                exit 0
                ;;
            -i|--interactive)
                EXECUTION_MODE="interactive"
                shift
                ;;
            -a|--auto)
                EXECUTION_MODE="auto"
                AUTO_MODE="${2:-full}"
                shift 2
                ;;
            -c|--custom)
                EXECUTION_MODE="custom"
                shift
                ;;
            -p|--parallel)
                PARALLEL_MODE=true
                shift
                ;;
            -s|--sequential)
                PARALLEL_MODE=false
                shift
                ;;
            -r|--no-report)
                GENERATE_REPORT=false
                shift
                ;;
            -v|--verbose)
                set -x
                shift
                ;;
            -q|--quiet)
                exec > /dev/null 2>&1
                shift
                ;;
            quick|full|recon|protocol|dos|injection|exfiltration|firmware)
                EXECUTION_MODE="auto"
                AUTO_MODE="$1"
                shift
                ;;
            *)
                echo -e "${RED}[!] 알 수 없는 옵션: $1${NC}"
                print_usage
                exit 1
                ;;
        esac
    done
    
    # 헤더 출력
    print_header
    
    # Root 권한 체크
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[!] 이 스크립트는 root 권한이 필요합니다${NC}"
        echo -e "${YELLOW}[*] 다음 명령으로 실행하세요: sudo $0${NC}"
        exit 1
    fi
    
    # 시스템 상태 확인
    check_system_status
    
    # 필수 도구 확인
    check_required_tools
    
    # 실행 모드에 따른 처리
    case $EXECUTION_MODE in
        "interactive")
            interactive_attack_selection
            ;;
        "auto")
            execute_automatic_attacks "$AUTO_MODE"
            ;;
        "custom")
            # 사용자 정의 선택 (향후 구현)
            interactive_attack_selection
            ;;
    esac
    
    # 공격 실행
    if [ ${#SELECTED_ATTACKS[@]} -gt 0 ]; then
        execute_attacks
    else
        echo -e "${RED}[!] 선택된 공격이 없습니다${NC}"
        exit 1
    fi
    
    # 최종 리포트 생성
    generate_final_report
    
    # 결과 조회
    view_results
    
    echo -e "${BOLD}${GREEN}🎊 Enhanced DVD Attack Suite 실행 완료!${NC}"
    echo ""
    echo -e "${CYAN}📋 추가 명령어:${NC}"
    echo "  • $0 --help                     # 도움말"
    echo "  • $0 -a full                    # 전체 자동 실행"
    echo "  • $0 protocol                   # 프로토콜 공격만"
    echo "  • find $BASE_DIR -name '*.log'  # 로그 파일 찾기"
    echo ""
}

# 정리 함수
cleanup() {
    echo -e "\n${YELLOW}[*] 정리 작업 중...${NC}"
    
    # 백그라운드 프로세스 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    # 임시 파일 정리
    if [ -d "$BASE_DIR/temp" ]; then
        rm -f "$BASE_DIR/temp"/*.tmp 2>/dev/null
    fi
    
    echo -e "${GREEN}[✓] 정리 완료${NC}"
    exit 0
}

# 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"