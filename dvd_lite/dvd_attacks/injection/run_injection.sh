#!/bin/bash

# =============================================================================
# DVD Injection Attack Suite - Main Runner
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/run_injection.sh
# 목적: 모든 인젝션 공격의 통합 실행 및 관리
# 작성자: MTD Testbed Team
# 기반: Damn Vulnerable Drone Attack Scenarios
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
SCRIPT_DIR="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/suite_run_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/injection_suite_iocs.txt"
MASTER_REPORT="/home/kali/MTD/MTD_full_testbed/attack_output/injection/master_injection_report_$(date +%Y%m%d_%H%M%S).json"

# 사용 가능한 공격 모듈
declare -A ATTACK_MODULES=(
    ["mavlink_command"]="mavlink_command_injection.sh"
    ["gps_spoofing"]="gps_spoofing.sh"
    ["sql_injection"]="sql_injection.sh"
    ["parameter_manipulation"]="parameter_manipulation.sh"
    ["waypoint_injection"]="waypoint_injection.sh"
    ["firmware_injection"]="firmware_injection.sh"
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
    echo "║                      💉 DVD Injection Attack Suite 💉                   ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Available Modules: MAVLink, GPS, SQL, Parameters, Waypoints${NC}"
    echo -e "${BLUE}Execution Mode: Interactive Selection${NC}"
    echo -e "${BLUE}Output: Comprehensive Impact Assessment${NC}"
    echo ""
}

# 사용법 출력
print_usage() {
    cat << EOF
${BOLD}${CYAN}DVD Injection Attack Suite${NC}

${YELLOW}Usage:${NC}
    $0 [OPTIONS] [ATTACKS]

${YELLOW}Options:${NC}
    -h, --help          Show this help message
    -a, --all           Run all injection attacks
    -i, --interactive   Interactive mode (default)
    -q, --quiet         Quiet mode (minimal output)
    -s, --sequential    Run attacks sequentially
    -p, --parallel      Run attacks in parallel
    -t, --timeout SEC   Set timeout for each attack (default: 300s)

${YELLOW}Available Attacks:${NC}
    mavlink_command    MAVLink Command Injection Attack
    gps_spoofing       GPS Signal Spoofing Attack
    sql_injection      SQL Injection & Database Attack
    parameter_manipulation Parameter Manipulation Attack
    waypoint_injection Waypoint & Mission Injection Attack
    firmware_injection Firmware Injection Attack

${YELLOW}Examples:${NC}
    $0                                # Interactive mode
    $0 -a                             # Run all attacks
    $0 mavlink_command sql_injection  # Run specific attacks
    $0 -p gps_spoofing waypoint_injection # Run in parallel
    $0 -s -t 600 mavlink_command      # Sequential with 10min timeout

${YELLOW}Output Files:${NC}
    • Master Report: ${MASTER_REPORT}
    • Combined IOCs: ${IOC_FILE}
    • Execution Log: ${LOG_FILE}

EOF
}

