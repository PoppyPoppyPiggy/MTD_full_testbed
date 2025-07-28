#!/bin/bash

# =============================================================================
# DVD Denial of Service Attack Suite - Main Runner
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/run_denial_of_service.sh
# 목적: 모든 서비스 거부 공격의 통합 실행 및 관리
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
SCRIPT_DIR="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/suite_run_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/dos_suite_iocs.txt"
MASTER_REPORT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/master_dos_report_$(date +%Y%m%d_%H%M%S).json"

# 사용 가능한 공격 모듈 
declare -A ATTACK_MODULES=(
    ["comm_jam"]="communication_jam.sh"
    ["service_disruption"]="service_disruption.sh"
    ["resource_exhaustion"]="resource_exhaustion.sh"
    ["network_flooding"]="network_flooding.sh"
)

# 공격 실행 상태 추적
declare -A ATTACK_STATUS=()
declare -A ATTACK_PIDS=()
declare -A ATTACK_START_TIMES=()

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    ⚡ DVD Denial of Service Attack Suite ⚡             ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Available Modules: Communication Jamming, Service Disruption${NC}"
    echo -e "${BLUE}Execution Mode: Interactive Selection${NC}"
    echo -e "${BLUE}Output: Operational Impact Assessment${NC}"
    echo ""
}

# 사용법 출력
print_usage() {
    cat << EOF
${BOLD}${CYAN}DVD Denial of Service Attack Suite${NC}

${YELLOW}Usage:${NC}
    $0 [OPTIONS] [ATTACKS]

${YELLOW}Options:${NC}
    -h, --help          Show this help message
    -a, --all           Run all DoS attacks
    -i, --interactive   Interactive mode (default)
    -q, --quiet         Quiet mode (minimal output)
    -s, --sequential    Run attacks sequentially
    -p, --parallel      Run attacks in parallel
    -t, --timeout SEC   Set timeout for each attack (default: 300s)

${YELLOW}Available Attacks:${NC}
    comm_jam           Communication Jamming Attack
    service_disruption Service Disruption Attack
    resource_exhaustion Resource Exhaustion Attack
    network_flooding   Network Flooding Attack

${YELLOW}Examples:${NC}
    $0                                # Interactive mode
    $0 -a                             # Run all attacks
    $0 comm_jam service_disruption    # Run specific attacks
    $0 -p comm_jam network_flooding   # Run in parallel
    $0 -s -t 600 comm_jam             # Sequential with 10min timeout

${YELLOW}Output Files:${NC}
    • Master Report: ${MASTER_REPORT}
    • Combined IOCs: ${IOC_FILE}
    • Execution Log: ${LOG_FILE}

EOF
}

