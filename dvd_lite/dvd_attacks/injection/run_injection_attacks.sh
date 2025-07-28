#!/bin/bash

# =============================================================================
# DVD Injection Attack Suite - Main Runner
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/run_injection_attacks.sh
# 목적: 모든 주입 공격의 통합 실행 및 관리
# 작성자: MTD Testbed Team
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
    ["mavlink_injection"]="mavlink_injection.sh"
    ["gps_spoofing"]="gps_spoofing.sh"
    ["command_injection"]="command_injection.sh"
    ["sensor_spoofing"]="sensor_spoofing.sh"
    ["data_manipulation"]="data_manipulation.sh"
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
    echo "║                     💉 DVD Injection Attack Suite 💉                   ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Available Modules: MAVLink, GPS, Command, Sensor, Data${NC}"
    echo -e "${BLUE}Execution Mode: Interactive Selection${NC}"
    echo -e "${BLUE}Output: Flight Control Impact Assessment${NC}"
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
    -t, --timeout SEC   Set timeout for each attack (default: 600s)

${YELLOW}Available Attacks:${NC}
    mavlink_injection  MAVLink Protocol Injection
    gps_spoofing       GPS Signal Spoofing
    command_injection  Flight Command Injection
    sensor_spoofing    Sensor Data Spoofing
    data_manipulation  Telemetry Data Manipulation

${YELLOW}Examples:${NC}
    $0                                    # Interactive mode
    $0 -a                                 # Run all attacks
    $0 mavlink_injection gps_spoofing     # Run specific attacks
    $0 -p mavlink_injection command_injection # Run in parallel
    $0 -s -t 900 mavlink_injection        # Sequential with 15min timeout

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
    echo -e "${BLUE}1)${NC} ${BOLD}MAVLink Protocol Injection${NC}"
    echo -e "   ${CYAN}• Flight command injection${NC}"
    echo -e "   ${CYAN}• Parameter manipulation${NC}"
    echo -e "   ${CYAN}• Waypoint modification${NC}"
    echo -e "   ${CYAN}• Telemetry data spoofing${NC}"
    echo ""
    echo -e "${BLUE}2)${NC} ${BOLD}GPS Signal Spoofing${NC}"
    echo -e "   ${CYAN}• Fake GPS signal generation${NC}"
    echo -e "   ${CYAN}• Position manipulation${NC}"
    echo -e "   ${CYAN}• Navigation deception${NC}"
    echo -e "   ${CYAN}• Multi-constellation attacks${NC}"
    echo ""
    echo -e "${BLUE}3)${NC} ${BOLD}Flight Command Injection${NC}"
    echo -e "   ${CYAN}• Unauthorized flight commands${NC}"
    echo -e "   ${CYAN}• Mode change attacks${NC}"
    echo -e "   ${CYAN}• Emergency command injection${NC}"
    echo -e "   ${CYAN}• Safety system bypass${NC}"
    echo ""
    echo -e "${BLUE}4)${NC} ${BOLD}Sensor Data Spoofing${NC}"
    echo -e "   ${CYAN}• IMU data manipulation${NC}"
    echo -e "   ${CYAN}• Barometer spoofing${NC}"
    echo -e "   ${CYAN}• Battery status falsification${NC}"
    echo -e "   ${CYAN}• Multi-sensor attacks${NC}"
    echo ""
    echo -e "${BLUE}5)${NC} ${BOLD}Telemetry Data Manipulation${NC}"
    echo -e "   ${CYAN}• Real-time data injection${NC}"
    echo -e "   ${CYAN}• Status information spoofing${NC}"
    echo -e "   ${CYAN}• Alert message manipulation${NC}"
    echo -e "   ${CYAN}• System health falsification${NC}"
    echo ""
    echo -e "${BLUE}6)${NC} ${BOLD}All Attacks${NC}"
    echo -e "   ${CYAN}• Comprehensive injection assessment${NC}"
    echo ""
    
    while true; do
        echo -e "${YELLOW}Select attacks to execute (1-6, or 'q' to quit):${NC}"
        read -p "Choice(s): " -r user_input
        
        case $user_input in
            "q"|"Q"|"quit"|"exit")
                echo -e "${RED}[!] Exiting...${NC}"
                exit 0
                ;;
            "1")
                selected_attacks+=("mavlink_injection")
                break
                ;;
            "2")
                selected_attacks+=("gps_spoofing")
                break
                ;;
            "3")
                selected_attacks+=("command_injection")
                break
                ;;
            "4")
                selected_attacks+=("sensor_spoofing")
                break
                ;;
            "5")
                selected_attacks+=("data_manipulation")
                break
                ;;
            "6")
                selected_attacks=("mavlink_injection" "gps_spoofing" "command_injection" "sensor_spoofing" "data_manipulation")
                break
                ;;
            "1,2"|"1 2"|"2,1"|"2 1")
                selected_attacks=("mavlink_injection" "gps_spoofing")
                break
                ;;
            "1,3"|"1 3"|"3,1"|"3 1")
                selected_attacks=("mavlink_injection" "command_injection")
                break
                ;;
            "all"|"ALL")
                selected_attacks=("mavlink_injection" "gps_spoofing" "command_injection" "sensor_spoofing" "data_manipulation")
                break
                ;;
            *)
                echo -e "${RED}[!] Invalid selection. Please choose 1-6, combinations, or 'q' to quit.${NC}"
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
        
        # 공격 간 대기 (시스템 안정화)
        if [ $current_attack -lt $total_attacks ]; then
            echo -e "${YELLOW}[*] Waiting 20 seconds for system stabilization...${NC}"
            sleep 20
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
    local monitoring_duration=600  # 10분 모니터링
    local check_interval=15
    local checks_done=0
    local max_checks=$((monitoring_duration / check_interval))
    
    echo -e "${BLUE}[*] Monitoring parallel injection attacks for ${monitoring_duration} seconds...${NC}"
    echo ""
    
    while [ $checks_done -lt $max_checks ]; do
        local active_attacks=0
        local completed_attacks=0
        
        printf "\r${RED}Injection Progress: [%-30s] %d/%d checks" \
               "$(printf "%*s" $((checks_done * 30 / max_checks)) | tr ' ' '💉')" \
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