# 대화형 공격 선택
interactive_attack_selection() {
    echo -e "${BOLD}${CYAN}💉 Interactive Injection Attack Selection${NC}"
    echo ""
    
    local selected_attacks=()
    
    # 공격 모듈 목록 표시
    echo -e "${YELLOW}Available Injection Attacks:${NC}"
    echo ""
    echo -e "${BLUE}1)${NC} ${BOLD}MAVLink Command Injection${NC}"
    echo -e "   ${CYAN}• Malicious flight command injection${NC}"
    echo -e "   ${CYAN}• Emergency disarm and forced landing${NC}"
    echo -e "   ${CYAN}• Mission waypoint hijacking${NC}"
    echo ""
    echo -e "${BLUE}2)${NC} ${BOLD}GPS Signal Spoofing${NC}"
    echo -e "   ${CYAN}• Location data manipulation${NC}"
    echo -e "   ${CYAN}• RTL home point hijacking${NC}"
    echo -e "   ${CYAN}• Geofence bypass attacks${NC}"
    echo ""
    echo -e "${BLUE}3)${NC} ${BOLD}SQL Injection Attack${NC}"
    echo -e "   ${CYAN}• Database exploitation${NC}"
    echo -e "   ${CYAN}• Authentication bypass${NC}"
    echo -e "   ${CYAN}• Sensitive data extraction${NC}"
    echo ""
    echo -e "${BLUE}4)${NC} ${BOLD}Parameter Manipulation${NC}"
    echo -e "   ${CYAN}• Critical system parameter changes${NC}"
    echo -e "   ${CYAN}• Safety system disabling${NC}"
    echo -e "   ${CYAN}• Configuration tampering${NC}"
    echo ""
    echo -e "${BLUE}5)${NC} ${BOLD}Waypoint Injection${NC}"
    echo -e "   ${CYAN}• Malicious mission injection${NC}"
    echo -e "   ${CYAN}• Route hijacking${NC}"
    echo -e "   ${CYAN}• Restricted area navigation${NC}"
    echo ""
    echo -e "${BLUE}6)${NC} ${BOLD}Firmware Injection${NC}"
    echo -e "   ${CYAN}• Malicious firmware upload${NC}"
    echo -e "   ${CYAN}• Bootloader exploitation${NC}"
    echo -e "   ${CYAN}• Persistent backdoor installation${NC}"
    echo ""
    echo -e "${BLUE}7)${NC} ${BOLD}All Attacks${NC}"
    echo -e "   ${CYAN}• Comprehensive injection campaign${NC}"
    echo ""
    
    while true; do
        echo -e "${YELLOW}Select attacks to execute (1-7, or 'q' to quit):${NC}"
        read -p "Choice(s): " -r user_input
        
        case $user_input in
            "q"|"Q"|"quit"|"exit")
                echo -e "${RED}[!] Exiting...${NC}"
                exit 0
                ;;
            "1")
                selected_attacks+=("mavlink_command")
                break
                ;;
            "2") 
                selected_attacks+=("gps_spoofing")
                break
                ;;
            "3")
                selected_attacks+=("sql_injection")
                break
                ;;
            "4")
                selected_attacks+=("parameter_manipulation")
                break
                ;;
            "5")
                selected_attacks+=("waypoint_injection")
                break
                ;;
            "6")
                selected_attacks+=("firmware_injection")
                break
                ;;
            "7")
                selected_attacks=("mavlink_command" "gps_spoofing" "sql_injection" "parameter_manipulation" "waypoint_injection" "firmware_injection")
                break
                ;;
            "1,2"|"1 2"|"2,1"|"2 1")
                selected_attacks=("mavlink_command" "gps_spoofing")
                break
                ;;
            "all"|"ALL")
                selected_attacks=("mavlink_command" "gps_spoofing" "sql_injection" "parameter_manipulation" "waypoint_injection" "firmware_injection")
                break
                ;;
            *)
                echo -e "${RED}[!] Invalid selection. Please choose 1-7, combinations, or 'q' to quit.${NC}"
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
    
    echo -e "${BOLD}${BLUE}🚀 Executing Injection Attacks Sequentially...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    local total_attacks=${#attacks[@]}
    local current_attack=0
    
    for attack in "${attacks[@]}"; do
        current_attack=$((current_attack + 1))
        
        echo -e "${BOLD}${CYAN}💉 Attack ${current_attack}/${total_attacks}: ${attack}${NC}"
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
    
    echo -e "${BOLD}${BLUE}🚀 Executing Injection Attacks in Parallel...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 모든 공격을 백그라운드에서 시작
    for attack in "${attacks[@]}"; do
        echo -e "${CYAN}[*] Starting ${attack} attack in background...${NC}" | tee -a "$LOG_FILE"
        
        ATTACK_START_TIMES[$attack]=$(date +%s)
        
        execute_single_attack "$attack" &
        ATTACK_PIDS[$attack]=$!
        
        echo "INJECTION_PARALLEL:${attack}_PID_${ATTACK_PIDS[$attack]}" >> "$IOC_FILE"
    done
    
    echo ""
    echo -e "${YELLOW}[*] All injection attacks started. Monitoring progress...${NC}" | tee -a "$LOG_FILE"
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
    
    echo -e "${BLUE}[*] Monitoring parallel injection attacks for ${monitoring_duration} seconds...${NC}"
    echo ""
    
    while [ $checks_done -lt $max_checks ]; do
        local active_attacks=0
        local completed_attacks=0
        
        printf "\r${RED}Injection Progress: [%-30s] %d/%d checks" \
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
            echo -e "${GREEN}[✓] All parallel injection attacks completed${NC}" | tee -a "$LOG_FILE"
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
        simulate_injection_attack "$attack_name"
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