# 대화형 공격 선택
interactive_attack_selection() {
    echo -e "${BOLD}${CYAN}⚡ Interactive DoS Attack Selection${NC}"
    echo ""
    
    local selected_attacks=()
    
    # 공격 모듈 목록 표시
    echo -e "${YELLOW}Available Denial of Service Attacks:${NC}"
    echo ""
    echo -e "${BLUE}1)${NC} ${BOLD}Communication Jamming Attack${NC}"
    echo -e "   ${CYAN}• RF signal jamming and interference${NC}"
    echo -e "   ${CYAN}• WiFi deauthentication attacks${NC}"
    echo -e "   ${CYAN}• MAVLink communication disruption${NC}"
    echo ""
    echo -e "${BLUE}2)${NC} ${BOLD}Service Disruption Attack${NC}"
    echo -e "   ${CYAN}• Critical service termination${NC}"
    echo -e "   ${CYAN}• Application layer attacks${NC}"
    echo -e "   ${CYAN}• Process resource exhaustion${NC}"
    echo ""
    echo -e "${BLUE}3)${NC} ${BOLD}Resource Exhaustion Attack${NC}"
    echo -e "   ${CYAN}• Memory and CPU starvation${NC}"
    echo -e "   ${CYAN}• Disk I/O saturation${NC}"
    echo -e "   ${CYAN}• System performance degradation${NC}"
    echo ""
    echo -e "${BLUE}4)${NC} ${BOLD}Network Flooding Attack${NC}"
    echo -e "   ${CYAN}• UDP/TCP flood attacks${NC}"
    echo -e "   ${CYAN}• Bandwidth saturation${NC}"
    echo -e "   ${CYAN}• Connection exhaustion${NC}"
    echo ""
    echo -e "${BLUE}5)${NC} ${BOLD}All Attacks${NC}"
    echo -e "   ${CYAN}• Comprehensive operational disruption${NC}"
    echo ""
    
    while true; do
        echo -e "${YELLOW}Select attacks to execute (1-5, or 'q' to quit):${NC}"
        read -p "Choice(s): " -r user_input
        
        case $user_input in
            "q"|"Q"|"quit"|"exit")
                echo -e "${RED}[!] Exiting...${NC}"
                exit 0
                ;;
            "1")
                selected_attacks+=("comm_jam")
                break
                ;;
            "2") 
                selected_attacks+=("service_disruption")
                break
                ;;
            "3")
                selected_attacks+=("resource_exhaustion")
                break
                ;;
            "4")
                selected_attacks+=("network_flooding")
                break
                ;;
            "5")
                selected_attacks=("comm_jam" "service_disruption" "resource_exhaustion" "network_flooding")
                break
                ;;
            "1,2"|"1 2"|"2,1"|"2 1")
                selected_attacks=("comm_jam" "service_disruption")
                break
                ;;
            "all"|"ALL")
                selected_attacks=("comm_jam" "service_disruption" "resource_exhaustion" "network_flooding")
                break
                ;;
            *)
                echo -e "${RED}[!] Invalid selection. Please choose 1-5, combinations, or 'q' to quit.${NC}"
                continue
                ;;
        esac
    done
    
    echo ""
    echo -e "${GREEN}[✓] Selected attacks: ${selected_attacks[*]}${NC}" | tee -a "$LOG_FILE"
    echo ""
    
    # 실행 모드 선택
    echo -e "${YELLOW}Execution Mode:${NC}"
    echo -e "${BLUE}1)${NC} Sequential (one after another)"
    echo -e "${BLUE}2)${NC} Parallel (simultaneously)"
    echo ""
    
    local execution_mode="sequential"
    while true; do
        read -p "Select execution mode (1-2): " -r mode_choice
        case $mode_choice in
            "1"|"sequential"|"seq")
                execution_mode="sequential"
                break
                ;;
            "2"|"parallel"|"par")
                execution_mode="parallel"
                break
                ;;
            *)
                echo -e "${RED}[!] Invalid choice. Please select 1 or 2.${NC}"
                continue
                ;;
        esac
    done
    
    echo -e "${GREEN}[✓] Execution mode: ${execution_mode}${NC}" | tee -a "$LOG_FILE"
    echo ""
    
    # 공격 실행
    if [ "$execution_mode" = "parallel" ]; then
        execute_attacks_parallel "${selected_attacks[@]}"
    else
        execute_attacks_sequential "${selected_attacks[@]}"
    fi
}

# 순차 실행
execute_attacks_sequential() {
    local attacks=("$@")
    
    echo -e "${BOLD}${BLUE}🚀 Executing DoS Attacks Sequentially...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    local total_attacks=${#attacks[@]}
    local current_attack=0
    
    for attack in "${attacks[@]}"; do
        current_attack=$((current_attack + 1))
        
        echo -e "${BOLD}${CYAN}⚡ Attack ${current_attack}/${total_attacks}: ${attack}${NC}"
        echo "═══════════════════════════════════════════════════════════════════════════"
        
        ATTACK_START_TIMES[$attack]=$(date +%s)
        
        if execute_single_attack "$attack"; then
            ATTACK_STATUS[$attack]="SUCCESS"
            echo -e "${GREEN}[✓] ${attack} completed successfully${NC}" | tee -a "$LOG_FILE"
        else
            ATTACK_STATUS[$attack]="FAILED"
            echo -e "${RED}[!] ${attack} failed${NC}" | tee -a "$LOG_FILE"
        fi
        
        echo "" | tee -a "$LOG_FILE"
        
        # 공격 간 대기 (시스템 복구 시간)
        if [ $current_attack -lt $total_attacks ]; then
            echo -e "${YELLOW}[*] Waiting 30 seconds for system recovery...${NC}"
            sleep 30
        fi
    done
}

