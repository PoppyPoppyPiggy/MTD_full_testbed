#!/bin/bash
# dos_attacks.sh - 서비스 거부 공격 통합 실행 스크립트
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/dos_attacks.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

SCRIPT_DIR="$(dirname "$0")"
LOG_FILE="$(get_log_dir)/dos_attacks_main.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║              서비스 거부 공격 도구                ║"
    echo "║          Denial of Service Attack Suite          ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    echo -e "${CYAN}사용법: $0 <attack_type> [options]${NC}"
    echo ""
    echo -e "${YELLOW}사용 가능한 공격:${NC}"
    echo "  1. wifi_deauth           - WiFi 인증 해제 공격"
    echo "  2. geofencing            - 지오펜스 조작 공격"
    echo "  3. gps_offset            - GPS 오프셋 글리칭 공격"
    echo "  4. flight_termination    - 비행 종료 공격"
    echo "  5. camera_ros_flood      - 카메라 ROS 토픽 플러딩 공격"
    echo "  6. denial_of_takeoff     - 이륙 거부 공격"
    echo "  7. communication_flood   - 통신 링크 플러딩 공격"
    echo "  8. all                   - 모든 공격 순차 실행"
    echo "  9. interactive           - 대화형 모드"
    echo ""
    echo -e "${YELLOW}옵션:${NC}"
    echo "  --help, -h              - 이 도움말 표시"
    echo "  --list, -l              - 사용 가능한 공격 목록"
    echo "  --verbose, -v           - 상세 출력"
    echo "  --dry-run              - 실제 공격 없이 테스트"
    echo ""
    echo -e "${YELLOW}예시:${NC}"
    echo "  $0 wifi_deauth"
    echo "  $0 all --verbose"
    echo "  $0 interactive"
}

list_attacks() {
    echo -e "${GREEN}=== 사용 가능한 DoS 공격 ===${NC}"
    echo ""
    
    local attacks=(
        "wifi_deauth:WiFi 인증 해제 공격:WiFi 네트워크에서 클라이언트 강제 연결 해제"
        "geofencing:지오펜스 조작 공격:드론의 지오펜스 설정을 조작하여 비행 제한"
        "gps_offset:GPS 오프셋 글리칭:GPS 위치 파라미터 조작으로 EKF 실패 유도"
        "flight_termination:비행 종료 공격:강제 비행 종료 명령 전송"
        "camera_ros_flood:카메라 ROS 플러딩:ROS 토픽을 플러딩하여 카메라 피드 방해"
        "denial_of_takeoff:이륙 거부 공격:Pre-arm 검사 방해로 이륙 방지"
        "communication_flood:통신 링크 플러딩:MAVLink 통신 채널 포화 공격"
    )
    
    for attack in "${attacks[@]}"; do
        local name=$(echo "$attack" | cut -d: -f1)
        local title=$(echo "$attack" | cut -d: -f2)
        local desc=$(echo "$attack" | cut -d: -f3)
        
        echo -e "${CYAN}$name${NC}"
        echo -e "  제목: $title"
        echo -e "  설명: $desc"
        echo ""
    done
}

check_attack_availability() {
    local attack_name="$1"
    
    case "$attack_name" in
        "wifi_deauth")
            [[ -f "$SCRIPT_DIR/wifi_deauth.sh" ]] && return 0 ;;
        "geofencing")
            [[ -f "$SCRIPT_DIR/geofencing_attack.sh" ]] && return 0 ;;
        "gps_offset")
            [[ -f "$SCRIPT_DIR/gps_offset_attack.sh" ]] && return 0 ;;
        "flight_termination")
            [[ -f "$SCRIPT_DIR/flight_termination.sh" ]] && return 0 ;;
        "camera_ros_flood")
            [[ -f "$SCRIPT_DIR/camera_ros_flood.sh" ]] && return 0 ;;
        "denial_of_takeoff")
            [[ -f "$SCRIPT_DIR/denial_of_takeoff.sh" ]] && return 0 ;;
        "communication_flood")
            [[ -f "$SCRIPT_DIR/communication_link_flood.sh" ]] && return 0 ;;
    esac
    
    return 1
}

