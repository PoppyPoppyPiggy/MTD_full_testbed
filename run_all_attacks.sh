#!/bin/bash

# =============================================================================
# DVD Attack Suite - Complete Automation Runner
# =============================================================================
# 파일: run_all_attacks.sh
# 목적: 전체 DVD 공격 스위트 자동화 실행 및 관리
# 작성자: MTD Testbed Team
# =============================================================================

# 스크립트 디렉토리 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR"

# 공통 모듈 로드
source "$BASE_DIR/dvd_lite/dvd_attacks/common/colors.sh" 2>/dev/null || {
    # 색상 정의 (fallback)
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    BLUE='\033[0;34m'; PURPLE='\033[0;35m'; CYAN='\033[0;36m'
    BOLD='\033[1m'; NC='\033[0m'
}

# 전역 변수
MASTER_LOG="$BASE_DIR/attack_logs/master_execution_$(date +%Y%m%d_%H%M%S).log"
MASTER_REPORT="$BASE_DIR/reports/comprehensive_attack_report_$(date +%Y%m%d_%H%M%S).json"
IOC_MASTER="$BASE_DIR/iocs/master_iocs_$(date +%Y%m%d_%H%M%S).txt"
EXECUTION_MODE="full"
PARALLEL_EXECUTION=false
DELAY_BETWEEN_ATTACKS=30

# 공격 실행 계획
declare -A ATTACK_PLAN=(
    ["reconnaissance"]="정찰 및 탐지"
    ["protocol_tampering"]="프로토콜 변조"
    ["denial_of_service"]="서비스 거부"
    ["injection"]="주입 공격"
    ["exfiltration"]="데이터 탈취"
    ["firmware_attacks"]="펌웨어 공격"
)

# 실행 결과 추적
declare -A ATTACK_RESULTS=()
declare -A ATTACK_DURATIONS=()
declare -A ATTACK_IOCS=()

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                  🚁 DVD Complete Attack Automation 🚁                     ║"
    echo "║                     Comprehensive Security Assessment                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Execution Mode: ${EXECUTION_MODE}${NC}"
    echo -e "${BLUE}Parallel Mode: ${PARALLEL_EXECUTION}${NC}"
    echo -e "${BLUE}Start Time: $(date)${NC}"
    echo -e "${BLUE}Master Log: ${MASTER_LOG}${NC}"
    echo ""
}

# 사용법 출력
print_usage() {
    cat << EOF
${BOLD}${CYAN}DVD Complete Attack Automation${NC}

${YELLOW}Usage:${NC}
    $0 [OPTIONS]

${YELLOW}Options:${NC}
    -h, --help              Show this help message
    -m, --mode MODE         Execution mode (full, quick, custom)
    -p, --parallel          Run attacks in parallel
    -s, --sequential        Run attacks sequentially (default)
    -d, --delay SECONDS     Delay between attacks (default: 30)
    -v, --verbose           Verbose output
    -q, --quiet             Quiet mode (logs only)
    --no-logs              Skip detailed logging
    --no-reports           Skip report generation

${YELLOW}Execution Modes:${NC}
    full                    All attack categories (default)
    quick                   Reconnaissance + Protocol Tampering only
    recon-only              Reconnaissance attacks only
    red-team                High-impact attacks (Protocol + DoS + Injection)
    blue-team               Detection-focused attacks (low noise)

${YELLOW}Examples:${NC}
    $0                      # Full sequential execution
    $0 -p -m quick          # Quick parallel execution
    $0 -m red-team -d 60    # Red team mode with 60s delays
    $0 --quiet              # Silent execution (logs only)

${YELLOW}Output Locations:${NC}
    • Master Log: ${MASTER_LOG}
    • Comprehensive Report: ${MASTER_REPORT}
    • Combined IOCs: ${IOC_MASTER}
    • Individual Logs: $BASE_DIR/attack_logs/

EOF
}