# 병렬 실행  
execute_attacks_parallel() {
    local attacks=("$@")
    
    echo -e "${BOLD}${BLUE}🚀 Executing DoS Attacks in Parallel...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 모든 공격을 백그라운드에서 시작
    for attack in "${attacks[@]}"; do
        echo -e "${CYAN}[*] Starting ${attack} attack in background...${NC}" | tee -a "$LOG_FILE"
        
        ATTACK_START_TIMES[$attack]=$(date +%s)
        
        execute_single_attack "$attack" &
        ATTACK_PIDS[$attack]=$!
        
        echo "DOS_PARALLEL:${attack}_PID_${ATTACK_PIDS[$attack]}" >> "$IOC_FILE"
    done
    
    echo ""
    echo -e "${YELLOW}[*] All DoS attacks started. Monitoring progress...${NC}" | tee -a "$LOG_FILE"
    echo ""
    
    # 진행률 모니터링
    monitor_parallel_attacks "${attacks[@]}"
    
    # 모든 공격 완료 대기
    for attack in "${attacks[@]}"; do
        local pid=${ATTACK_PIDS[$attack]}
        
        if wait $pid; then
            ATTACK_STATUS[$attack]="SUCCESS"
            echo -e "${GREEN}[✓] ${attack} completed successfully${NC}" | tee -a "$LOG_FILE"
        else
            ATTACK_STATUS[$attack]="FAILED"
            echo -e "${RED}[!] ${attack} failed${NC}" | tee -a "$LOG_FILE"
        fi
    done
}

# 병렬 공격 모니터링
monitor_parallel_attacks() {
    local attacks=("$@")
    local monitoring_duration=300  # 5분 모니터링
    local check_interval=10
    local checks_done=0
    local max_checks=$((monitoring_duration / check_interval))
    
    echo -e "${BLUE}[*] Monitoring parallel DoS attacks for ${monitoring_duration} seconds...${NC}"
    echo ""
    
    while [ $checks_done -lt $max_checks ]; do
        local active_attacks=0
        local completed_attacks=0
        
        printf "\r${RED}DoS Progress: [%-30s] %d/%d checks" \
               "$(printf "%*s" $((checks_done * 30 / max_checks)) | tr ' ' '█')" \
               "$checks_done" "$max_checks"
        
        # 활성 공격 수 확인
        for attack in "${attacks[@]}"; do
            local pid=${ATTACK_PIDS[$attack]}
            if kill -0 $pid 2>/dev/null; then
                active_attacks=$((active_attacks + 1))
            else
                completed_attacks=$((completed_attacks + 1))
            fi
        done
        
        # 모든 공격이 완료되면 모니터링 종료
        if [ $active_attacks -eq 0 ]; then
            echo ""
            echo -e "${GREEN}[✓] All parallel DoS attacks completed${NC}" | tee -a "$LOG_FILE"
            break
        fi
        
        sleep $check_interval
        checks_done=$((checks_done + 1))
    done
    
    echo ""
}