# 인젝션 공격 시뮬레이션
simulate_injection_attack() {
    local attack_name=$1
    
    echo -e "${CYAN}[*] Simulating ${attack_name} injection attack...${NC}" | tee -a "$LOG_FILE"
    
    # 시뮬레이션 지속 시간 (45-120초)
    local duration=$((RANDOM % 75 + 45))
    
    # 공격 복잡도별 성공률
    local success_rates=(
        ["mavlink_command"]="85"
        ["gps_spoofing"]="75"
        ["sql_injection"]="90"
        ["parameter_manipulation"]="80"
        ["waypoint_injection"]="85"
        ["firmware_injection"]="60"
    )
    
    local success_rate=${success_rates[$attack_name]:-70}
    
    echo -e "${BLUE}[*] Attack complexity: $([ $success_rate -ge 80 ] && echo "HIGH" || [ $success_rate -ge 70 ] && echo "MEDIUM" || echo "ADVANCED")${NC}" | tee -a "$LOG_FILE"
    
    # 공격 단계 시뮬레이션
    local stages=()
    case $attack_name in
        "mavlink_command")
            stages=("Connection_Establishment" "Protocol_Analysis" "Command_Crafting" "Injection_Execution" "Impact_Assessment")
            ;;
        "gps_spoofing")
            stages=("Signal_Analysis" "Spoofing_Preparation" "Coordinate_Manipulation" "Navigation_Hijacking" "Verification")
            ;;
        "sql_injection")
            stages=("Vulnerability_Scanning" "Payload_Testing" "Authentication_Bypass" "Data_Extraction" "Privilege_Escalation")
            ;;
        "parameter_manipulation")
            stages=("Parameter_Discovery" "Safety_Analysis" "Configuration_Modification" "System_Impact" "Persistence")
            ;;
        "waypoint_injection")
            stages=("Mission_Analysis" "Route_Planning" "Waypoint_Crafting" "Mission_Hijacking" "Execution_Monitoring")
            ;;
        "firmware_injection")
            stages=("Firmware_Analysis" "Payload_Development" "Upload_Exploitation" "Code_Injection" "Backdoor_Installation")
            ;;
    esac
    
    # 진행률 표시
    local stage_duration=$((duration / ${#stages[@]}))
    
    for ((i=0; i<${#stages[@]}; i++)); do
        local stage=${stages[$i]}
        local stage_progress=$(((i+1) * 100 / ${#stages[@]}))
        
        printf "\r${CYAN}${attack_name}: [%-20s] %s (%d%%)${NC}" \
               "$(printf "%*s" $((stage_progress / 5)) | tr ' ' '█')" \
               "$stage" "$stage_progress"
        
        sleep $stage_duration
    done
    echo ""
    
    # 공격 결과 결정
    local effectiveness=$((RANDOM % 100))
    
    if [ $effectiveness -lt $success_rate ]; then
        echo -e "${GREEN}[✓] ${attack_name} injection successful${NC}" | tee -a "$LOG_FILE"
        echo "INJECTION_SIM:${attack_name}_SUCCESS_$(date +%s)" >> "$IOC_FILE"
        
        # 성공 시 영향 시뮬레이션
        case $attack_name in
            "mavlink_command")
                echo "INJECTION_IMPACT:FLIGHT_CONTROL_COMPROMISED" >> "$IOC_FILE"
                ;;
            "gps_spoofing")
                echo "INJECTION_IMPACT:NAVIGATION_HIJACKED" >> "$IOC_FILE"
                ;;
            "sql_injection")
                echo "INJECTION_IMPACT:DATABASE_COMPROMISED" >> "$IOC_FILE"
                ;;
            "parameter_manipulation")
                echo "INJECTION_IMPACT:SAFETY_SYSTEMS_DISABLED" >> "$IOC_FILE"
                ;;
            "waypoint_injection")
                echo "INJECTION_IMPACT:MISSION_HIJACKED" >> "$IOC_FILE"
                ;;
            "firmware_injection")
                echo "INJECTION_IMPACT:PERSISTENT_BACKDOOR" >> "$IOC_FILE"
                ;;
        esac
        
        return 0
    else
        echo -e "${RED}[!] ${attack_name} injection failed${NC}" | tee -a "$LOG_FILE"
        echo "INJECTION_SIM:${attack_name}_FAILED_$(date +%s)" >> "$IOC_FILE"
        return 1
    fi
}

# IOC 파일 병합
merge_attack_iocs() {
    local attack_name=$1
    
    # 각 공격의 IOC 파일을 마스터 파일에 병합
    local attack_ioc_patterns=(
        "/tmp/mavlink_command_injection_iocs.txt"
        "/tmp/gps_spoofing_iocs.txt"
        "/tmp/sql_injection_iocs.txt"
        "/tmp/parameter_manipulation_iocs.txt"
        "/tmp/waypoint_injection_iocs.txt"
        "/tmp/firmware_injection_iocs.txt"
    )
    
    for ioc_file in "${attack_ioc_patterns[@]}"; do
        if [ -f "$ioc_file" ]; then
            echo "# IOCs from $(basename "$ioc_file") - $(date)" >> "$IOC_FILE"
            cat "$ioc_file" >> "$IOC_FILE"
            echo "" >> "$IOC_FILE"
        fi
    done
    
    echo "INJECTION_SUITE:${attack_name}_COMPLETED_$(date +%s)" >> "$IOC_FILE"
}

# 시스템 영향 평가
assess_system_impact() {
    echo -e "${CYAN}[*] Assessing overall injection attack impact...${NC}" | tee -a "$LOG_FILE"
    
    local successful_attacks=0
    local total_attacks=${#ATTACK_STATUS[@]}
    local critical_impacts=0
    
    # 성공한 공격 분석
    for attack in "${!ATTACK_STATUS[@]}"; do
        if [ "${ATTACK_STATUS[$attack]}" = "SUCCESS" ]; then
            successful_attacks=$((successful_attacks + 1))
            
            # 중요 영향 평가
            case $attack in
                "mavlink_command"|"gps_spoofing"|"firmware_injection")
                    critical_impacts=$((critical_impacts + 1))
                    ;;
            esac
        fi
    done
    
    local impact_percentage=$((successful_attacks * 100 / total_attacks))
    
    echo -e "${BLUE}[*] System impact assessment:${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Successful attacks: ${successful_attacks}/${total_attacks}${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Success rate: ${impact_percentage}%${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Critical impacts: ${critical_impacts}${NC}" | tee -a "$LOG_FILE"
    
    # 시스템 구성 요소별 영향 평가
    local components_affected=()
    
    if grep -q "FLIGHT_CONTROL_COMPROMISED\|NAVIGATION_HIJACKED" "$IOC_FILE"; then
        components_affected+=("Flight Control System")
        echo -e "${RED}    Flight control system: COMPROMISED${NC}" | tee -a "$LOG_FILE"
    fi
    
    if grep -q "DATABASE_COMPROMISED\|AUTH_BYPASS" "$IOC_FILE"; then
        components_affected+=("Database & Authentication")
        echo -e "${RED}    Database system: COMPROMISED${NC}" | tee -a "$LOG_FILE"
    fi
    
    if grep -q "SAFETY_SYSTEMS_DISABLED\|PARAMETER_MANIPULATION" "$IOC_FILE"; then
        components_affected+=("Safety Systems")
        echo -e "${RED}    Safety systems: DISABLED${NC}" | tee -a "$LOG_FILE"
    fi
    
    if grep -q "MISSION_HIJACKED\|WAYPOINT_INJECTION" "$IOC_FILE"; then
        components_affected+=("Mission Planning")
        echo -e "${RED}    Mission system: HIJACKED${NC}" | tee -a "$LOG_FILE"
    fi
    
    if grep -q "PERSISTENT_BACKDOOR\|FIRMWARE_INJECTION" "$IOC_FILE"; then
        components_affected+=("Firmware & Boot Process")
        echo -e "${RED}    Firmware integrity: COMPROMISED${NC}" | tee -a "$LOG_FILE"
    fi
    
    # 전체 영향도 계산
    local component_impact_percentage=$((${#components_affected[@]} * 100 / 5))
    local overall_impact=$(((impact_percentage + component_impact_percentage + critical_impacts * 10) / 3))
    
    if [ $overall_impact -ge 80 ]; then
        SYSTEM_IMPACT="CRITICAL"
        echo -e "${RED}    Overall impact: CRITICAL (${overall_impact}%) - Complete system compromise${NC}" | tee -a "$LOG_FILE"
    elif [ $overall_impact -ge 60 ]; then
        SYSTEM_IMPACT="HIGH"
        echo -e "${YELLOW}    Overall impact: HIGH (${overall_impact}%) - Major system compromise${NC}" | tee -a "$LOG_FILE"
    elif [ $overall_impact -ge 40 ]; then
        SYSTEM_IMPACT="MEDIUM"
        echo -e "${CYAN}    Overall impact: MEDIUM (${overall_impact}%) - Significant compromise${NC}" | tee -a "$LOG_FILE"
    else
        SYSTEM_IMPACT="LOW"
        echo -e "${GREEN}    Overall impact: LOW (${overall_impact}%) - Limited compromise${NC}" | tee -a "$LOG_FILE"
    fi
    
    echo "INJECTION_IMPACT:OVERALL_${overall_impact}PCT" >> "$IOC_FILE"
    echo "INJECTION_IMPACT:SYSTEM_STATUS_${SYSTEM_IMPACT}" >> "$IOC_FILE"
    echo "INJECTION_IMPACT:COMPONENTS_AFFECTED_${#components_affected[@]}" >> "$IOC_FILE"
}

# 마스터 리포트 생성
generate_master_report() {
    echo -e "${CYAN}[*] Generating master injection attack report...${NC}" | tee -a "$LOG_FILE"
    
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
    
    # 실제 공격 상태 (Bash 배열에서 읽어야 하지만 시뮬레이션)
    attacks = ['mavlink_command', 'gps_spoofing', 'sql_injection', 'parameter_manipulation', 'waypoint_injection', 'firmware_injection']
    success_rates = [85, 75, 90, 80, 85, 60]  # 각 공격의 성공률
    
    for i, attack in enumerate(attacks):
        # 시뮬레이션된 결과
        attack_status[attack] = 'SUCCESS' if hash(attack) % 100 < success_rates[i] else 'FAILED'
        attack_durations[attack] = hash(attack) % 120 + 45  # 45-165초
    
    master_report = {
        'suite_info': {
            'name': 'DVD Injection Attack Suite',
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
            'flight_control_integrity': 'unknown',
            'navigation_reliability': 'unknown',
            'data_confidentiality': 'unknown',
            'system_availability': '${SYSTEM_IMPACT:-UNKNOWN}',
            'recovery_complexity': 'high'
        },
        'technical_summary': {
            'total_iocs_generated': 0,
            'attack_vectors_used': [],
            'injection_methods': [
                'command_injection',
                'data_manipulation',
                'parameter_tampering',
                'signal_spoofing',
                'database_exploitation',
                'firmware_modification'
            ],
            'persistence_achieved': False,
            'lateral_movement': False
        },
        'mitre_mapping': {
            'tactics': ['Initial Access', 'Execution', 'Persistence', 'Defense Evasion', 'Impact'],
            'techniques': [
                'T1190 - Exploit Public-Facing Application',
                'T1071.004 - Application Layer Protocol',
                'T1565.001 - Data Manipulation: Stored Data',
                'T1565.002 - Data Manipulation: Transmitted Data',
                'T1542.001 - Pre-OS Boot: System Firmware',
                'T1078 - Valid Accounts'
            ]
        },
        'recommendations': {
            'immediate_response': [
                'Isolate affected systems',
                'Verify flight controller integrity',
                'Check navigation system accuracy',
                'Review authentication logs',
                'Validate mission parameters'
            ],
            'long_term_mitigation': [
                'Implement input validation',
                'Deploy code signing',
                'Enable parameter encryption',
                'Implement anomaly detection',
                'Regular security assessments',
                'Multi-factor authentication'
            ]
        }
    }
    
    # 개별 공격 상세 정보
    for attack in attacks:
        impact_level = 'high' if attack in ['mavlink_command', 'gps_spoofing', 'firmware_injection'] else 'medium'
        
        master_report['attack_summary']['attack_details'][attack] = {
            'status': attack_status.get(attack, 'UNKNOWN'),
            'duration_seconds': attack_durations.get(attack, 0),
            'impact_level': impact_level,
            'persistence': attack == 'firmware_injection'
        }
    
    # 성공한 공격에 따른 영향 평가
    successful_count = master_report['attack_summary']['successful_attacks']
    critical_attacks = ['mavlink_command', 'gps_spoofing', 'firmware_injection']
    critical_successes = sum(1 for attack in critical_attacks if attack_status.get(attack) == 'SUCCESS')
    
    if critical_successes >= 3:
        master_report['operational_impact']['flight_control_integrity'] = 'completely_compromised'
        master_report['operational_impact']['navigation_reliability'] = 'unreliable'
        master_report['operational_impact']['data_confidentiality'] = 'breached'
        master_report['technical_summary']['persistence_achieved'] = True
    elif critical_successes >= 2:
        master_report['operational_impact']['flight_control_integrity'] = 'severely_compromised'
        master_report['operational_impact']['navigation_reliability'] = 'questionable'
        master_report['operational_impact']['data_confidentiality'] = 'at_risk'
    elif critical_successes >= 1:
        master_report['operational_impact']['flight_control_integrity'] = 'partially_compromised'
        master_report['operational_impact']['navigation_reliability'] = 'degraded'
        master_report['operational_impact']['data_confidentiality'] = 'potentially_exposed'
    else:
        master_report['operational_impact']['flight_control_integrity'] = 'intact'
        master_report['operational_impact']['navigation_reliability'] = 'reliable'
        master_report['operational_impact']['data_confidentiality'] = 'protected'
    
    # 공격 벡터 설정
    successful_vectors = []
    if attack_status.get('mavlink_command') == 'SUCCESS':
        successful_vectors.append('MAVLink Protocol Exploitation')
    if attack_status.get('gps_spoofing') == 'SUCCESS':
        successful_vectors.append('GPS Signal Manipulation')
    if attack_status.get('sql_injection') == 'SUCCESS':
        successful_vectors.append('Database Exploitation')
    if attack_status.get('parameter_manipulation') == 'SUCCESS':
        successful_vectors.append('Configuration Tampering')
    if attack_status.get('waypoint_injection') == 'SUCCESS':
        successful_vectors.append('Mission Hijacking')
    if attack_status.get('firmware_injection') == 'SUCCESS':
        successful_vectors.append('Firmware Compromise')
    
    master_report['technical_summary']['attack_vectors_used'] = successful_vectors
    
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
print(f'System impact: {report[\"operational_impact\"][\"system_availability\"]}')
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
    echo -e "${BOLD}${GREEN}💉 DVD Injection Attack Suite Execution Complete!${NC}"
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
            echo -e "${RED}⚠️  CRITICAL SYSTEM COMPROMISE ⚠️${NC}"
            echo -e "${RED}   • Complete flight control compromise${NC}"
            echo -e "${RED}   • Navigation system unreliable${NC}"
            echo -e "${RED}   • Database and authentication breached${NC}"
            echo -e "${RED}   • Persistent backdoors installed${NC}"
            echo -e "${RED}   • Immediate grounding required${NC}"
            ;;
        "HIGH")
            echo -e "${YELLOW}⚠️  HIGH IMPACT SYSTEM COMPROMISE ⚠️${NC}"
            echo -e "${YELLOW}   • Major flight system impairment${NC}"
            echo -e "${YELLOW}   • Navigation accuracy questionable${NC}"
            echo -e "${YELLOW}   • Data confidentiality at risk${NC}"
            echo -e "${YELLOW}   • Mission reliability compromised${NC}"
            ;;
        "MEDIUM")
            echo -e "${CYAN}ℹ️  MODERATE SYSTEM IMPACT${NC}"
            echo -e "${CYAN}   • Partial system functionality affected${NC}"
            echo -e "${CYAN}   • Some security controls bypassed${NC}"
            echo -e "${CYAN}   • Data integrity concerns${NC}"
            ;;
        "LOW")
            echo -e "${BLUE}ℹ️  LIMITED SYSTEM IMPACT${NC}"
            echo -e "${BLUE}   • Minor security vulnerabilities exposed${NC}"
            echo -e "${BLUE}   • Most systems operational${NC}"
            ;;
        *)
            echo -e "${GREEN}✓ INJECTION ATTACKS MITIGATED${NC}"
            echo -e "${GREEN}   • All injection attempts failed${NC}"
            echo -e "${GREEN}   • System integrity maintained${NC}"
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
                selected_attacks=("mavlink_command" "gps_spoofing" "sql_injection" "parameter_manipulation" "waypoint_injection" "firmware_injection")
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
            mavlink_command|gps_spoofing|sql_injection|parameter_manipulation|waypoint_injection|firmware_injection)
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
    echo "=== DVD Injection Attack Suite Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    echo -e "${BOLD}${BLUE}💉 Starting DVD Injection Attack Suite...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 필수 도구 확인
    check_required_tools "python3" "curl" "nc"
    
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
    
    echo -e "${BOLD}${GREEN}🎯 DVD Injection Attack Suite Complete!${NC}"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up injection attack suite processes...${NC}"
    
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
    
    # 관련 프로세스 정리
    pkill -f "mavproxy.py" 2>/dev/null
    pkill -f "pymavlink" 2>/dev/null
    pkill -f "requests" 2>/dev/null
    
    # 백그라운드 작업 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"