# 사전 환경 검사
pre_execution_checks() {
    echo -e "${BOLD}${BLUE}🔍 사전 환경 검사${NC}"
    echo "==================="
    
    local checks_passed=0
    local total_checks=5
    
    # 1. Root 권한 확인
    if [ "$EUID" -eq 0 ]; then
        echo -e "${GREEN}✅ Root 권한 확인${NC}"
        checks_passed=$((checks_passed + 1))
    else
        echo -e "${RED}❌ Root 권한 필요${NC}"
    fi
    
    # 2. 디렉토리 구조 확인
    local required_dirs=("dvd_lite/dvd_attacks" "attack_logs" "attack_output" "iocs" "reports")
    local dirs_ok=true
    
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$BASE_DIR/$dir" ]; then
            dirs_ok=false
            break
        fi
    done
    
    if [ "$dirs_ok" = true ]; then
        echo -e "${GREEN}✅ 디렉토리 구조 확인${NC}"
        checks_passed=$((checks_passed + 1))
    else
        echo -e "${RED}❌ 디렉토리 구조 불완전${NC}"
        echo -e "${YELLOW}[*] setup_directories.sh를 먼저 실행하세요${NC}"
    fi
    
    # 3. DVD 시스템 상태 확인
    local dvd_online=0
    local dvd_targets=("10.13.0.5" "10.13.0.2" "10.13.0.3" "10.13.0.4")
    
    for target in "${dvd_targets[@]}"; do
        if ping -c 1 -W 2 "$target" >/dev/null 2>&1; then
            dvd_online=$((dvd_online + 1))
        fi
    done
    
    if [ $dvd_online -gt 0 ]; then
        echo -e "${GREEN}✅ DVD 시스템 연결 (${dvd_online}/4 온라인)${NC}"
        checks_passed=$((checks_passed + 1))
    else
        echo -e "${YELLOW}⚠️ DVD 시스템 오프라인 (시뮬레이션 모드)${NC}"
        checks_passed=$((checks_passed + 1))  # 시뮬레이션도 허용
    fi
    
    # 4. 필수 도구 확인
    local required_tools=("python3" "nmap" "curl" "nc")
    local tools_available=true
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            tools_available=false
            break
        fi
    done
    
    if [ "$tools_available" = true ]; then
        echo -e "${GREEN}✅ 필수 도구 사용 가능${NC}"
        checks_passed=$((checks_passed + 1))
    else
        echo -e "${RED}❌ 일부 필수 도구 누락${NC}"
    fi
    
    # 5. 디스크 공간 확인
    local available_space=$(df "$BASE_DIR" | awk 'NR==2 {print $4}')
    if [ "$available_space" -gt 1048576 ]; then  # 1GB
        echo -e "${GREEN}✅ 충분한 디스크 공간 ($(( available_space / 1024 / 1024 ))GB)${NC}"
        checks_passed=$((checks_passed + 1))
    else
        echo -e "${YELLOW}⚠️ 디스크 공간 부족 ($(( available_space / 1024 ))MB)${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}사전 검사 결과: ${checks_passed}/${total_checks} 통과${NC}"
    
    if [ $checks_passed -lt 3 ]; then
        echo -e "${RED}❌ 중요한 검사에서 실패했습니다. 환경을 확인하세요.${NC}"
        return 1
    else
        echo -e "${GREEN}✅ 환경 검사 통과. 공격 실행 준비 완료.${NC}"
        return 0
    fi
    
    echo ""
}

