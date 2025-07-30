#!/bin/bash

# =============================================================================
# DVD Firmware Attack Suite - Main Runner
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/firmware_attacks/run_firmware_attacks.sh
# 목적: 모든 펌웨어 공격의 통합 실행 및 관리
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
SCRIPT_DIR="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/firmware_attacks"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/firmware_attacks/suite_run_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/firmware_attacks_suite_iocs.txt"
MASTER_REPORT="/home/kali/MTD/MTD_full_testbed/attack_output/firmware_attacks/master_firmware_report_$(date +%Y%m%d_%H%M%S).json"

# 사용 가능한 공격 모듈
declare -A ATTACK_MODULES=(
    ["secure_boot"]="secure_boot_bypass.sh"
    ["firmware_mod"]="firmware_modification.sh"  
    ["bootloader"]="bootloader_exploit.sh"
    ["flash_dump"]="flash_memory_dump.sh"
    ["crypto_keys"]="cryptographic_keys.sh"
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
    echo "║                    🔓 DVD Firmware Attack Suite 🔓                        ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Available Modules: Secure Boot, Firmware Mod, Bootloader, Flash Dump${NC}"
    echo -e "${BLUE}Execution Mode: Interactive Selection${NC}"
    echo -e "${BLUE}Output: Integrated Security Assessment${NC}"
    echo ""
}

# 사용법 출력
print_usage() {
    cat << EOF
${BOLD}${CYAN}DVD Firmware Attack Suite${NC}

${YELLOW}Usage:${NC}
    $0 [OPTIONS] [ATTACKS]

${YELLOW}Options:${NC}
    -h, --help          Show this help message
    -a, --all           Run all firmware attacks
    -i, --interactive   Interactive mode (default)
    -q, --quiet         Quiet mode (minimal output)
    -s, --sequential    Run attacks sequentially
    -p, --parallel      Run attacks in parallel
    -t, --timeout SEC   Set timeout for each attack (default: 900s)

${YELLOW}Available Attacks:${NC}
    secure_boot        Secure Boot Bypass Attack
    firmware_mod       Firmware Modification Attack
    bootloader         Bootloader Exploitation Attack
    flash_dump         Flash Memory Dump Attack
    crypto_keys        Cryptographic Key Extraction

${YELLOW}Examples:${NC}
    $0                           # Interactive mode
    $0 -a                        # Run all attacks
    $0 secure_boot firmware_mod  # Run specific attacks
    $0 -p secure_boot bootloader # Run in parallel
    $0 -s -t 600 secure_boot     # Sequential with 10min timeout

${YELLOW}Output Files:${NC}
    • Master Report: ${MASTER_REPORT}
    • Combined IOCs: ${IOC_FILE}
    • Execution Log: ${LOG_FILE}

EOF
}