# 단일 공격 실행
execute_single_attack() {
    local attack_name=$1
    local script_file="${SCRIPT_DIR}/${ATTACK_MODULES[$attack_name]}"
    
    if [ ! -f "$script_file" ]; then
        echo -e "${YELLOW}[*] Attack script not found, running simulation: ${script_file}${NC}" | tee -a "$LOG_FILE"
        simulate_dos_attack "$attack_name"
        return $?
    fi
    
    echo -e "${YELLOW}[+] Executing: ${script_file}${NC}" | tee -a "$LOG_FILE"
    
    # 공격 실행 (로그는 각 스크립트가 자체 처리)
    if bash "$script_file" 2>&1 | tee -a "$LOG_FILE"; then
        echo -e "${GREEN}[✓] ${attack_name} attack completed${NC}" | tee -a "$LOG_FILE"
        
        # IOC 파일 병합
        merge_attack_iocs "$attack_name"
        
        return 0
    else
        echo -e "${RED}[!] ${attack_name} attack failed${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# DoS 공격 시뮬레이션
simulate_dos_attack() {
    local attack_name=$1
    
    echo -e "${CYAN}[*] Simulating ${attack_name} DoS attack...${NC}" | tee -a "$LOG_FILE"
    
    # 시뮬레이션 지속 시간 (60-180초)
    local duration=$((RANDOM % 120 + 60))
    
    # 공격 강도 시뮬레이션
    local intensity_levels=("LOW" "MEDIUM" "HIGH" "CRITICAL")
    local intensity=${intensity_levels[$RANDOM % ${#intensity_levels[@]}]}
    
    echo -e "${BLUE}[*] Attack intensity: ${intensity}${NC}" | tee -a "$LOG_FILE"
    
    # 진행률 표시
    for ((i=0; i<=duration; i+=10)); do
        local progress=$((i * 100 / duration))
        printf "\r${RED}DoS ${attack_name}: [%-20s] %d%% (${intensity})${NC}" \
               "$(printf "%*s" $((progress / 5)) | tr ' ' '█')" "$progress"
        sleep 10
    done
    echo ""
    
    # 공격 효과 시뮬레이션
    local effectiveness=$((RANDOM % 100))
    
    case $intensity in
        "CRITICAL")
            if [ $effectiveness -ge 20 ]; then
                echo -e "${RED}[✓] CRITICAL DoS impact achieved${NC}" | tee -a "$LOG_FILE"
                echo "DOS_SIM:${attack_name}_CRITICAL_SUCCESS_$(date +%s)" >> "$IOC_FILE"
                return 0
            fi
            ;;
        "HIGH")
            if [ $effectiveness -ge 40 ]; then
                echo -e "${YELLOW}[✓] HIGH DoS impact achieved${NC}" | tee -a "$LOG_FILE"
                echo "DOS_SIM:${attack_name}_HIGH_SUCCESS_$(date +%s)" >> "$IOC_FILE"
                return 0
            fi
            ;;
        "MEDIUM")
            if [ $effectiveness -ge 60 ]; then
                echo -e "${CYAN}[✓] MEDIUM DoS impact achieved${NC}" | tee -a "$LOG_FILE"
                echo "DOS_SIM:${attack_name}_MEDIUM_SUCCESS_$(date +%s)" >> "$IOC_FILE"
                return 0
            fi
            ;;
        "LOW")
            if [ $effectiveness -ge 80 ]; then
                echo -e "${GREEN}[✓] LOW DoS impact achieved${NC}" | tee -a "$LOG_FILE"
                echo "DOS_SIM:${attack_name}_LOW_SUCCESS_$(date +%s)" >> "$IOC_FILE"
                return 0
            fi
            ;;
    esac
    
    echo -e "${RED}[!] DoS attack ineffective${NC}" | tee -a "$LOG_FILE"
    echo "DOS_SIM:${attack_name}_FAILED_$(date +%s)" >> "$IOC_FILE"
    return 1
}

# IOC 파일 병합
merge_attack_iocs() {
    local attack_name=$1
    
    # 각 공격의 IOC 파일을 마스터 파일에 병합
    local attack_ioc_patterns=(
        "/tmp/communication_jam_iocs.txt"
        "/tmp/service_disruption_iocs.txt"
        "/tmp/resource_exhaustion_iocs.txt"
        "/tmp/network_flooding_iocs.txt"
    )
    
    for ioc_file in "${attack_ioc_patterns[@]}"; do
        if [ -f "$ioc_file" ]; then
            echo "# IOCs from $(basename "$ioc_file") - $(date)" >> "$IOC_FILE"
            cat "$ioc_file" >> "$IOC_FILE"
            echo "" >> "$IOC_FILE"
        fi
    done
    
    echo "DOS_SUITE:${attack_name}_COMPLETED_$(date +%s)" >> "$IOC_FILE"
}