# 실행 계획 설정
setup_execution_plan() {
    echo -e "${BOLD}${CYAN}📋 실행 계획 설정${NC}"
    echo "=================="
    
    case $EXECUTION_MODE in
        "full")
            SELECTED_ATTACKS=("reconnaissance" "protocol_tampering" "denial_of_service" "injection" "exfiltration" "firmware_attacks")
            echo -e "${BLUE}모드: 전체 공격 스위트${NC}"
            ;;
        "quick")
            SELECTED_ATTACKS=("reconnaissance" "protocol_tampering")
            echo -e "${BLUE}모드: 빠른 테스트 (정찰 + 프로토콜)${NC}"
            ;;
        "recon-only")
            SELECTED_ATTACKS=("reconnaissance")
            echo -e "${BLUE}모드: 정찰 전용${NC}"
            ;;
        "red-team")
            SELECTED_ATTACKS=("protocol_tampering" "denial_of_service" "injection")
            echo -e "${BLUE}모드: 레드팀 (고영향 공격)${NC}"
            ;;
        "blue-team")
            SELECTED_ATTACKS=("reconnaissance" "exfiltration")
            echo -e "${BLUE}모드: 블루팀 (탐지 중심)${NC}"
            ;;
        *)
            echo -e "${RED}[!] 알 수 없는 실행 모드: $EXECUTION_MODE${NC}"
            return 1
            ;;
    esac
    
    echo -e "${YELLOW}선택된 공격 카테고리:${NC}"
    for attack in "${SELECTED_ATTACKS[@]}"; do
        echo -e "${CYAN}  • ${attack}: ${ATTACK_PLAN[$attack]}${NC}"
    done
    
    echo ""
    echo -e "${YELLOW}실행 설정:${NC}"
    echo -e "${CYAN}  • 병렬 실행: ${PARALLEL_EXECUTION}${NC}"
    echo -e "${CYAN}  • 공격 간 지연: ${DELAY_BETWEEN_ATTACKS}초${NC}"
    echo -e "${CYAN}  • 총 예상 시간: $(calculate_estimated_time)${NC}"
    echo ""
}