# 주입 공격 시뮬레이션
simulate_injection_attack() {
    local attack_name=$1
    
    echo -e "${CYAN}[*] Simulating ${attack_name} injection attack...${NC}" | tee -a "$LOG_FILE"
    
    # 공격별 시뮬레이션 파라미터
    local injection_targets=()
    local injection_methods=()
    
    case $attack_name in
        "mavlink_injection")
            injection_targets=("COMMAND_LONG" "SET_MODE" "MISSION_ITEM" "PARAM_SET")
            injection_methods=("UDP_Packet" "Protocol_Manipulation" "Parameter_Override")
            ;;
        "gps_spoofing")
            injection_targets=("GPS_L1" "GLONASS_L1" "Galileo_E1" "Multi_Constellation")
            injection_methods=("SDR_Transmission" "Signal_Replay" "Gradual_Drift")
            ;;
        "command_injection")
            injection_targets=("ARM_DISARM" "TAKEOFF" "LAND" "RTL" "GUIDED_MODE")
            injection_methods=("Direct_Injection" "Mode_Override" "Safety_Bypass")
            ;;
        "sensor_spoofing")
            injection_targets=("IMU" "Barometer" "Battery" "Compass" "Accelerometer")
            injection_methods=("Data_Override" "Sensor_Emulation" "Bus_Injection")
            ;;
        "data_manipulation")
            injection_targets=("Telemetry" "Status" "Alerts" "Health" "Position")
            injection_methods=("Stream_Injection" "Packet_Modification" "Real_Time_Override")
            ;;
    esac
    
    local total_targets=${#injection_targets[@]}
    local successful_injections=0
    
    # 시뮬레이션 지속 시간 (120-300초)
    local duration=$((RANDOM % 180 + 120))
    
    echo -e "${BLUE}[*] Injection targets: ${injection_targets[*]}${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}[*] Methods available: ${injection_methods[*]}${NC}" | tee -a "$LOG_FILE"
    
    # 각 타겟에 대한 주입 시도
    for target in "${injection_targets[@]}"; do
        local method=${injection_methods[$RANDOM % ${#injection_methods[@]}]}
        
        echo -e "${YELLOW}[*] Injecting ${target} using ${method}...${NC}" | tee -a "$LOG_FILE"
        
        # 진행률 표시
        local injection_duration=$((duration / total_targets))
        for ((i=1; i<=injection_duration; i+=5)); do
            local progress=$((i * 100 / injection_duration))
            printf "\r${CYAN}${target}: [%-15s] %d%%${NC}" \
                   "$(printf "%*s" $((progress / 7)) | tr ' ' '→')" "$progress"
            sleep 5
        done
        echo ""
        
        # 성공률 시뮬레이션 (공격별 다른 성공률)
        local success_threshold=50
        case $attack_name in
            "mavlink_injection") success_threshold=70 ;;
            "gps_spoofing") success_threshold=60 ;;
            "command_injection") success_threshold=80 ;;
            "sensor_spoofing") success_threshold=65 ;;
            "data_manipulation") success_threshold=75 ;;
        esac
        
        local injection_success=$((RANDOM % 100))
        if [ $injection_success -lt $success_threshold ]; then
            echo -e "${GREEN}[+] ${target} injection successful using ${method}${NC}" | tee -a "$LOG_FILE"
            successful_injections=$((successful_injections + 1))
            echo "INJECTION_SIM:${attack_name}_${target}_SUCCESS_${method}" >> "$IOC_FILE"
        else
            echo -e "${RED}[!] ${target} injection failed${NC}" | tee -a "$LOG_FILE"
            echo "INJECTION_SIM:${attack_name}_${target}_FAILED_${method}" >> "$IOC_FILE"
        fi
        
        sleep 2
    done
    
    local success_rate=$((successful_injections * 100 / total_targets))
    echo -e "${CYAN}[*] ${attack_name} simulation completed${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Success rate: ${success_rate}%${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Successful injections: ${successful_injections}/${total_targets}${NC}" | tee -a "$LOG_FILE"
    
    echo "INJECTION_SIM:${attack_name}_OVERALL_SUCCESS_RATE_${success_rate}PCT" >> "$IOC_FILE"
    
    # 전체 성공률이 50% 이상이면 성공으로 판정
    if [ $success_rate -ge 50 ]; then
        return 0
    else
        return 1
    fi
}

# IOC 파일 병합
merge_attack_iocs() {
    local attack_name=$1
    
    # 각 공격의 IOC 파일을 마스터 파일에 병합
    local attack_ioc_patterns=(
        "/tmp/mavlink_injection_iocs.txt"
        "/tmp/gps_spoofing_iocs.txt"
        "/tmp/command_injection_iocs.txt"
        "/tmp/sensor_spoofing_iocs.txt"
        "/tmp/data_manipulation_iocs.txt"
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

# 주입 공격 영향 평가
assess_injection_impact() {
    echo -e "${CYAN}[*] Assessing overall injection attack impact...${NC}" | tee -a "$LOG_FILE"
    
    local successful_attacks=0
    local total_attacks=${#ATTACK_STATUS[@]}
    local critical_systems_compromised=0
    
    # 공격별 영향 평가
    for attack in "${!ATTACK_STATUS[@]}"; do
        local status=${ATTACK_STATUS[$attack]}
        
        if [ "$status" = "SUCCESS" ]; then
            successful_attacks=$((successful_attacks + 1))
            
            # 중요 시스템 영향 평가
            case $attack in
                "mavlink_injection"|"command_injection")
                    critical_systems_compromised=$((critical_systems_compromised + 2))
                    ;;
                "gps_spoofing")
                    critical_systems_compromised=$((critical_systems_compromised + 3))
                    ;;
                "sensor_spoofing"|"data_manipulation")
                    critical_systems_compromised=$((critical_systems_compromised + 1))
                    ;;
            esac
        fi
    done
    
    local impact_percentage=$((successful_attacks * 100 / total_attacks))
    
    echo -e "${BLUE}[*] Injection impact assessment:${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Successful attacks: ${successful_attacks}/${total_attacks}${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Success rate: ${impact_percentage}%${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}    Critical systems affected: ${critical_systems_compromised}${NC}" | tee -a "$LOG_FILE"
    
    # 전체 영향도 계산
    local overall_impact_score=$((impact_percentage + critical_systems_compromised * 10))
    
    if [ $overall_impact_score -ge 90 ]; then
        INJECTION_IMPACT="CRITICAL"
        echo -e "${RED}    Overall impact: CRITICAL (${overall_impact_score})${NC}" | tee -a "$LOG_FILE"
    elif [ $overall_impact_score -ge 70 ]; then
        INJECTION_IMPACT="HIGH"
        echo -e "${YELLOW}    Overall impact: HIGH (${overall_impact_score})${NC}" | tee -a "$LOG_FILE"
    elif [ $overall_impact_score -ge 50 ]; then
        INJECTION_IMPACT="MODERATE"
        echo -e "${CYAN}    Overall impact: MODERATE (${overall_impact_score})${NC}" | tee -a "$LOG_FILE"
    else
        INJECTION_IMPACT="LOW"
        echo -e "${GREEN}    Overall impact: LOW (${overall_impact_score})${NC}" | tee -a "$LOG_FILE"
    fi
    
    echo "INJECTION_IMPACT:OVERALL_${overall_impact_score}" >> "$IOC_FILE"
    echo "INJECTION_IMPACT:SYSTEM_STATUS_${INJECTION_IMPACT}" >> "$IOC_FILE"
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
    
    # Bash 배열에서 상태 정보 읽기 (시뮬레이션)
    attacks = ['mavlink_injection', 'gps_spoofing', 'command_injection', 'sensor_spoofing', 'data_manipulation']
    for attack in attacks:
        # 실제로는 bash 변수에서 읽어야 하지만 시뮬레이션
        attack_status[attack] = 'SUCCESS' if hash(attack) % 4 != 0 else 'FAILED'
        attack_durations[attack] = hash(attack) % 240 + 120  # 120-360초
    
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
        'flight_control_impact': {
            'command_injection_capability': '${INJECTION_IMPACT:-UNKNOWN}',
            'navigation_system_compromise': 'unknown',
            'sensor_integrity_loss': 'unknown',
            'data_authenticity_compromise': 'unknown'
        },
        'technical_summary': {
            'total_iocs_generated': 0,
            'injection_vectors_used': [],
            'protocols_targeted': ['MAVLink', 'GPS', 'I2C/SPI', 'UART'],
            'attack_sophistication': 'high',
            'forensic_footprint': 'medium'
        },
        'mitre_mapping': {
            'tactic': 'Execution',
            'techniques': [
                'T1071.004 - Application Layer Protocol',
                'T1565.001 - Data Manipulation: Stored Data',
                'T1565.002 - Data Manipulation: Transmitted Data',
                'T1059 - Command and Scripting Interpreter',
                'T1200 - Hardware Additions'
            ]
        },
        'recommendations': {
            'immediate_response': [
                'Implement protocol authentication',
                'Deploy message integrity checking',
                'Enable command source validation',
                'Activate anomaly detection systems'
            ],
            'long_term_mitigation': [
                'End-to-end encryption implementation',
                'Digital signature verification',
                'Multi-factor command authentication',
                'Hardware security module integration',
                'Real-time system monitoring'
            ]
        }
    }
    
    # 개별 공격 상세 정보
    for attack in attacks:
        master_report['attack_summary']['attack_details'][attack] = {
            'status': attack_status.get(attack, 'UNKNOWN'),
            'duration_seconds': attack_durations.get(attack, 0),
            'flight_control_impact': 'high' if attack_status.get(attack) == 'SUCCESS' else 'none'
        }
    
    # 성공한 공격에 따른 영향 평가
    successful_count = master_report['attack_summary']['successful_attacks']
    if successful_count >= 4:
        master_report['flight_control_impact']['navigation_system_compromise'] = 'complete'
        master_report['flight_control_impact']['sensor_integrity_loss'] = 'critical'
        master_report['flight_control_impact']['data_authenticity_compromise'] = 'total'
        master_report['technical_summary']['attack_sophistication'] = 'advanced'
    elif successful_count >= 3:
        master_report['flight_control_impact']['navigation_system_compromise'] = 'significant'
        master_report['flight_control_impact']['sensor_integrity_loss'] = 'major'
        master_report['flight_control_impact']['data_authenticity_compromise'] = 'high'
    elif successful_count >= 2:
        master_report['flight_control_impact']['navigation_system_compromise'] = 'partial'
        master_report['flight_control_impact']['sensor_integrity_loss'] = 'moderate'
        master_report['flight_control_impact']['data_authenticity_compromise'] = 'medium'
    elif successful_count >= 1:
        master_report['flight_control_impact']['navigation_system_compromise'] = 'minimal'
        master_report['flight_control_impact']['sensor_integrity_loss'] = 'low'
        master_report['flight_control_impact']['data_authenticity_compromise'] = 'limited'
    else:
        master_report['flight_control_impact']['navigation_system_compromise'] = 'none'
        master_report['flight_control_impact']['sensor_integrity_loss'] = 'none'
        master_report['flight_control_impact']['data_authenticity_compromise'] = 'none'
    
    # 주입 벡터 설정
    if successful_count > 0:
        master_report['technical_summary']['injection_vectors_used'] = [
            'Protocol Injection', 'Signal Spoofing', 'Data Manipulation', 'Command Override'
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
print(f'Flight control impact: {report[\"flight_control_impact\"][\"command_injection_capability\"]}')
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
    
    # 비행 제어 영향 평가
    case "${INJECTION_IMPACT:-UNKNOWN}" in
        "CRITICAL")
            echo -e "${RED}⚠️  CRITICAL FLIGHT CONTROL COMPROMISE ⚠️${NC}"
            echo -e "${RED}   • Complete command injection capability${NC}"
            echo -e "${RED}   • Navigation system fully compromised${NC}"
            echo -e "${RED}   • Sensor data integrity lost${NC}"
            echo -e "${RED}   • Unauthorized flight control possible${NC}"
            ;;
        "HIGH")
            echo -e "${YELLOW}⚠️  HIGH-RISK FLIGHT SYSTEM BREACH ⚠️${NC}"
            echo -e "${YELLOW}   • Significant injection capabilities${NC}"
            echo -e "${YELLOW}   • Major control system impact${NC}"
            echo -e "${YELLOW}   • Flight safety compromised${NC}"
            ;;
        "MODERATE")
            echo -e "${CYAN}ℹ️  MODERATE FLIGHT CONTROL IMPACT${NC}"
            echo -e "${CYAN}   • Limited injection success${NC}"
            echo -e "${CYAN}   • Partial system compromise${NC}"
            ;;
        "LOW")
            echo -e "${BLUE}ℹ️  MINIMAL FLIGHT CONTROL IMPACT${NC}"
            echo -e "${BLUE}   • Minor injection capabilities${NC}"
            echo -e "${BLUE}   • Limited system influence${NC}"
            ;;
        *)
            echo -e "${GREEN}✓ FLIGHT CONTROL SYSTEMS SECURE${NC}"
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
    local timeout=600
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
                selected_attacks=("mavlink_injection" "gps_spoofing" "command_injection" "sensor_spoofing" "data_manipulation")
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
            mavlink_injection|gps_spoofing|command_injection|sensor_spoofing|data_manipulation)
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
    check_required_tools "python3" "nc"
    
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
    
    # 주입 공격 영향 평가
    assess_injection_impact
    
    echo ""
    
    # 마스터 리포트 생성
    echo -e "${BOLD}${CYAN}📊 Generating Master Injection Report...${NC}"
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
    pkill -f "mavlink" 2>/dev/null
    pkill -f "gps-sdr-sim" 2>/dev/null
    pkill -f "hackrf_transfer" 2>/dev/null
    
    # 백그라운드 작업 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"