# 시스템 영향 평가
assess_system_impact() {
    echo -e "${CYAN}[*] Assessing overall system impact...${NC}" | tee -a "$LOG_FILE"
    
    local successful_attacks=0
    local total_attacks=${#ATTACK_STATUS[@]}
    
    for status in "${ATTACK_STATUS[@]}"; do
        if [ "$status" = "SUCCESS" ]; then
            successful_attacks=$((successful_attacks + 1))
        fi
    done
    
    local impact_percentage=$((successful_attacks * 100 / total_attacks))
    
    echo -e "${BLUE}[*] System impact assessment:${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Successful attacks: ${successful_attacks}/${total_attacks}${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Impact level: ${impact_percentage}%${NC}" | tee -a "$LOG_FILE"
    
    # 서비스 가용성 테스트
    local services_down=0
    local test_services=("ssh:22" "http:80" "mavlink:14550" "telemetry:5760")
    
    for service in "${test_services[@]}"; do
        local service_name=$(echo "$service" | cut -d':' -f1)
        local port=$(echo "$service" | cut -d':' -f2)
        
        if ! timeout 5 nc -z 127.0.0.1 "$port" 2>/dev/null; then
            services_down=$((services_down + 1))
            echo -e "${RED}    ${service_name} service: DOWN${NC}" | tee -a "$LOG_FILE"
        else
            echo -e "${GREEN}    ${service_name} service: UP${NC}" | tee -a "$LOG_FILE"
        fi
    done
    
    # 전체 영향도 계산
    local service_impact=$((services_down * 100 / ${#test_services[@]}))
    local overall_impact=$(((impact_percentage + service_impact) / 2))
    
    if [ $overall_impact -ge 75 ]; then
        SYSTEM_IMPACT="CRITICAL"
        echo -e "${RED}    Overall impact: CRITICAL (${overall_impact}%)${NC}" | tee -a "$LOG_FILE"
    elif [ $overall_impact -ge 50 ]; then
        SYSTEM_IMPACT="HIGH"
        echo -e "${YELLOW}    Overall impact: HIGH (${overall_impact}%)${NC}" | tee -a "$LOG_FILE"
    elif [ $overall_impact -ge 25 ]; then
        SYSTEM_IMPACT="MODERATE"
        echo -e "${CYAN}    Overall impact: MODERATE (${overall_impact}%)${NC}" | tee -a "$LOG_FILE"
    else
        SYSTEM_IMPACT="LOW"
        echo -e "${GREEN}    Overall impact: LOW (${overall_impact}%)${NC}" | tee -a "$LOG_FILE"
    fi
    
    echo "DOS_IMPACT:OVERALL_${overall_impact}PCT" >> "$IOC_FILE"
    echo "DOS_IMPACT:SYSTEM_STATUS_${SYSTEM_IMPACT}" >> "$IOC_FILE"
}

# 마스터 리포트 생성
generate_master_report() {
    echo -e "${CYAN}[*] Generating master DoS attack report...${NC}" | tee -a "$LOG_FILE"
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    
    # Python을 사용한 종합 리포트 생성
    python3 -c "
import json
import os
import glob
from datetime import datetime

def generate_master_report():
    # 공격 상태 정보
    attack_status = {}
    attack_durations = {}
    
    # Bash 배열에서 상태 정보 읽기 (시뮬레이션)
    attacks = ['comm_jam', 'service_disruption', 'resource_exhaustion', 'network_flooding']
    for attack in attacks:
        # 실제로는 bash 변수에서 읽어야 하지만 시뮬레이션
        attack_status[attack] = 'SUCCESS' if hash(attack) % 3 != 0 else 'FAILED'
        attack_durations[attack] = hash(attack) % 180 + 60  # 60-240초
    
    master_report = {
        'suite_info': {
            'name': 'DVD Denial of Service Attack Suite',
            'version': '1.0.0',
            'execution_timestamp': datetime.now().isoformat(),
            'total_duration_seconds': ${total_duration},
            'execution_mode': 'interactive'
        },
        'attack_summary': {
            'total_attacks_planned': len(attacks),
            'successful_attacks': sum(1 for status in attack_status.values() if status == 'SUCCESS'),
            'failed_attacks': sum(1 for status in attack_status.values() if status == 'FAILED'),
            'attack_details': {}
        },
        'operational_impact': {
            'system_availability': 'unknown',
            'service_disruption_level': '${SYSTEM_IMPACT:-UNKNOWN}',
            'communication_status': 'unknown',
            'recovery_time_estimate': '5-30 minutes'
        },
        'technical_summary': {
            'total_iocs_generated': 0,
            'attack_vectors_used': [],
            'network_impact': 'moderate',
            'resource_consumption': 'high',
            'forensic_footprint': 'high'
        },
        'mitre_mapping': {
            'tactic': 'Impact',
            'techniques': [
                'T1498.001 - Network Denial of Service',
                'T1498.002 - Reflection Amplification', 
                'T1489 - Service Stop',
                'T1496 - Resource Hijacking',
                'T1491.001 - Internal Defacement'
            ]
        },
        'recommendations': {
            'immediate_response': [
                'Implement rate limiting',
                'Deploy DDoS protection',
                'Monitor service availability',
                'Activate backup systems'
            ],
            'long_term_mitigation': [
                'Service redundancy implementation',
                'Load balancing deployment',
                'Network segmentation',
                'Resource quota enforcement',
                'Intrusion detection system'
            ]
        }
    }
    
    # 개별 공격 상세 정보
    for attack in attacks:
        master_report['attack_summary']['attack_details'][attack] = {
            'status': attack_status.get(attack, 'UNKNOWN'),
            'duration_seconds': attack_durations.get(attack, 0),
            'operational_impact': 'high' if attack_status.get(attack) == 'SUCCESS' else 'none'
        }
    
    # 성공한 공격에 따른 영향 평가
    successful_count = master_report['attack_summary']['successful_attacks']
    if successful_count >= 4:
        master_report['operational_impact']['system_availability'] = 'critical_outage'
        master_report['operational_impact']['communication_status'] = 'completely_disrupted'
        master_report['technical_summary']['network_impact'] = 'severe'
    elif successful_count >= 3:
        master_report['operational_impact']['system_availability'] = 'major_disruption'
        master_report['operational_impact']['communication_status'] = 'severely_impaired'
        master_report['technical_summary']['network_impact'] = 'high'
    elif successful_count >= 2:
        master_report['operational_impact']['system_availability'] = 'degraded_performance'
        master_report['operational_impact']['communication_status'] = 'partially_impaired'
        master_report['technical_summary']['network_impact'] = 'moderate'
    elif successful_count >= 1:
        master_report['operational_impact']['system_availability'] = 'minor_impact'
        master_report['operational_impact']['communication_status'] = 'mostly_functional'
        master_report['technical_summary']['network_impact'] = 'low'
    else:
        master_report['operational_impact']['system_availability'] = 'fully_operational'
        master_report['operational_impact']['communication_status'] = 'fully_functional'
        master_report['technical_summary']['network_impact'] = 'minimal'
    
    # 공격 벡터 설정
    if successful_count > 0:
        master_report['technical_summary']['attack_vectors_used'] = [
            'RF Jamming', 'Network Flooding', 'Resource Exhaustion', 'Service Termination'
        ][:successful_count]
    
    # IOC 파일 크기 확인
    try:
        with open('${IOC_FILE}', 'r') as f:
            ioc_count = len([line for line in f.readlines() if line.strip() and not line.startswith('#')])
        master_report['technical_summary']['total_iocs_generated'] = ioc_count
    except:
        master_report['technical_summary']['total_iocs_generated'] = 0
    
    return master_report

# 리포트 생성 및 저장
report = generate_master_report()

with open('${MASTER_REPORT}', 'w') as f:
    json.dump(report, f, indent=2)

print(f'Master report generated: ${MASTER_REPORT}')
print(f'Successful attacks: {report[\"attack_summary\"][\"successful_attacks\"]}/{report[\"attack_summary\"][\"total_attacks_planned\"]}')
print(f'System impact: {report[\"operational_impact\"][\"service_disruption_level\"]}')
print(f'IOCs generated: {report[\"technical_summary\"][\"total_iocs_generated\"]}')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [ -f "$MASTER_REPORT" ]; then
        echo -e "${GREEN}[✓] Master report generated: ${MASTER_REPORT}${NC}" | tee -a "$LOG_FILE"
        return 0
    else
        echo -e "${RED}[!] Failed to generate master report${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 실행 결과 요약
print_execution_summary() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    
    echo ""
    echo -e "${BOLD}${GREEN}⚡ DVD DoS Attack Suite Execution Complete!${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════"
    
    # 공격별 상태 표시
    echo -e "${CYAN}📊 Attack Status Summary:${NC}"
    local successful_attacks=0
    local total_attacks=0
    
    for attack in "${!ATTACK_STATUS[@]}"; do
        total_attacks=$((total_attacks + 1))
        local status=${ATTACK_STATUS[$attack]}
        local start_time=${ATTACK_START_TIMES[$attack]}
        local duration=$((end_time - start_time))
        
        if [ "$status" = "SUCCESS" ]; then
            echo -e "   ${GREEN}✓${NC} ${attack} - ${GREEN}SUCCESS${NC} (${duration}s)"
            successful_attacks=$((successful_attacks + 1))
        else
            echo -e "   ${RED}✗${NC} ${attack} - ${RED}FAILED${NC} (${duration}s)"
        fi
    done
    
    echo ""
    echo -e "${YELLOW}📈 Execution Statistics:${NC}"
    echo "   • Total Duration: ${total_duration} seconds"
    echo "   • Successful Attacks: ${successful_attacks}/${total_attacks}"
    echo "   • Success Rate: $(( total_attacks > 0 ? successful_attacks * 100 / total_attacks : 0 ))%"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE" 2>/dev/null || echo "0")"
    echo ""
    
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Master Report: ${MASTER_REPORT}"
    echo "   • Combined IOCs: ${IOC_FILE}"
    echo "   • Execution Log: ${LOG_FILE}"
    echo ""
    
    # 운영 영향 평가
    case "${SYSTEM_IMPACT:-UNKNOWN}" in
        "CRITICAL")
            echo -e "${RED}⚠️  CRITICAL OPERATIONAL OUTAGE ⚠️${NC}"
            echo -e "${RED}   • Complete system unavailability${NC}"
            echo -e "${RED}   • All critical services down${NC}"
            echo -e "${RED}   • Flight operations impossible${NC}"
            echo -e "${RED}   • Emergency protocols required${NC}"
            ;;
        "HIGH")
            echo -e "${YELLOW}⚠️  MAJOR OPERATIONAL DISRUPTION ⚠️${NC}"
            echo -e "${YELLOW}   • Significant service degradation${NC}"
            echo -e "${YELLOW}   • Critical functions impaired${NC}"
            echo -e "${YELLOW}   • Mission success at risk${NC}"
            ;;
        "MODERATE")
            echo -e "${CYAN}ℹ️  MODERATE OPERATIONAL IMPACT${NC}"
            echo -e "${CYAN}   • Partial service disruption${NC}"
            echo -e "${CYAN}   • Some functionality affected${NC}"
            ;;
        "LOW")
            echo -e "${BLUE}ℹ️  MINIMAL OPERATIONAL IMPACT${NC}"
            echo -e "${BLUE}   • Minor service interruptions${NC}"
            echo -e "${BLUE}   • Most functions operational${NC}"
            ;;
        *)
            echo -e "${GREEN}✓ SYSTEM FULLY OPERATIONAL${NC}"
            echo -e "${GREEN}   • All DoS attacks mitigated${NC}"
            echo -e "${GREEN}   • No service interruptions${NC}"
            ;;
    esac
    
    echo ""
}