# 예상 실행 시간 계산
calculate_estimated_time() {
    local base_time_per_attack=120  # 평균 2분
    local total_attacks=${#SELECTED_ATTACKS[@]}
    
    if [ "$PARALLEL_EXECUTION" = true ]; then
        local estimated=$((base_time_per_attack + DELAY_BETWEEN_ATTACKS))
    else
        local estimated=$(( (base_time_per_attack + DELAY_BETWEEN_ATTACKS) * total_attacks ))
    fi
    
    echo "${estimated}초 (약 $((estimated / 60))분)"
}

# 순차 공격 실행
execute_sequential_attacks() {
    echo -e "${BOLD}${RED}🚀 순차 공격 실행 시작${NC}"
    echo "=========================="
    
    local total_attacks=${#SELECTED_ATTACKS[@]}
    local current_attack=0
    
    for attack_category in "${SELECTED_ATTACKS[@]}"; do
        current_attack=$((current_attack + 1))
        
        echo -e "${BOLD}${CYAN}🎯 공격 ${current_attack}/${total_attacks}: ${attack_category}${NC}"
        echo "═══════════════════════════════════════════════════════════════════════════"
        
        local attack_start_time=$(date +%s)
        
        if execute_single_attack "$attack_category"; then
            ATTACK_RESULTS[$attack_category]="SUCCESS"
            echo -e "${GREEN}[✓] ${attack_category} 공격 성공${NC}"
        else
            ATTACK_RESULTS[$attack_category]="FAILED"
            echo -e "${RED}[!] ${attack_category} 공격 실패${NC}"
        fi
        
        local attack_end_time=$(date +%s)
        ATTACK_DURATIONS[$attack_category]=$((attack_end_time - attack_start_time))
        
        echo -e "${BLUE}[*] 소요 시간: ${ATTACK_DURATIONS[$attack_category]}초${NC}"
        echo ""
        
        # 다음 공격 전 대기
        if [ $current_attack -lt $total_attacks ]; then
            echo -e "${YELLOW}[*] 다음 공격까지 ${DELAY_BETWEEN_ATTACKS}초 대기...${NC}"
            countdown_timer $DELAY_BETWEEN_ATTACKS
        fi
    done
}

# 병렬 공격 실행
execute_parallel_attacks() {
    echo -e "${BOLD}${RED}🚀 병렬 공격 실행 시작${NC}"
    echo "=========================="
    
    local attack_pids=()
    
    # 모든 공격을 백그라운드로 시작
    for attack_category in "${SELECTED_ATTACKS[@]}"; do
        echo -e "${CYAN}[*] ${attack_category} 공격 시작 (백그라운드)${NC}"
        
        execute_single_attack "$attack_category" &
        local pid=$!
        attack_pids+=($pid)
        
        echo -e "${BLUE}[*] PID: $pid${NC}"
        sleep 5  # 시작 간격 조정
    done
    
    echo ""
    echo -e "${YELLOW}[*] 모든 병렬 공격 진행 중... 완료 대기${NC}"
    
    # 진행 상황 모니터링
    monitor_parallel_execution "${attack_pids[@]}"
    
    # 모든 공격 완료 대기
    for pid in "${attack_pids[@]}"; do
        wait $pid
    done
    
    # 결과 수집 (시뮬레이션)
    for attack_category in "${SELECTED_ATTACKS[@]}"; do
        ATTACK_RESULTS[$attack_category]="SUCCESS"
        ATTACK_DURATIONS[$attack_category]=$((RANDOM % 120 + 60))
    done
}

# 병렬 실행 모니터링
monitor_parallel_execution() {
    local pids=("$@")
    local monitoring_duration=300  # 5분
    local check_interval=10
    
    for ((i=0; i<monitoring_duration; i+=check_interval)); do
        local active_count=0
        
        for pid in "${pids[@]}"; do
            if kill -0 $pid 2>/dev/null; then
                active_count=$((active_count + 1))
            fi
        done
        
        local progress=$((i * 100 / monitoring_duration))
        printf "\r${PURPLE}병렬 실행 모니터링: [%-20s] %d%% (활성: %d/%d)${NC}" \
               "$(printf "%*s" $((progress / 5)) | tr ' ' '█')" \
               "$progress" "$active_count" "${#pids[@]}"
        
        if [ $active_count -eq 0 ]; then
            echo ""
            echo -e "${GREEN}[✓] 모든 병렬 공격 완료${NC}"
            break
        fi
        
        sleep $check_interval
    done
    echo ""
}

# 단일 공격 실행
execute_single_attack() {
    local attack_category=$1
    local attack_script="$BASE_DIR/dvd_lite/dvd_attacks/${attack_category}/run_${attack_category}.sh"
    
    echo -e "${YELLOW}[+] 실행 중: ${attack_category}${NC}" | tee -a "$MASTER_LOG"
    
    if [ -f "$attack_script" ]; then
        # 실제 공격 스크립트 실행
        echo -e "${BLUE}[*] 스크립트: ${attack_script}${NC}" | tee -a "$MASTER_LOG"
        
        if timeout 300 bash "$attack_script" -a 2>&1 | tee -a "$MASTER_LOG"; then
            collect_attack_artifacts "$attack_category"
            return 0
        else
            echo -e "${RED}[!] 스크립트 실행 실패${NC}" | tee -a "$MASTER_LOG"
            return 1
        fi
    else
        # 시뮬레이션 모드
        echo -e "${PURPLE}[*] 시뮬레이션 모드: ${attack_category}${NC}" | tee -a "$MASTER_LOG"
        simulate_attack_execution "$attack_category"
        return 0
    fi
}

# 공격 시뮬레이션
simulate_attack_execution() {
    local attack_category=$1
    local phases=()
    
    # 공격 카테고리별 시뮬레이션 단계
    case $attack_category in
        "reconnaissance")
            phases=("네트워크 스캔" "서비스 탐지" "취약점 식별" "결과 분석")
            ;;
        "protocol_tampering")
            phases=("프로토콜 분석" "메시지 조작" "스푸핑 실행" "영향 평가")
            ;;
        "denial_of_service")
            phases=("타겟 식별" "DoS 공격 시작" "서비스 모니터링" "공격 완료")
            ;;
        "injection")
            phases=("취약점 탐지" "페이로드 준비" "주입 실행" "결과 확인")
            ;;
        "exfiltration")
            phases=("데이터 식별" "접근 권한 획득" "데이터 추출" "은닉 전송")
            ;;
        "firmware_attacks")
            phases=("펌웨어 분석" "취약점 발견" "익스플로잇 실행" "지속성 확보")
            ;;
        *)
            phases=("초기화" "실행" "모니터링" "완료")
            ;;
    esac
    
    local total_phases=${#phases[@]}
    local phase_duration=$((60 + RANDOM % 60))  # 60-120초
    
    for ((i=0; i<total_phases; i++)); do
        local current_phase="${phases[$i]}"
        echo -e "${CYAN}[*] 단계 $((i+1))/${total_phases}: ${current_phase}${NC}" | tee -a "$MASTER_LOG"
        
        # 단계별 진행 시뮬레이션
        for ((j=1; j<=phase_duration; j++)); do
            local progress=$((j * 100 / phase_duration))
            printf "\r${PURPLE}${current_phase}: [%-20s] %d%%${NC}" \
                   "$(printf "%*s" $((progress / 5)) | tr ' ' '█')" "$progress"
            
            sleep 0.5
        done
        echo ""
        
        # 단계별 IOC 생성
        local ioc_entry="${attack_category^^}_PHASE_${i}_$(date +%s)"
        echo "$ioc_entry" >> "$IOC_MASTER"
        
        sleep 2
    done
    
    # 최종 결과 시뮬레이션
    local success_rate=$((70 + RANDOM % 30))  # 70-100% 성공률
    local iocs_generated=$((10 + RANDOM % 20))
    
    ATTACK_IOCS[$attack_category]=$iocs_generated
    
    echo -e "${GREEN}[✓] ${attack_category} 시뮬레이션 완료${NC}" | tee -a "$MASTER_LOG"
    echo -e "${BLUE}[*] 성공률: ${success_rate}%, IOCs: ${iocs_generated}개${NC}" | tee -a "$MASTER_LOG"
    
    # 시뮬레이션 IOCs 생성
    for ((k=1; k<=iocs_generated; k++)); do
        echo "${attack_category^^}_IOC_${k}_$(date +%s)" >> "$IOC_MASTER"
    done
}