execute_attack() {
    local attack_name="$1"
    local dry_run="$2"
    
    log_info "Executing $attack_name attack..."
    
    if [[ "$dry_run" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN] Would execute: $attack_name${NC}"
        return 0
    fi
    
    local script_path=""
    local attack_title=""
    
    case "$attack_name" in
        "wifi_deauth")
            script_path="$SCRIPT_DIR/wifi_deauth.sh"
            attack_title="WiFi 인증 해제 공격"
            ;;
        "geofencing")
            script_path="$SCRIPT_DIR/geofencing_attack.sh"
            attack_title="지오펜스 조작 공격"
            ;;
        "gps_offset")
            script_path="$SCRIPT_DIR/gps_offset_attack.sh"
            attack_title="GPS 오프셋 글리칭 공격"
            ;;
        "flight_termination")
            script_path="$SCRIPT_DIR/flight_termination.sh"
            attack_title="비행 종료 공격"
            ;;
        "camera_ros_flood")
            script_path="$SCRIPT_DIR/camera_ros_flood.sh"
            attack_title="카메라 ROS 플러딩 공격"
            ;;
        "denial_of_takeoff")
            script_path="$SCRIPT_DIR/denial_of_takeoff.sh"
            attack_title="이륙 거부 공격"
            ;;
        "communication_flood")
            script_path="$SCRIPT_DIR/communication_link_flood.sh"
            attack_title="통신 링크 플러딩 공격"
            ;;
        *)
            log_error "Unknown attack: $attack_name"
            return 1
            ;;
    esac
    
    if [[ ! -f "$script_path" ]]; then
        log_error "Attack script not found: $script_path"
        return 1
    fi
    
    echo -e "\n${BLUE}[*] Starting: $attack_title${NC}"
    echo "======================================" >> "$LOG_FILE"
    echo "Attack: $attack_title" >> "$LOG_FILE"
    echo "Started: $(date)" >> "$LOG_FILE"
    echo "======================================" >> "$LOG_FILE"
    
    # 공격 실행
    if bash "$script_path"; then
        log_success "$attack_title completed successfully"
        echo "Status: SUCCESS" >> "$LOG_FILE"
        return 0
    else
        log_error "$attack_title failed"
        echo "Status: FAILED" >> "$LOG_FILE"
        return 1
    fi
}

run_all_attacks() {
    local dry_run="$1"
    
    log_info "Running all DoS attacks sequentially..."
    
    local attacks=(
        "wifi_deauth"
        "geofencing"
        "gps_offset"
        "flight_termination"
        "camera_ros_flood"
        "denial_of_takeoff"
        "communication_flood"
    )
    
    local results=()
    local successful=0
    local total=${#attacks[@]}
    
    echo -e "${GREEN}=== 전체 DoS 공격 실행 ===${NC}"
    echo "총 공격 수: $total"
    echo ""
    
    for attack in "${attacks[@]}"; do
        if check_attack_availability "$attack"; then
            echo -e "${CYAN}[*] 공격 실행: $attack${NC}"
            
            if execute_attack "$attack" "$dry_run"; then
                results+=("$attack:SUCCESS")
                ((successful++))
            else
                results+=("$attack:FAILED")
            fi
            
            # 공격 간 대기 시간
            echo -e "${YELLOW}[*] 다음 공격까지 대기 중... (30초)${NC}"
            sleep 30
        else
            log_warning "Attack $attack not available"
            results+=("$attack:UNAVAILABLE")
        fi
    done
    
    # 결과 요약
    echo -e "\n${GREEN}=== 전체 공격 결과 ===${NC}"
    echo "성공한 공격: $successful/$total"
    echo "성공률: $((successful * 100 / total))%"
    echo ""
    
    for result in "${results[@]}"; do
        local attack_name=$(echo "$result" | cut -d: -f1)
        local status=$(echo "$result" | cut -d: -f2)
        
        case "$status" in
            "SUCCESS")
                echo -e "  └─ $attack_name: ${GREEN}성공${NC}"
                ;;
            "FAILED")
                echo -e "  └─ $attack_name: ${RED}실패${NC}"
                ;;
            "UNAVAILABLE")
                echo -e "  └─ $attack_name: ${YELLOW}사용 불가${NC}"
                ;;
        esac
    done
}