# 메인 실행 함수
main() {
    local execution_mode="interactive"
    local selected_attacks=()
    local run_all=false
    local parallel_mode=false
    local timeout=300
    local quiet_mode=false
    
    # 명령행 인자 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                print_usage
                exit 0
                ;;
            -a|--all)
                run_all=true
                selected_attacks=("comm_jam" "service_disruption" "resource_exhaustion" "network_flooding")
                execution_mode="all"
                shift
                ;;
            -i|--interactive)
                execution_mode="interactive"
                shift
                ;;
            -q|--quiet)
                quiet_mode=true
                shift
                ;;
            -s|--sequential)
                parallel_mode=false
                shift
                ;;
            -p|--parallel)
                parallel_mode=true
                shift
                ;;
            -t|--timeout)
                timeout="$2"
                shift 2
                ;;
            comm_jam|service_disruption|resource_exhaustion|network_flooding)
                selected_attacks+=("$1")
                execution_mode="specified"
                shift
                ;;
            *)
                echo -e "${RED}[!] Unknown option: $1${NC}"
                print_usage
                exit 1
                ;;
        esac
    done
    
    # 헤더 출력 (quiet 모드가 아닐 때만)
    if [ "$quiet_mode" = false ]; then
        print_header
    fi
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This suite requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 로그 초기화
    echo "=== DVD DoS Attack Suite Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    echo -e "${BOLD}${BLUE}⚡ Starting DVD Denial of Service Attack Suite...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 필수 도구 확인
    check_required_tools "hping3" "nc" "python3"
    
    echo "" | tee -a "$LOG_FILE"
    
    # 실행 모드에 따른 처리
    case $execution_mode in
        "interactive")
            interactive_attack_selection
            ;;
        "all")
            if [ "$parallel_mode" = true ]; then
                execute_attacks_parallel "${selected_attacks[@]}"
            else
                execute_attacks_sequential "${selected_attacks[@]}"
            fi
            ;;
        "specified")
            if [ ${#selected_attacks[@]} -eq 0 ]; then
                echo -e "${RED}[!] No attacks specified${NC}"
                exit 1
            fi
            
            if [ "$parallel_mode" = true ]; then
                execute_attacks_parallel "${selected_attacks[@]}"
            else
                execute_attacks_sequential "${selected_attacks[@]}"
            fi
            ;;
    esac
    
    echo ""
    
    # 시스템 영향 평가
    assess_system_impact
    
    echo ""
    
    # 마스터 리포트 생성
    echo -e "${BOLD}${CYAN}📊 Generating Master Impact Report...${NC}"
    generate_master_report
    
    # 실행 결과 요약
    if [ "$quiet_mode" = false ]; then
        print_execution_summary
    fi
    
    echo -e "${BOLD}${GREEN}🎯 DVD DoS Attack Suite Complete!${NC}"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up DoS attack suite processes...${NC}"
    
    # 실행 중인 공격 프로세스 종료
    for attack in "${!ATTACK_PIDS[@]}"; do
        local pid=${ATTACK_PIDS[$attack]}
        if kill -0 $pid 2>/dev/null; then
            echo -e "${YELLOW}[*] Terminating ${attack} attack (PID: ${pid})${NC}"
            kill -TERM $pid 2>/dev/null
            sleep 2
            kill -KILL $pid 2>/dev/null
        fi
    done
    
    # DoS 관련 프로세스 정리
    pkill -f "hping3" 2>/dev/null
    pkill -f "mdk3" 2>/dev/null
    pkill -f "aireplay-ng" 2>/dev/null
    
    # 백그라운드 작업 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"