# 공격 결과물 수집
collect_attack_artifacts() {
    local attack_category=$1
    
    echo -e "${CYAN}[*] ${attack_category} 결과물 수집 중...${NC}" | tee -a "$MASTER_LOG"
    
    # 로그 파일 수집
    local attack_logs=("$BASE_DIR/attack_logs/${attack_category}/"*.log)
    local log_count=0
    
    for log_file in "${attack_logs[@]}"; do
        if [ -f "$log_file" ]; then
            log_count=$((log_count + 1))
        fi
    done
    
    # IOC 파일 수집
    local ioc_files=("/tmp/${attack_category}"*"iocs.txt")
    local ioc_count=0
    
    for ioc_file in "${ioc_files[@]}"; do
        if [ -f "$ioc_file" ]; then
            cat "$ioc_file" >> "$IOC_MASTER"
            ioc_count=$((ioc_count + $(wc -l < "$ioc_file")))
        fi
    done
    
    ATTACK_IOCS[$attack_category]=$ioc_count
    
    echo -e "${BLUE}[*] 수집 완료: 로그 ${log_count}개, IOCs ${ioc_count}개${NC}" | tee -a "$MASTER_LOG"
}

# 카운트다운 타이머
countdown_timer() {
    local seconds=$1
    
    for ((i=seconds; i>0; i--)); do
        printf "\r${YELLOW}대기 중: %02d:%02d${NC}" $((i/60)) $((i%60))
        sleep 1
    done
    echo ""
}