interactive_mode() {
    echo -e "${GREEN}=== 대화형 DoS 공격 모드 ===${NC}"
    echo ""
    
    while true; do
        echo -e "${CYAN}사용 가능한 공격:${NC}"
        echo "  1) WiFi 인증 해제 공격"
        echo "  2) 지오펜스 조작 공격"
        echo "  3) GPS 오프셋 글리칭 공격"
        echo "  4) 비행 종료 공격"
        echo "  5) 카메라 ROS 플러딩 공격"
        echo "  6) 이륙 거부 공격"
        echo "  7) 통신 링크 플러딩 공격"
        echo "  8) 모든 공격 실행"
        echo "  9) 종료"
        echo ""
        
        read -p "선택하세요 (1-9): " choice
        
        case "$choice" in
            1) execute_attack "wifi_deauth" "false" ;;
            2) execute_attack "geofencing" "false" ;;
            3) execute_attack "gps_offset" "false" ;;
            4) execute_attack "flight_termination" "false" ;;
            5) execute_attack "camera_ros_flood" "false" ;;
            6) execute_attack "denial_of_takeoff" "false" ;;
            7) execute_attack "communication_flood" "false" ;;
            8) run_all_attacks "false" ;;
            9) 
                echo -e "${GREEN}대화형 모드를 종료합니다.${NC}"
                break
                ;;
            *)
                echo -e "${RED}잘못된 선택입니다. 1-9 사이의 숫자를 입력하세요.${NC}"
                ;;
        esac
        
        echo ""
        read -p "계속하려면 Enter를 누르세요..."
        echo ""
    done
}