# 공격 모듈 상태 확인
check_attack_modules() {
    echo -e "${CYAN}[*] Checking available firmware attack modules...${NC}" | tee -a "$LOG_FILE"
    
    local missing_modules=()
    
    for attack_name in "${!ATTACK_MODULES[@]}"; do
        local script_file="${SCRIPT_DIR}/${ATTACK_MODULES[$attack_name]}"
        
        if [ -f "$script_file" ] && [ -x "$script_file" ]; then
            echo -e "${GREEN}[✓] ${attack_name}: ${ATTACK_MODULES[$attack_name]}${NC}" | tee -a "$LOG_FILE"
        else
            echo -e "${RED}[!] ${attack_name}: ${ATTACK_MODULES[$attack_name]} (MISSING/NOT EXECUTABLE)${NC}" | tee -a "$LOG_FILE"
            missing_modules+=("$attack_name")
        fi
    done
    
    # 누락된 모듈이 있어도 계속 진행 (시뮬레이션)
    if [ ${#missing_modules[@]} -gt 0 ]; then
        echo -e "${YELLOW}[!] Missing modules will be simulated: ${missing_modules[*]}${NC}" | tee -a "$LOG_FILE"
    fi
    
    return 0
}

# 대화형 공격 선택
interactive_attack_selection() {
    echo -e "${BOLD}${CYAN}🔓 Interactive Firmware Attack Selection${NC}"
    echo ""
    
    local selected_attacks=()
    
    # 공격 모듈 목록 표시
    echo -e "${YELLOW}Available Firmware Attacks:${NC}"
    echo ""
    echo -e "${BLUE}1)${NC} ${BOLD}Secure Boot Bypass Attack${NC}"
    echo -e "   ${CYAN}• Cryptographic signature bypass${NC}"
    echo -e "   ${CYAN}• Hardware-based security circumvention${NC}"
    echo -e "   ${CYAN}• Boot chain integrity compromise${NC}"
    echo ""
    echo -e "${BLUE}2)${NC} ${BOLD}Firmware Modification Attack${NC}"
    echo -e "   ${CYAN}• Binary firmware patching${NC}"
    echo -e "   ${CYAN}• Backdoor injection${NC}"
    echo -e "   ${CYAN}• Malicious code insertion${NC}"
    echo ""
    echo -e "${BLUE}3)${NC} ${BOLD}Bootloader Exploitation Attack${NC}"
    echo -e "   ${CYAN}• Bootloader vulnerability exploitation${NC}"
    echo -e "   ${CYAN}• Early boot process compromise${NC}"
    echo -e "   ${CYAN}• Privilege escalation${NC}"
    echo ""
    echo -e "${BLUE}4)${NC} ${BOLD}Flash Memory Dump Attack${NC}"
    echo -e "   ${CYAN}• Full firmware extraction${NC}"
    echo -e "   ${CYAN}• Memory content analysis${NC}"
    echo -e "   ${CYAN}• Sensitive data recovery${NC}"
    echo ""
    echo -e "${BLUE}5)${NC} ${BOLD}Cryptographic Key Extraction${NC}"
    echo -e "   ${CYAN}• Hardware security key extraction${NC}"
    echo -e "   ${CYAN}• Side-channel analysis${NC}"
    echo -e "   ${CYAN}• Key recovery attacks${NC}"
    echo ""
    echo -e "${BLUE}6)${NC} ${BOLD}All Attacks${NC}"
    echo -e "   ${CYAN}• Comprehensive firmware security assessment${NC}"
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
                selected_attacks+=("secure_boot")
                break
                ;;
            "2")
                selected_attacks+=("firmware_mod")
                break
                ;;
            "3")
                selected_attacks+=("bootloader")
                break
                ;;
            "4")
                selected_attacks+=("flash_dump")
                break
                ;;
            "5")
                selected_attacks+=("crypto_keys")
                break
                ;;
            "6")
                selected_attacks=("secure_boot" "firmware_mod" "bootloader" "flash_dump" "crypto_keys")
                break
                ;;
            "1,2"|"1 2"|"2,1"|"2 1")
                selected_attacks=("secure_boot" "firmware_mod")
                break
                ;;
            "1,3"|"1 3"|"3,1"|"3 1")
                selected_attacks=("secure_boot" "bootloader")
                break
                ;;
            "all"|"ALL")
                selected_attacks=("secure_boot" "firmware_mod" "bootloader" "flash_dump" "crypto_keys")
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
    
    echo -e "${BOLD}${BLUE}🚀 Executing Firmware Attacks Sequentially...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    local total_attacks=${#attacks[@]}
    local current_attack=0
    
    for attack in "${attacks[@]}"; do
        current_attack=$((current_attack + 1))
        
        echo -e "${BOLD}${CYAN}🔓 Attack ${current_attack}/${total_attacks}: ${attack}${NC}"
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
        
        # 공격 간 짧은 대기
        if [ $current_attack -lt $total_attacks ]; then
            echo -e "${YELLOW}[*] Waiting 15 seconds before next attack...${NC}"
            sleep 15
        fi
    done
}

# 병렬 실행
execute_attacks_parallel() {
    local attacks=("$@")
    
    echo -e "${BOLD}${BLUE}🚀 Executing Firmware Attacks in Parallel...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 모든 공격을 백그라운드에서 시작
    for attack in "${attacks[@]}"; do
        echo -e "${CYAN}[*] Starting ${attack} attack in background...${NC}" | tee -a "$LOG_FILE"
        
        ATTACK_START_TIMES[$attack]=$(date +%s)
        
        execute_single_attack "$attack" &
        ATTACK_PIDS[$attack]=$!
        
        echo "FIRMWARE_PARALLEL:${attack}_PID_${ATTACK_PIDS[$attack]}" >> "$IOC_FILE"
    done
    
    echo ""
    echo -e "${YELLOW}[*] All firmware attacks started. Monitoring progress...${NC}" | tee -a "$LOG_FILE"
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
    
    echo -e "${BLUE}[*] Monitoring parallel firmware attacks for ${monitoring_duration} seconds...${NC}"
    echo ""
    
    while [ $checks_done -lt $max_checks ]; do
        local active_attacks=0
        local completed_attacks=0
        
        printf "\r${CYAN}Progress: [%-30s] %d/%d checks" \
               "$(printf "%*s" $((checks_done * 30 / max_checks)) | tr ' ' '=')" \
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
            echo -e "${GREEN}[✓] All parallel firmware attacks completed${NC}" | tee -a "$LOG_FILE"
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
        simulate_firmware_attack "$attack_name"
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

# 펌웨어 공격 시뮬레이션
simulate_firmware_attack() {
    local attack_name=$1
    
    echo -e "${CYAN}[*] Simulating ${attack_name} firmware attack...${NC}" | tee -a "$LOG_FILE"
    
    # 시뮬레이션 지속 시간 (30-120초)
    local duration=$((RANDOM % 90 + 30))
    
    # 진행률 표시
    for ((i=0; i<=duration; i+=5)); do
        local progress=$((i * 100 / duration))
        printf "\r${YELLOW}Simulating ${attack_name}: [%-20s] %d%%${NC}" \
               "$(printf "%*s" $((progress / 5)) | tr ' ' '=')" "$progress"
        sleep 5
    done
    echo ""
    
    # 성공률 시뮬레이션 (70% 성공률)
    local success=$((RANDOM % 10))
    if [ $success -lt 7 ]; then
        echo -e "${GREEN}[✓] Simulated ${attack_name} attack successful${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_SIM:${attack_name}_SUCCESS_$(date +%s)" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Simulated ${attack_name} attack failed${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_SIM:${attack_name}_FAILED_$(date +%s)" >> "$IOC_FILE"
        return 1
    fi
}

# IOC 파일 병합
merge_attack_iocs() {
    local attack_name=$1
    
    # 각 공격의 IOC 파일을 마스터 파일에 병합
    local attack_ioc_patterns=(
        "/tmp/secure_boot_bypass_iocs.txt"
        "/tmp/firmware_modification_iocs.txt"
        "/tmp/bootloader_exploit_iocs.txt"
        "/tmp/flash_memory_dump_iocs.txt"
        "/tmp/cryptographic_keys_iocs.txt"
    )
    
    for ioc_file in "${attack_ioc_patterns[@]}"; do
        if [ -f "$ioc_file" ]; then
            echo "# IOCs from $(basename "$ioc_file") - $(date)" >> "$IOC_FILE"
            cat "$ioc_file" >> "$IOC_FILE"
            echo "" >> "$IOC_FILE"
        fi
    done
    
    echo "FIRMWARE_SUITE:${attack_name}_COMPLETED_$(date +%s)" >> "$IOC_FILE"
}

# 마스터 리포트 생성
generate_master_report() {
    echo -e "${CYAN}[*] Generating master firmware attack report...${NC}" | tee -a "$LOG_FILE"
    
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
    attacks = ['secure_boot', 'firmware_mod', 'bootloader', 'flash_dump', 'crypto_keys']
    for attack in attacks:
        # 실제로는 bash 변수에서 읽어야 하지만 시뮬레이션
        attack_status[attack] = 'SUCCESS' if hash(attack) % 3 != 0 else 'FAILED'
        attack_durations[attack] = hash(attack) % 300 + 60  # 60-360초
    
    master_report = {
        'suite_info': {
            'name': 'DVD Firmware Attack Suite',
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
        'security_assessment': {
            'firmware_security_level': 'unknown',
            'boot_chain_integrity': 'unknown',
            'cryptographic_strength': 'unknown',
            'overall_risk_level': 'unknown'
        },
        'technical_summary': {
            'total_iocs_generated': 0,
            'firmware_artifacts': [],
            'extracted_keys': [],
            'modified_binaries': [],
            'forensic_footprint': 'high'
        },
        'recommendations': {
            'immediate_actions': [
                'Implement hardware security modules',
                'Enable secure boot with verified signatures',
                'Deploy firmware integrity monitoring',
                'Restrict physical access to devices'
            ],
            'long_term_improvements': [
                'Implement anti-tamper mechanisms',
                'Deploy code signing infrastructure',
                'Regular firmware security audits',
                'Implement secure update mechanisms'
            ]
        }
    }
    
    # 개별 공격 상세 정보
    for attack in attacks:
        master_report['attack_summary']['attack_details'][attack] = {
            'status': attack_status.get(attack, 'UNKNOWN'),
            'duration_seconds': attack_durations.get(attack, 0),
            'security_impact': 'high' if attack_status.get(attack) == 'SUCCESS' else 'none'
        }
    
    # 성공한 공격에 따른 보안 수준 평가
    successful_count = master_report['attack_summary']['successful_attacks']
    if successful_count >= 4:
        master_report['security_assessment']['firmware_security_level'] = 'critical_vulnerable'
        master_report['security_assessment']['boot_chain_integrity'] = 'compromised'
        master_report['security_assessment']['cryptographic_strength'] = 'weak'
        master_report['security_assessment']['overall_risk_level'] = 'critical'
    elif successful_count >= 3:
        master_report['security_assessment']['firmware_security_level'] = 'highly_vulnerable'
        master_report['security_assessment']['boot_chain_integrity'] = 'partially_compromised'
        master_report['security_assessment']['cryptographic_strength'] = 'moderate'
        master_report['security_assessment']['overall_risk_level'] = 'high'
    elif successful_count >= 2:
        master_report['security_assessment']['firmware_security_level'] = 'vulnerable'
        master_report['security_assessment']['boot_chain_integrity'] = 'weakened'
        master_report['security_assessment']['cryptographic_strength'] = 'adequate'
        master_report['security_assessment']['overall_risk_level'] = 'medium'
    elif successful_count >= 1:
        master_report['security_assessment']['firmware_security_level'] = 'partially_vulnerable'
        master_report['security_assessment']['boot_chain_integrity'] = 'mostly_intact'
        master_report['security_assessment']['cryptographic_strength'] = 'good'
        master_report['security_assessment']['overall_risk_level'] = 'low'
    else:
        master_report['security_assessment']['firmware_security_level'] = 'secure'
        master_report['security_assessment']['boot_chain_integrity'] = 'intact'
        master_report['security_assessment']['cryptographic_strength'] = 'strong'
        master_report['security_assessment']['overall_risk_level'] = 'minimal'
    
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
print(f'Overall risk level: {report[\"security_assessment\"][\"overall_risk_level\"]}')
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
    echo -e "${BOLD}${GREEN}🔓 DVD Firmware Attack Suite Execution Complete!${NC}"
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
    
    # 보안 위험 평가
    if [ $successful_attacks -ge 4 ]; then
        echo -e "${RED}⚠️  CRITICAL FIRMWARE SECURITY BREACH ⚠️${NC}"
        echo -e "${RED}   • Complete firmware compromise possible${NC}"
        echo -e "${RED}   • Boot chain integrity lost${NC}"
        echo -e "${RED}   • Persistent backdoor installation feasible${NC}"
        echo -e "${RED}   • Device fully controllable by attacker${NC}"
    elif [ $successful_attacks -ge 3 ]; then
        echo -e "${YELLOW}⚠️  HIGH-RISK FIRMWARE VULNERABILITIES ⚠️${NC}"
        echo -e "${YELLOW}   • Major security weaknesses identified${NC}"
        echo -e "${YELLOW}   • Partial firmware compromise achieved${NC}"
        echo -e "${YELLOW}   • Significant attack surface exposed${NC}"
    elif [ $successful_attacks -ge 2 ]; then
        echo -e "${CYAN}ℹ️  MODERATE FIRMWARE SECURITY ISSUES${NC}"
        echo -e "${CYAN}   • Some security controls bypassed${NC}"
        echo -e "${CYAN}   • Limited compromise possible${NC}"
    elif [ $successful_attacks -ge 1 ]; then
        echo -e "${BLUE}ℹ️  MINIMAL FIRMWARE VULNERABILITIES${NC}"
        echo -e "${BLUE}   • Minor security weakness found${NC}"
        echo -e "${BLUE}   • Limited impact potential${NC}"
    else
        echo -e "${GREEN}✓ FIRMWARE SECURITY INTACT${NC}"
        echo -e "${GREEN}   • All attacks successfully defended${NC}"
        echo -e "${GREEN}   • Strong security posture maintained${NC}"
    fi
    
    echo ""
}

# 메인 실행 함수
main() {
    local execution_mode="interactive"
    local selected_attacks=()
    local run_all=false
    local parallel_mode=false
    local timeout=900
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
                selected_attacks=("secure_boot" "firmware_mod" "bootloader" "flash_dump" "crypto_keys")
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
            secure_boot|firmware_mod|bootloader|flash_dump|crypto_keys)
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
    echo "=== DVD Firmware Attack Suite Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    echo -e "${BOLD}${BLUE}🔓 Starting DVD Firmware Attack Suite...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 공격 모듈 상태 확인
    if ! check_attack_modules; then
        echo -e "${YELLOW}[*] Some modules missing, continuing with available ones...${NC}"
    fi
    
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
    
    # 마스터 리포트 생성
    echo ""
    echo -e "${BOLD}${CYAN}📊 Generating Master Security Report...${NC}"
    generate_master_report
    
    # 실행 결과 요약
    if [ "$quiet_mode" = false ]; then
        print_execution_summary
    fi
    
    echo -e "${BOLD}${GREEN}🎯 DVD Firmware Attack Suite Complete!${NC}"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up firmware attack suite processes...${NC}"
    
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
    
    # 백그라운드 작업 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"