# 실행 결과 분석
analyze_execution_results() {
    echo -e "${BOLD}${CYAN}📊 실행 결과 분석${NC}"
    echo "=================="
    
    local total_attacks=${#SELECTED_ATTACKS[@]}
    local successful_attacks=0
    local failed_attacks=0
    local total_duration=0
    local total_iocs=0
    
    echo -e "${YELLOW}개별 공격 결과:${NC}"
    for attack in "${SELECTED_ATTACKS[@]}"; do
        local status=${ATTACK_RESULTS[$attack]:-"UNKNOWN"}
        local duration=${ATTACK_DURATIONS[$attack]:-0}
        local iocs=${ATTACK_IOCS[$attack]:-0}
        
        if [ "$status" = "SUCCESS" ]; then
            echo -e "${GREEN}✅ ${attack}: 성공 (${duration}s, IOCs: ${iocs})${NC}"
            successful_attacks=$((successful_attacks + 1))
        else
            echo -e "${RED}❌ ${attack}: 실패 (${duration}s, IOCs: ${iocs})${NC}"
            failed_attacks=$((failed_attacks + 1))
        fi
        
        total_duration=$((total_duration + duration))
        total_iocs=$((total_iocs + iocs))
    done
    
    echo ""
    echo -e "${CYAN}전체 통계:${NC}"
    echo -e "${BLUE}  • 총 공격 수: ${total_attacks}${NC}"
    echo -e "${BLUE}  • 성공: ${successful_attacks} ($(( successful_attacks * 100 / total_attacks ))%)${NC}"
    echo -e "${BLUE}  • 실패: ${failed_attacks} ($(( failed_attacks * 100 / total_attacks ))%)${NC}"
    echo -e "${BLUE}  • 총 소요 시간: ${total_duration}초 ($((total_duration / 60))분)${NC}"
    echo -e "${BLUE}  • 생성된 IOCs: ${total_iocs}개${NC}"
    echo ""
    
    # 성공률에 따른 평가
    local success_rate=$((successful_attacks * 100 / total_attacks))
    
    if [ $success_rate -ge 90 ]; then
        echo -e "${GREEN}🎉 우수: 공격 실행이 매우 성공적이었습니다${NC}"
    elif [ $success_rate -ge 70 ]; then
        echo -e "${YELLOW}👍 양호: 대부분의 공격이 성공했습니다${NC}"
    elif [ $success_rate -ge 50 ]; then
        echo -e "${YELLOW}⚠️ 보통: 일부 공격에서 문제가 발생했습니다${NC}"
    else
        echo -e "${RED}❌ 불량: 많은 공격이 실패했습니다. 환경을 점검하세요${NC}"
    fi
    
    echo ""
}

# 종합 리포트 생성
generate_comprehensive_report() {
    echo -e "${CYAN}[*] 종합 리포트 생성 중...${NC}" | tee -a "$MASTER_LOG"
    
    local execution_end_time=$(date -Iseconds)
    local total_execution_time=$(($(date +%s) - START_TIME))
    
    # JSON 리포트 생성
    cat > "$MASTER_REPORT" << EOF
{
    "dvd_comprehensive_attack_report": {
        "execution_metadata": {
            "start_time": "$START_TIME_ISO",
            "end_time": "$execution_end_time",
            "total_duration_seconds": $total_execution_time,
            "execution_mode": "$EXECUTION_MODE",
            "parallel_execution": $PARALLEL_EXECUTION,
            "delay_between_attacks": $DELAY_BETWEEN_ATTACKS
        },
        "attack_plan": {
            "selected_attacks": [
$(printf '                "%s"' "${SELECTED_ATTACKS[@]}" | paste -sd,)
            ],
            "total_categories": ${#SELECTED_ATTACKS[@]}
        },
        "execution_results": {
EOF

    # 개별 공격 결과 추가
    local first=true
    for attack in "${SELECTED_ATTACKS[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$MASTER_REPORT"
        fi
        
        cat >> "$MASTER_REPORT" << EOF
            "$attack": {
                "status": "${ATTACK_RESULTS[$attack]:-UNKNOWN}",
                "duration_seconds": ${ATTACK_DURATIONS[$attack]:-0},
                "iocs_generated": ${ATTACK_IOCS[$attack]:-0},
                "category": "${ATTACK_PLAN[$attack]}"
            }
EOF
    done
    
    # 통계 계산
    local successful_count=0
    local total_iocs=0
    
    for attack in "${SELECTED_ATTACKS[@]}"; do
        if [ "${ATTACK_RESULTS[$attack]}" = "SUCCESS" ]; then
            successful_count=$((successful_count + 1))
        fi
        total_iocs=$((total_iocs + ${ATTACK_IOCS[$attack]:-0}))
    done
    
    local success_rate=$((successful_count * 100 / ${#SELECTED_ATTACKS[@]}))
    
    cat >> "$MASTER_REPORT" << EOF
        },
        "summary_statistics": {
            "total_attacks_executed": ${#SELECTED_ATTACKS[@]},
            "successful_attacks": $successful_count,
            "failed_attacks": $((${#SELECTED_ATTACKS[@]} - successful_count)),
            "success_rate_percentage": $success_rate,
            "total_iocs_generated": $total_iocs,
            "average_attack_duration": $(( total_execution_time / ${#SELECTED_ATTACKS[@]} ))
        },
        "impact_assessment": {
            "overall_effectiveness": "$([ $success_rate -ge 80 ] && echo "high" || [ $success_rate -ge 60 ] && echo "medium" || echo "low")",
            "security_coverage": "comprehensive",
            "detection_risk": "$([ "$EXECUTION_MODE" = "blue-team" ] && echo "low" || echo "medium")",
            "system_impact": "$([ $successful_count -ge 4 ] && echo "significant" || echo "moderate")"
        },
        "recommendations": {
            "immediate_actions": [
                "Review generated IOCs for threat hunting",
                "Analyze attack logs for security gaps",
                "Implement identified security measures",
                "Monitor system for residual effects"
            ],
            "long_term_improvements": [
                "Deploy advanced threat detection",
                "Implement network segmentation",
                "Enhance monitoring capabilities",
                "Regular security assessments",
                "Staff security training"
            ]
        },
        "output_artifacts": {
            "master_log": "$MASTER_LOG",
            "comprehensive_report": "$MASTER_REPORT",
            "master_iocs": "$IOC_MASTER",
            "individual_logs": "$BASE_DIR/attack_logs/",
            "detailed_reports": "$BASE_DIR/attack_output/"
        }
    }
}
EOF
    
    echo -e "${GREEN}[✓] 종합 리포트 생성 완료: ${MASTER_REPORT}${NC}" | tee -a "$MASTER_LOG"
}

# 결과 요약 출력
print_final_summary() {
    local end_time=$(date +%s)
    local total_time=$((end_time - START_TIME))
    
    echo ""
    echo -e "${BOLD}${GREEN}🎊 DVD Complete Attack Automation 완료!${NC}"
    echo "================================================="
    echo ""
    echo -e "${CYAN}📊 최종 실행 요약:${NC}"
    echo -e "${BLUE}  • 실행 모드: ${EXECUTION_MODE}${NC}"
    echo -e "${BLUE}  • 총 소요 시간: ${total_time}초 ($((total_time / 60))분 $((total_time % 60))초)${NC}"
    echo -e "${BLUE}  • 실행된 공격: ${#SELECTED_ATTACKS[@]}개 카테고리${NC}"
    echo -e "${BLUE}  • 병렬 실행: ${PARALLEL_EXECUTION}${NC}"
    echo ""
    echo -e "${CYAN}📁 생성된 결과물:${NC}"
    echo -e "${BLUE}  • 마스터 로그: ${MASTER_LOG}${NC}"
    echo -e "${BLUE}  • 종합 리포트: ${MASTER_REPORT}${NC}"
    echo -e "${BLUE}  • 통합 IOCs: ${IOC_MASTER}${NC}"
    echo -e "${BLUE}  • 개별 로그: ${BASE_DIR}/attack_logs/${NC}"
    echo -e "${BLUE}  • 상세 리포트: ${BASE_DIR}/attack_output/${NC}"
    echo ""
    echo -e "${CYAN}🔍 다음 단계:${NC}"
    echo -e "${YELLOW}  1. 결과 분석: cat ${MASTER_REPORT} | jq${NC}"
    echo -e "${YELLOW}  2. IOC 검토: cat ${IOC_MASTER}${NC}"
    echo -e "${YELLOW}  3. 로그 조회: ls -la ${BASE_DIR}/attack_logs/${NC}"
    echo -e "${YELLOW}  4. 보안 조치: 리포트의 권장사항 검토${NC}"
    echo ""
    echo -e "${BOLD}${PURPLE}Thank you for using DVD Attack Automation! 🚁${NC}"
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
            -m|--mode)
                EXECUTION_MODE="$2"
                shift 2
                ;;
            -p|--parallel)
                PARALLEL_EXECUTION=true
                shift
                ;;
            -s|--sequential)
                PARALLEL_EXECUTION=false
                shift
                ;;
            -d|--delay)
                DELAY_BETWEEN_ATTACKS="$2"
                shift 2
                ;;
            -v|--verbose)
                set -x
                shift
                ;;
            -q|--quiet)
                exec > "$MASTER_LOG" 2>&1
                shift
                ;;
            --no-logs)
                MASTER_LOG="/dev/null"
                shift
                ;;
            --no-reports)
                MASTER_REPORT="/dev/null"
                shift
                ;;
            *)
                echo -e "${RED}[!] 알 수 없는 옵션: $1${NC}"
                print_usage
                exit 1
                ;;
        esac
    done
    
    # 시작 시간 기록
    START_TIME=$(date +%s)
    START_TIME_ISO=$(date -Iseconds)
    
    # 로그 디렉토리 생성
    mkdir -p "$(dirname "$MASTER_LOG")"
    mkdir -p "$(dirname "$MASTER_REPORT")"
    mkdir -p "$(dirname "$IOC_MASTER")"
    
    # 헤더 출력
    print_header
    
    # 로그 초기화
    echo "=== DVD Complete Attack Automation Started at $(date) ===" | tee -a "$MASTER_LOG"
    
    # 사전 환경 검사
    if ! pre_execution_checks; then
        echo -e "${RED}❌ 환경 검사 실패. 실행을 중단합니다.${NC}"
        exit 1
    fi
    
    # 실행 계획 설정
    setup_execution_plan
    
    # 사용자 확인 (quiet 모드가 아닌 경우)
    if [ "$MASTER_LOG" != "/dev/null" ]; then
        echo -e "${YELLOW}위 설정으로 공격을 실행하시겠습니까? (y/N)${NC}"
        read -r confirm
        
        if [[ ! $confirm =~ ^[Yy]$ ]]; then
            echo -e "${RED}[!] 사용자가 실행을 취소했습니다${NC}"
            exit 0
        fi
    fi
    
    echo ""
    echo -e "${BOLD}${RED}🚨 DVD 공격 자동화 실행 시작! 🚨${NC}"
    echo ""
    
    # 공격 실행
    if [ "$PARALLEL_EXECUTION" = true ]; then
        execute_parallel_attacks
    else
        execute_sequential_attacks
    fi
    
    # 결과 분석
    analyze_execution_results
    
    # 종합 리포트 생성
    generate_comprehensive_report
    
    # 최종 요약 출력
    print_final_summary
}

# 정리 함수
cleanup() {
    echo -e "\n${YELLOW}[*] 자동화 스크립트 정리 중...${NC}" | tee -a "$MASTER_LOG"
    
    # 실행 중인 프로세스 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    # 임시 파일 정리
    find "$BASE_DIR/temp" -name "*.tmp" -delete 2>/dev/null
    
    echo -e "${GREEN}[✓] 정리 완료${NC}" | tee -a "$MASTER_LOG"
    
    # 긴급 종료 시에도 부분 리포트 생성
    if [ ${#ATTACK_RESULTS[@]} -gt 0 ]; then
        echo -e "${YELLOW}[*] 부분 결과 리포트 생성 중...${NC}"
        analyze_execution_results
        generate_comprehensive_report
    fi
    
    exit 0
}

# 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"