generate_summary_report() {
    local attack_results=("$@")
    
    log_info "Generating DoS attack summary report..."
    
    local report_file="$(get_log_dir)/dos_attacks_summary_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║            서비스 거부 공격 통합 보고서           ║
║          Denial of Service Attack Summary         ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Attack Suite: Denial of Service (DoS)
Total Attacks Executed: ${#attack_results[@]}

╔═══ ATTACK SUMMARY ═══╗

$(for result in "${attack_results[@]}"; do
    local attack=$(echo "$result" | cut -d: -f1)
    local status=$(echo "$result" | cut -d: -f2)
    echo "  └─ $attack: $status"
done)

╔═══ ATTACK CATEGORIES ═══╗

1. Network-Level Attacks
   - WiFi Deauthentication: 무선 네트워크 연결 차단
   - Communication Flooding: 통신 채널 포화 공격

2. Protocol-Level Attacks  
   - Geofencing Manipulation: 지오펜스 파라미터 조작
   - GPS Offset Glitching: GPS 위치 데이터 손상

3. Application-Level Attacks
   - Flight Termination: 비행 종료 명령 주입
   - Denial of Takeoff: 이륙 방지 공격
   - ROS Topic Flooding: 로봇 운영체제 토픽 플러딩

╔═══ SECURITY IMPLICATIONS ═══╗

1. Mission Disruption
   - 드론 운영 임무 중단
   - 자율 비행 방해
   - 안전 시스템 우회

2. Communication Attacks
   - 지상 제어소-드론 간 통신 차단
   - 텔레메트리 데이터 손실
   - 명령 전달 실패

3. Safety System Compromise
   - 안전 장치 무력화
   - 응급 상황 대응 방해
   - 시스템 무결성 훼손

╔═══ ATTACK EFFECTIVENESS ═══╗

High Impact Attacks:
  - Flight Termination: 즉시 비행 중단
  - WiFi Deauthentication: 통신 연결 차단
  - Denial of Takeoff: 미션 시작 방해

Medium Impact Attacks:
  - Geofencing Manipulation: 운영 제한 조작
  - GPS Offset Glitching: 항법 시스템 혼란
  - Communication Flooding: 서비스 품질 저하

Specialized Attacks:
  - ROS Topic Flooding: 특정 시스템 대상

╔═══ DEFENSIVE COUNTERMEASURES ═══╗

1. Network Security
   - 802.11w (PMF) 활성화
   - VPN 터널링 구현
   - 네트워크 분할 및 격리

2. Protocol Hardening
   - MAVLink 메시지 서명
   - 파라미터 변경 인증
   - 통신 암호화 강화

3. System Monitoring
   - 실시간 이상 탐지
   - 통신 패턴 분석
   - 자동 대응 시스템

4. Redundancy & Backup
   - 다중 통신 채널
   - 백업 항법 시스템
   - 오프라인 안전 모드

╔═══ RECOMMENDATIONS ═══╗

Immediate Actions:
  1. 중요 시스템 네트워크 격리
  2. 강력한 인증 메커니즘 구현
  3. 실시간 모니터링 시스템 배치

Long-term Strategy:
  1. 보안 강화된 통신 프로토콜 적용
  2. AI 기반 이상 탐지 시스템 도입
  3. 정기적인 보안 감사 및 테스트

╚═══════════════════════╝
EOF

    log_success "Summary report saved to: $report_file"
    echo -e "${GREEN}Summary report location: $report_file${NC}"
}

main() {
    print_banner
    
    # 명령줄 인수 파싱
    local attack_type=""
    local verbose=false
    local dry_run=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                print_help
                exit 0
                ;;
            --list|-l)
                list_attacks
                exit 0
                ;;
            --verbose|-v)
                verbose=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                if [[ -z "$attack_type" ]]; then
                    attack_type="$1"
                else
                    echo -e "${RED}Error: Unknown option $1${NC}"
                    print_help
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # 로깅 설정
    echo "DoS Attacks Suite Started: $(date)" >> "$LOG_FILE"
    echo "Arguments: $*" >> "$LOG_FILE"
    echo "======================================" >> "$LOG_FILE"
    
    # Verbose 모드 설정
    if [[ "$verbose" == true ]]; then
        export VERBOSE=true
        echo -e "${YELLOW}Verbose mode enabled${NC}"
    fi
    
    # Dry-run 모드 알림
    if [[ "$dry_run" == true ]]; then
        echo -e "${YELLOW}Dry-run mode enabled - no actual attacks will be executed${NC}"
    fi
    
    # 공격 타입에 따른 실행
    case "$attack_type" in
        "interactive")
            interactive_mode
            ;;
        "all")
            run_all_attacks "$dry_run"
            ;;
        "wifi_deauth"|"geofencing"|"gps_offset"|"flight_termination"|"camera_ros_flood"|"denial_of_takeoff"|"communication_flood")
            if check_attack_availability "$attack_type"; then
                execute_attack "$attack_type" "$dry_run"
            else
                log_error "Attack $attack_type is not available"
                exit 1
            fi
            ;;
        "")
            echo -e "${RED}Error: No attack type specified${NC}"
            echo ""
            print_help
            exit 1
            ;;
        *)
            echo -e "${RED}Error: Unknown attack type: $attack_type${NC}"
            echo ""
            print_help
            exit 1
            ;;
    esac
    
    echo "DoS Attacks Suite Completed: $(date)" >> "$LOG_FILE"
    log_success "DoS attack suite execution completed"
}

# 스크립트가 직접 실행될 때만 main 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi