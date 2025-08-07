#!/bin/bash

# =============================================================================
# DVD MTD 테스트베드 - 마스터 공격 실행 시스템
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/master_attack_runner.sh
# 목적: 모든 공격 시나리오의 체계적 실행 및 결과 수집
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
SCRIPT_NAME="DVD MTD Master Attack Runner"
VERSION="2.0.0"
LOG_DIR="/home/kali/MTD/MTD_full_testbed/attack_logs"
OUTPUT_DIR="/home/kali/MTD/MTD_full_testbed/attack_output"
SUPERVISED_DIR="/home/kali/MTD/MTD_full_testbed/supervised_data"
MASTER_LOG="$LOG_DIR/master_runner_$(date +%Y%m%d_%H%M%S).log"
ATTACK_BASE_DIR="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks"

# 실행 모드
EXECUTION_MODE="sequential"  # sequential, parallel, priority, random
MAX_PARALLEL=3
ATTACK_INTERVAL=5
ENABLE_LOGGING=true
GENERATE_ML_DATA=true
ENABLE_CTI=true

# 공격 카테고리 정의
declare -A ATTACK_CATEGORIES=(
    ["reconnaissance"]="wifi_network_discovery mavlink_discovery drone_fingerprinting"
    ["protocol_tampering"]="gps_spoofing mavlink_injection rf_jamming"
    ["denial_of_service"]="mavlink_flood wifi_deauth resource_exhaustion"
    ["injection"]="flight_plan_injection parameter_manipulation firmware_upload_manipulation"
    ["exfiltration"]="telemetry_exfiltration flight_log_extraction video_stream_hijacking"
    ["firmware_attacks"]="bootloader_exploit firmware_rollback secure_boot_bypass"
)

# 공격 난이도 매핑
declare -A ATTACK_DIFFICULTIES=(
    # Beginner Level
    ["wifi_network_discovery"]="BEGINNER"
    ["mavlink_discovery"]="BEGINNER"
    ["wifi_deauth"]="BEGINNER"
    ["flight_log_extraction"]="BEGINNER"
    
    # Intermediate Level  
    ["drone_fingerprinting"]="INTERMEDIATE"
    ["mavlink_injection"]="INTERMEDIATE"
    ["mavlink_flood"]="INTERMEDIATE"
    ["parameter_manipulation"]="INTERMEDIATE"
    ["telemetry_exfiltration"]="INTERMEDIATE"
    ["resource_exhaustion"]="INTERMEDIATE"
    
    # Advanced Level
    ["gps_spoofing"]="ADVANCED"
    ["rf_jamming"]="ADVANCED"
    ["flight_plan_injection"]="ADVANCED"
    ["firmware_upload_manipulation"]="ADVANCED"
    ["video_stream_hijacking"]="ADVANCED"
    ["bootloader_exploit"]="ADVANCED"
    ["firmware_rollback"]="ADVANCED"
    ["secure_boot_bypass"]="ADVANCED"
)

# 공격 우선순위 (낮을수록 먼저 실행)
declare -A ATTACK_PRIORITIES=(
    # Phase 1: 정찰 (1-3)
    ["wifi_network_discovery"]="1"
    ["mavlink_discovery"]="2" 
    ["drone_fingerprinting"]="3"
    
    # Phase 2: 프로토콜 조작 (4-6)
    ["gps_spoofing"]="4"
    ["mavlink_injection"]="5"
    ["rf_jamming"]="6"
    
    # Phase 3: 서비스 거부 (7-9)
    ["mavlink_flood"]="7"
    ["wifi_deauth"]="8"
    ["resource_exhaustion"]="9"
    
    # Phase 4: 주입 공격 (10-12)
    ["flight_plan_injection"]="10"
    ["parameter_manipulation"]="11"
    ["firmware_upload_manipulation"]="12"
    
    # Phase 5: 데이터 탈취 (13-15)
    ["telemetry_exfiltration"]="13"
    ["flight_log_extraction"]="14"
    ["video_stream_hijacking"]="15"
    
    # Phase 6: 펌웨어 공격 (16-18)
    ["bootloader_exploit"]="16"
    ["firmware_rollback"]="17"
    ["secure_boot_bypass"]="18"
)

# 실행 상태 추적
declare -A ATTACK_RESULTS=()
declare -A ATTACK_DURATIONS=()
declare -A ATTACK_IOC_COUNTS=()
TOTAL_ATTACKS=0
SUCCESSFUL_ATTACKS=0
FAILED_ATTACKS=0
START_TIME=0
CURRENT_ATTACK=""

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                     🚀 DVD MTD MASTER ATTACK RUNNER 🚀                     ║"
    echo "║                           테스트베드 공격 오케스트레이터                          ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${CYAN}Version: $VERSION${NC}"
    echo -e "${CYAN}Mode: $EXECUTION_MODE${NC}"
    echo -e "${CYAN}ML Data: $([ "$GENERATE_ML_DATA" = true ] && echo "Enabled" || echo "Disabled")${NC}"
    echo -e "${CYAN}CTI Collection: $([ "$ENABLE_CTI" = true ] && echo "Enabled" || echo "Disabled")${NC}"
    echo ""
}

# 디렉토리 초기화
initialize_directories() {
    echo -e "${CYAN}[*] Initializing directory structure...${NC}" | tee -a "$MASTER_LOG"
    
    # 필요한 디렉토리들 생성
    local dirs=(
        "$LOG_DIR" "$OUTPUT_DIR" "$SUPERVISED_DIR"
        "$LOG_DIR/reconnaissance" "$LOG_DIR/protocol_tampering" "$LOG_DIR/denial_of_service"
        "$LOG_DIR/injection" "$LOG_DIR/exfiltration" "$LOG_DIR/firmware_attacks"
        "$OUTPUT_DIR/reconnaissance" "$OUTPUT_DIR/protocol_tampering" "$OUTPUT_DIR/denial_of_service"
        "$OUTPUT_DIR/injection" "$OUTPUT_DIR/exfiltration" "$OUTPUT_DIR/firmware_attacks"
        "$SUPERVISED_DIR/datasets" "$SUPERVISED_DIR/models" "$SUPERVISED_DIR/features"
        "$SUPERVISED_DIR/visualizations" "$SUPERVISED_DIR/evaluation"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[✓] Created: $dir${NC}" | tee -a "$MASTER_LOG"
        else
            echo -e "${RED}[×] Failed to create: $dir${NC}" | tee -a "$MASTER_LOG"
        fi
    done
}

# 시스템 환경 확인
check_system_requirements() {
    echo -e "${CYAN}[*] Checking system requirements...${NC}" | tee -a "$MASTER_LOG"
    
    local requirements_met=true
    
    # Python 확인
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        echo -e "${GREEN}[✓] Python 3 found: $python_version${NC}" | tee -a "$MASTER_LOG"
    else
        echo -e "${RED}[×] Python 3 not found${NC}" | tee -a "$MASTER_LOG"
        requirements_met=false
    fi
    
    # 필수 도구들 확인
    local tools=("nmap" "nc" "curl" "wget" "aircrack-ng")
    
    for tool in "${tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            echo -e "${GREEN}[✓] $tool available${NC}" | tee -a "$MASTER_LOG"
        else
            echo -e "${YELLOW}[!] $tool not found (some attacks may fail)${NC}" | tee -a "$MASTER_LOG"
        fi
    done
    
    # 권한 확인
    if [ "$EUID" -eq 0 ]; then
        echo -e "${GREEN}[✓] Root privileges available${NC}" | tee -a "$MASTER_LOG"
    else
        echo -e "${YELLOW}[!] Running without root (some attacks may fail)${NC}" | tee -a "$MASTER_LOG"
    fi
    
    return $([ "$requirements_met" = true ] && echo 0 || echo 1)
}

# 개별 공격 실행
execute_single_attack() {
    local attack_name=$1
    local category=$2
    local attack_script="$ATTACK_BASE_DIR/$category/$attack_name.sh"
    
    echo -e "${CYAN}[*] Executing attack: $attack_name${NC}" | tee -a "$MASTER_LOG"
    CURRENT_ATTACK="$attack_name"
    
    # 스크립트 존재 확인
    if [ ! -f "$attack_script" ]; then
        echo -e "${RED}[×] Attack script not found: $attack_script${NC}" | tee -a "$MASTER_LOG"
        ATTACK_RESULTS["$attack_name"]="SCRIPT_NOT_FOUND"
        ATTACK_DURATIONS["$attack_name"]=0
        ATTACK_IOC_COUNTS["$attack_name"]=0
        ((FAILED_ATTACKS++))
        return 1
    fi
    
    # 실행 권한 설정
    chmod +x "$attack_script"
    
    # 공격 시작 시간 기록
    local attack_start_time=$(date +%s)
    
    # 공격 실행 (타임아웃 300초)
    echo -e "${BLUE}[*] Starting $attack_name attack...${NC}" | tee -a "$MASTER_LOG"
    
    local attack_log="$LOG_DIR/$category/${attack_name}_$(date +%Y%m%d_%H%M%S).log"
    
    if timeout 300 bash "$attack_script" &> "$attack_log"; then
        local attack_duration=$(($(date +%s) - attack_start_time))
        echo -e "${GREEN}[✓] Attack completed successfully${NC}" | tee -a "$MASTER_LOG"
        
        ATTACK_RESULTS["$attack_name"]="SUCCESS"
        ATTACK_DURATIONS["$attack_name"]=$attack_duration
        ((SUCCESSFUL_ATTACKS++))
        
        # IOC 개수 계산
        local ioc_count=0
        if [ -f "/tmp/${attack_name}_iocs.txt" ]; then
            ioc_count=$(wc -l < "/tmp/${attack_name}_iocs.txt")
        fi
        ATTACK_IOC_COUNTS["$attack_name"]=$ioc_count
        
        echo -e "${BLUE}    Duration: ${attack_duration}s, IOCs: $ioc_count${NC}" | tee -a "$MASTER_LOG"
        
        # ML 데이터 생성
        if [ "$GENERATE_ML_DATA" = true ]; then
            generate_ml_features "$attack_name" "$category" "SUCCESS" "$attack_duration" "$ioc_count"
        fi
        
        return 0
        
    else
        local attack_duration=$(($(date +%s) - attack_start_time))
        echo -e "${RED}[×] Attack failed or timed out${NC}" | tee -a "$MASTER_LOG"
        
        ATTACK_RESULTS["$attack_name"]="FAILED"
        ATTACK_DURATIONS["$attack_name"]=$attack_duration
        ATTACK_IOC_COUNTS["$attack_name"]=0
        ((FAILED_ATTACKS++))
        
        # 실패 원인 분석
        analyze_attack_failure "$attack_name" "$attack_log"
        
        # ML 데이터 생성 (실패 케이스도 중요)
        if [ "$GENERATE_ML_DATA" = true ]; then
            generate_ml_features "$attack_name" "$category" "FAILED" "$attack_duration" "0"
        fi
        
        return 1
    fi
    
    ((TOTAL_ATTACKS++))
}

# 공격 실패 분석
analyze_attack_failure() {
    local attack_name=$1
    local log_file=$2
    
    echo -e "${YELLOW}[*] Analyzing failure for $attack_name...${NC}" | tee -a "$MASTER_LOG"
    
    if [ -f "$log_file" ]; then
        # 일반적인 실패 원인들 검색
        local failure_reasons=()
        
        if grep -q "Permission denied" "$log_file"; then
            failure_reasons+=("PERMISSION_DENIED")
        fi
        
        if grep -q "Connection refused\|Connection timeout" "$log_file"; then
            failure_reasons+=("CONNECTION_FAILED")
        fi
        
        if grep -q "command not found\|No such file" "$log_file"; then
            failure_reasons+=("MISSING_DEPENDENCY")
        fi
        
        if grep -q "Network is unreachable\|No route to host" "$log_file"; then
            failure_reasons+=("NETWORK_UNREACHABLE")
        fi
        
        if [ ${#failure_reasons[@]} -gt 0 ]; then
            echo -e "${RED}[!] Failure reasons: ${failure_reasons[*]}${NC}" | tee -a "$MASTER_LOG"
            
            for reason in "${failure_reasons[@]}"; do
                echo "ATTACK_FAILURE:${attack_name}_${reason}" >> "/tmp/master_attack_failures.txt"
            done
        else
            echo -e "${YELLOW}[?] Unknown failure reason${NC}" | tee -a "$MASTER_LOG"
            echo "ATTACK_FAILURE:${attack_name}_UNKNOWN" >> "/tmp/master_attack_failures.txt"
        fi
    fi
}

# 지도학습 특성 생성
generate_ml_features() {
    local attack_name=$1
    local category=$2
    local result=$3
    local duration=$4
    local ioc_count=$5
    
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local features_file="$SUPERVISED_DIR/features/attack_features_$(date +%Y%m%d).jsonl"
    
    # 공격 특성 추출
    local attack_complexity=1
    case ${ATTACK_DIFFICULTIES["$attack_name"]} in
        "BEGINNER") attack_complexity=1 ;;
        "INTERMEDIATE") attack_complexity=2 ;;
        "ADVANCED") attack_complexity=3 ;;
    esac
    
    # 네트워크 특성 시뮬레이션 (실제로는 네트워크 모니터링에서 수집)
    local network_features=$(python3 -c "
import json
import random

# 시뮬레이션된 네트워크 특성
features = {
    'packet_count': random.randint(100, 5000),
    'connection_attempts': random.randint(1, 50),
    'unique_ips': random.randint(1, 10),
    'port_scans': random.randint(0, 100),
    'protocol_violations': random.randint(0, 20),
    'bandwidth_usage': round(random.uniform(0.1, 100.0), 2),
    'latency_avg': round(random.uniform(1.0, 500.0), 2)
}

# 공격 유형에 따른 조정
attack_name = '$attack_name'
if 'wifi' in attack_name:
    features['wifi_activity'] = 1
    features['packet_count'] *= 2
elif 'mavlink' in attack_name:
    features['mavlink_packets'] = random.randint(50, 500)
elif 'firmware' in attack_name:
    features['firmware_activity'] = 1
    features['low_level_access'] = 1

print(json.dumps(features))
")
    
    # 공격 특성
    local attack_features=$(python3 -c "
import json
import random

features = {
    'attack_complexity': $attack_complexity,
    'payload_size': random.randint(64, 8192),
    'exploit_attempts': random.randint(1, 10),
    'stealth_level': round(random.uniform(0.0, 1.0), 2),
    'persistence_mechanisms': random.randint(0, 3),
    'privilege_escalation': random.choice([True, False]),
    'lateral_movement': random.choice([True, False]),
    'data_destruction': False
}

# 공격 유형별 조정
attack_name = '$attack_name'
if 'injection' in attack_name:
    features['persistence_mechanisms'] += 1
elif 'firmware' in attack_name:
    features['privilege_escalation'] = True
    features['persistence_mechanisms'] = 3
elif 'exfiltration' in attack_name:
    features['stealth_level'] = min(1.0, features['stealth_level'] + 0.3)

print(json.dumps(features))
")
    
    # MTD 특성 시뮬레이션
    local mtd_features=$(python3 -c "
import json
import random

features = {
    'mtd_triggers': random.randint(0, 20),
    'topology_changes': random.randint(0, 10),
    'encryption_rotations': random.randint(0, 5),
    'frequency_hops': random.randint(0, 15),
    'emergency_responses': random.randint(0, 8),
    'response_time': round(random.uniform(0.1, 10.0), 2),
    'effectiveness_score': round(random.uniform(0.0, 1.0), 2)
}

print(json.dumps(features))
")
    
    # 완전한 지도학습 샘플 생성
    local ml_sample=$(python3 -c "
import json

sample = {
    'timestamp': '$timestamp',
    'attack_vector': '$attack_name',
    'attack_category': '$category',
    'attack_result': '$result',
    'duration': $duration,
    'ioc_count': $ioc_count,
    'network_features': $network_features,
    'attack_features': $attack_features,
    'mtd_features': $mtd_features,
    'labels': {
        'attack_success': '$result' == 'SUCCESS',
        'detection_triggered': $ioc_count > 0,
        'mtd_effective': '$result' == 'FAILED' and $ioc_count > 0
    },
    'metadata': {
        'difficulty': '${ATTACK_DIFFICULTIES["$attack_name"]}',
        'priority': ${ATTACK_PRIORITIES["$attack_name"]},
        'execution_mode': '$EXECUTION_MODE'
    }
}

print(json.dumps(sample, indent=2))
")
    
    # JSONL 형식으로 추가 (각 줄이 하나의 JSON 객체)
    echo "$ml_sample" >> "$features_file"
    
    echo -e "${BLUE}[*] ML features generated for $attack_name${NC}" | tee -a "$MASTER_LOG"
}

# 순차 실행
run_sequential_attacks() {
    echo -e "${CYAN}[*] Starting sequential attack execution...${NC}" | tee -a "$MASTER_LOG"
    
    local attack_order=()
    
    # 우선순위 순서로 정렬
    if [ "$EXECUTION_MODE" = "priority" ]; then
        echo -e "${BLUE}[*] Ordering attacks by priority...${NC}" | tee -a "$MASTER_LOG"
        
        # 우선순위별로 정렬
        for attack in "${!ATTACK_PRIORITIES[@]}"; do
            attack_order+=("${ATTACK_PRIORITIES["$attack"]}:$attack")
        done
        
        # 정렬
        IFS=\n' attack_order=($(sort -n <<<"${attack_order[*]}"))
        
    elif [ "$EXECUTION_MODE" = "random" ]; then
        echo -e "${BLUE}[*] Randomizing attack order...${NC}" | tee -a "$MASTER_LOG"
        
        # 모든 공격을 배열에 추가
        for category in "${!ATTACK_CATEGORIES[@]}"; do
            for attack in ${ATTACK_CATEGORIES["$category"]}; do
                attack_order+=("0:$attack")  # 우선순위 무시
            done
        done
        
        # 셔플
        attack_order=($(printf '%s\n' "${attack_order[@]}" | shuf))
        
    else
        # 기본 순차 실행 (카테고리 순서)
        echo -e "${BLUE}[*] Using default category order...${NC}" | tee -a "$MASTER_LOG"
        
        local categories=("reconnaissance" "protocol_tampering" "denial_of_service" "injection" "exfiltration" "firmware_attacks")
        
        for category in "${categories[@]}"; do
            for attack in ${ATTACK_CATEGORIES["$category"]}; do
                attack_order+=("0:$attack")
            done
        done
    fi
    
    # 공격 실행
    local total_planned=${#attack_order[@]}
    local current_num=0
    
    for attack_entry in "${attack_order[@]}"; do
        IFS=':' read -r priority attack_name <<< "$attack_entry"
        ((current_num++))
        
        # 공격이 속한 카테고리 찾기
        local attack_category=""
        for category in "${!ATTACK_CATEGORIES[@]}"; do
            if [[ " ${ATTACK_CATEGORIES["$category"]} " =~ " $attack_name " ]]; then
                attack_category="$category"
                break
            fi
        done
        
        if [ -z "$attack_category" ]; then
            echo -e "${RED}[×] Category not found for attack: $attack_name${NC}" | tee -a "$MASTER_LOG"
            continue
        fi
        
        echo -e "${BOLD}${YELLOW}[$current_num/$total_planned] $attack_name ($attack_category)${NC}" | tee -a "$MASTER_LOG"
        
        # 공격 실행
        execute_single_attack "$attack_name" "$attack_category"
        local exit_code=$?
        
        # 공격 간 간격
        if [ $current_num -lt $total_planned ] && [ $ATTACK_INTERVAL -gt 0 ]; then
            echo -e "${CYAN}[*] Waiting ${ATTACK_INTERVAL}s before next attack...${NC}" | tee -a "$MASTER_LOG"
            sleep $ATTACK_INTERVAL
        fi
        
        # 실패한 정찰 공격이 있는 경우 중단 옵션
        if [ "$attack_category" = "reconnaissance" ] && [ $exit_code -ne 0 ]; then
            echo -e "${YELLOW}[!] Critical reconnaissance attack failed${NC}" | tee -a "$MASTER_LOG"
            
            read -p "Continue with remaining attacks? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo -e "${RED}[!] Attack sequence aborted by user${NC}" | tee -a "$MASTER_LOG"
                break
            fi
        fi
    done
}

# 병렬 실행
run_parallel_attacks() {
    echo -e "${CYAN}[*] Starting parallel attack execution (max: $MAX_PARALLEL)...${NC}" | tee -a "$MASTER_LOG"
    
    local pids=()
    local running_attacks=()
    
    # 모든 공격을 준비
    local all_attacks=()
    for category in "${!ATTACK_CATEGORIES[@]}"; do
        for attack in ${ATTACK_CATEGORIES["$category"]}; do
            all_attacks+=("$category:$attack")
        done
    done
    
    local total_attacks=${#all_attacks[@]}
    local completed=0
    
    # 병렬 실행 루프
    for attack_entry in "${all_attacks[@]}"; do
        IFS=':' read -r category attack_name <<< "$attack_entry"
        
        # 실행 중인 프로세스가 최대치에 도달하면 대기
        while [ ${#pids[@]} -ge $MAX_PARALLEL ]; do
            # 완료된 프로세스 확인
            for i in "${!pids[@]}"; do
                local pid=${pids[$i]}
                local attack=${running_attacks[$i]}
                
                if ! kill -0 $pid 2>/dev/null; then
                    # 프로세스 완료
                    wait $pid
                    local exit_code=$?
                    
                    ((completed++))
                    echo -e "${BLUE}[$completed/$total_attacks] $attack completed${NC}" | tee -a "$MASTER_LOG"
                    
                    # 배열에서 제거
                    unset pids[$i]
                    unset running_attacks[$i]
                    
                    # 배열 재정렬
                    pids=("${pids[@]}")
                    running_attacks=("${running_attacks[@]}")
                    
                    break
                fi
            done
            
            sleep 1
        done
        
        # 새 공격 시작
        echo -e "${CYAN}[*] Starting $attack_name in background...${NC}" | tee -a "$MASTER_LOG"
        
        (
            execute_single_attack "$attack_name" "$category"
        ) &
        
        local new_pid=$!
        pids+=($new_pid)
        running_attacks+=("$attack_name")
    done
    
    # 남은 프로세스들 대기
    echo -e "${CYAN}[*] Waiting for remaining attacks to complete...${NC}" | tee -a "$MASTER_LOG"
    
    for pid in "${pids[@]}"; do
        wait $pid
    done
    
    echo -e "${GREEN}[✓] All parallel attacks completed${NC}" | tee -a "$MASTER_LOG"
}

# 카테고리별 실행
run_category_attacks() {
    local target_category=$1
    
    if [ -z "$target_category" ]; then
        echo "사용 가능한 카테고리:"
        for category in "${!ATTACK_CATEGORIES[@]}"; do
            local attack_count=$(echo ${ATTACK_CATEGORIES["$category"]} | wc -w)
            echo "  • $category ($attack_count attacks)"
        done
        
        read -p "실행할 카테고리를 선택하세요: " target_category
    fi
    
    if [ -z "${ATTACK_CATEGORIES["$target_category"]}" ]; then
        echo -e "${RED}[×] Invalid category: $target_category${NC}" | tee -a "$MASTER_LOG"
        return 1
    fi
    
    echo -e "${CYAN}[*] Executing $target_category attacks...${NC}" | tee -a "$MASTER_LOG"
    
    local attacks=(${ATTACK_CATEGORIES["$target_category"]})
    local current=0
    
    for attack_name in "${attacks[@]}"; do
        ((current++))
        echo -e "${BOLD}${YELLOW}[$current/${#attacks[@]}] $attack_name${NC}" | tee -a "$MASTER_LOG"
        
        execute_single_attack "$attack_name" "$target_category"
        
        # 공격 간 간격
        if [ $current -lt ${#attacks[@]} ] && [ $ATTACK_INTERVAL -gt 0 ]; then
            sleep $ATTACK_INTERVAL
        fi
    done
}

# 난이도별 실행
run_difficulty_attacks() {
    local target_difficulty=$1
    
    if [ -z "$target_difficulty" ]; then
        echo "사용 가능한 난이도:"
        echo "  • BEGINNER (초급)"
        echo "  • INTERMEDIATE (중급)"  
        echo "  • ADVANCED (고급)"
        
        read -p "실행할 난이도를 선택하세요: " target_difficulty
    fi
    
    echo -e "${CYAN}[*] Executing $target_difficulty difficulty attacks...${NC}" | tee -a "$MASTER_LOG"
    
    # 해당 난이도의 공격들 수집
    local difficulty_attacks=()
    for attack in "${!ATTACK_DIFFICULTIES[@]}"; do
        if [ "${ATTACK_DIFFICULTIES["$attack"]}" = "$target_difficulty" ]; then
            difficulty_attacks+=("$attack")
        fi
    done
    
    if [ ${#difficulty_attacks[@]} -eq 0 ]; then
        echo -e "${RED}[×] No attacks found for difficulty: $target_difficulty${NC}" | tee -a "$MASTER_LOG"
        return 1
    fi
    
    echo -e "${BLUE}[*] Found ${#difficulty_attacks[@]} attacks for $target_difficulty difficulty${NC}" | tee -a "$MASTER_LOG"
    
    local current=0
    for attack_name in "${difficulty_attacks[@]}"; do
        ((current++))
        
        # 공격 카테고리 찾기
        local attack_category=""
        for category in "${!ATTACK_CATEGORIES[@]}"; do
            if [[ " ${ATTACK_CATEGORIES["$category"]} " =~ " $attack_name " ]]; then
                attack_category="$category"
                break
            fi
        done
        
        echo -e "${BOLD}${YELLOW}[$current/${#difficulty_attacks[@]}] $attack_name ($attack_category)${NC}" | tee -a "$MASTER_LOG"
        
        execute_single_attack "$attack_name" "$attack_category"
        
        # 공격 간 간격
        if [ $current -lt ${#difficulty_attacks[@]} ] && [ $ATTACK_INTERVAL -gt 0 ]; then
            sleep $ATTACK_INTERVAL
        fi
    done
}

# CTI 데이터 수집
collect_cti_data() {
    if [ "$ENABLE_CTI" != true ]; then
        return
    fi
    
    echo -e "${CYAN}[*] Collecting CTI data...${NC}" | tee -a "$MASTER_LOG"
    
    local cti_output="$OUTPUT_DIR/cti_collection_$(date +%Y%m%d_%H%M%S).json"
    
    # 모든 IOC 파일 통합
    local all_iocs="/tmp/master_all_iocs.txt"
    : > "$all_iocs"  # 파일 초기화
    
    for attack in "${!ATTACK_RESULTS[@]}"; do
        local ioc_file="/tmp/${attack}_iocs.txt"
        if [ -f "$ioc_file" ]; then
            echo "# IOCs from $attack" >> "$all_iocs"
            cat "$ioc_file" >> "$all_iocs"
            echo "" >> "$all_iocs"
        fi
    done
    
    # CTI 보고서 생성
    python3 -c "
import json
from datetime import datetime

def generate_cti_report():
    iocs = []
    attack_patterns = {}
    
    # IOC 파일 읽기
    try:
        with open('$all_iocs', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(':')
                    if len(parts) >= 2:
                        ioc_type = parts[0]
                        ioc_value = ':'.join(parts[1:])
                        
                        iocs.append({
                            'type': ioc_type,
                            'value': ioc_value,
                            'timestamp': datetime.now().isoformat(),
                            'confidence': 0.8,
                            'source': 'DVD_MTD_Testbed'
                        })
    except FileNotFoundError:
        pass
    
    # 공격 패턴 분석
    attack_results = $( cat << 'PYTHON_DICT'
{$(for attack in "${!ATTACK_RESULTS[@]}"; do
    echo "\"$attack\": \"${ATTACK_RESULTS["$attack"]}\","
done)}
}
PYTHON_DICT
)
    
    # CTI 보고서 구성
    cti_report = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'testbed_version': '$VERSION',
            'execution_mode': '$EXECUTION_MODE',
            'total_attacks': $TOTAL_ATTACKS,
            'successful_attacks': $SUCCESSFUL_ATTACKS
        },
        'indicators': iocs,
        'attack_patterns': {
            attack: {
                'success_rate': 1.0 if result == 'SUCCESS' else 0.0,
                'avg_duration': ${ATTACK_DURATIONS[attack]} if attack in $attack_results else 0,
                'ioc_count': ${ATTACK_IOC_COUNTS[attack]} if attack in $attack_results else 0
            }
            for attack, result in attack_results.items()
        },
        'statistics': {
            'total_indicators': len(iocs),
            'success_rate': ($SUCCESSFUL_ATTACKS / max($TOTAL_ATTACKS, 1)) * 100,
            'avg_attack_duration': sum(${ATTACK_DURATIONS[attack]} for attack in $attack_results) / max(len($attack_results), 1),
            'total_iocs': sum(${ATTACK_IOC_COUNTS[attack]} for attack in $attack_results)
        }
    }
    
    # JSON 파일로 저장
    with open('$cti_output', 'w') as f:
        json.dump(cti_report, f, indent=2)
    
    print(f'CTI report saved: $cti_output')
    return len(iocs)

ioc_count = generate_cti_report()
print(f'Total IOCs collected: {ioc_count}')
" | tee -a "$MASTER_LOG"
    
    echo -e "${GREEN}[✓] CTI data collection completed${NC}" | tee -a "$MASTER_LOG"
}

# 실행 결과 요약
print_execution_summary() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    
    echo "" | tee -a "$MASTER_LOG"
    echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}" | tee -a "$MASTER_LOG"
    echo -e "${BOLD}${BLUE}║                           🎯 EXECUTION SUMMARY 🎯                           ║${NC}" | tee -a "$MASTER_LOG"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}" | tee -a "$MASTER_LOG"
    
    # 기본 통계
    echo -e "${CYAN}📊 Attack Statistics:${NC}" | tee -a "$MASTER_LOG"
    echo -e "${BLUE}  • Total Attacks: $TOTAL_ATTACKS${NC}" | tee -a "$MASTER_LOG"
    echo -e "${GREEN}  • Successful: $SUCCESSFUL_ATTACKS${NC}" | tee -a "$MASTER_LOG"
    echo -e "${RED}  • Failed: $FAILED_ATTACKS${NC}" | tee -a "$MASTER_LOG"
    
    if [ $TOTAL_ATTACKS -gt 0 ]; then
        local success_rate=$((SUCCESSFUL_ATTACKS * 100 / TOTAL_ATTACKS))
        echo -e "${YELLOW}  • Success Rate: ${success_rate}%${NC}" | tee -a "$MASTER_LOG"
    fi
    
    echo -e "${BLUE}  • Total Duration: ${total_duration}s${NC}" | tee -a "$MASTER_LOG"
    
    # 카테고리별 결과
    echo -e "\n${CYAN}🎯 Category Results:${NC}" | tee -a "$MASTER_LOG"
    
    for category in "${!ATTACK_CATEGORIES[@]}"; do
        local category_attacks=(${ATTACK_CATEGORIES["$category"]})
        local category_success=0
        local category_total=0
        local category_iocs=0
        
        for attack in "${category_attacks[@]}"; do
            if [ -n "${ATTACK_RESULTS["$attack"]}" ]; then
                ((category_total++))
                if [ "${ATTACK_RESULTS["$attack"]}" = "SUCCESS" ]; then
                    ((category_success++))
                fi
                category_iocs=$((category_iocs + ${ATTACK_IOC_COUNTS["$attack"]}))
            fi
        done
        
        if [ $category_total -gt 0 ]; then
            local category_rate=$((category_success * 100 / category_total))
            echo -e "${BLUE}  • ${category}: ${category_rate}% (${category_success}/${category_total}) - IOCs: ${category_iocs}${NC}" | tee -a "$MASTER_LOG"
        fi
    done
    
    # 난이도별 결과
    echo -e "\n${CYAN}📈 Difficulty Results:${NC}" | tee -a "$MASTER_LOG"
    
    for difficulty in "BEGINNER" "INTERMEDIATE" "ADVANCED"; do
        local diff_success=0
        local diff_total=0
        
        for attack in "${!ATTACK_DIFFICULTIES[@]}"; do
            if [ "${ATTACK_DIFFICULTIES["$attack"]}" = "$difficulty" ] && [ -n "${ATTACK_RESULTS["$attack"]}" ]; then
                ((diff_total++))
                if [ "${ATTACK_RESULTS["$attack"]}" = "SUCCESS" ]; then
                    ((diff_success++))
                fi
            fi
        done
        
        if [ $diff_total -gt 0 ]; then
            local diff_rate=$((diff_success * 100 / diff_total))
            echo -e "${BLUE}  • ${difficulty}: ${diff_rate}% (${diff_success}/${diff_total})${NC}" | tee -a "$MASTER_LOG"
        fi
    done
    
    # 상위 성능 공격들
    echo -e "\n${CYAN}⭐ Top Performing Attacks:${NC}" | tee -a "$MASTER_LOG"
    
    local successful_attacks=()
    for attack in "${!ATTACK_RESULTS[@]}"; do
        if [ "${ATTACK_RESULTS["$attack"]}" = "SUCCESS" ]; then
            successful_attacks+=("$attack:${ATTACK_DURATIONS["$attack"]}:${ATTACK_IOC_COUNTS["$attack"]}")
        fi
    done
    
    # IOC 생성량으로 정렬
    IFS=\n' successful_attacks=($(sort -t: -k3 -nr <<<"${successful_attacks[*]}"))
    
    local count=0
    for attack_entry in "${successful_attacks[@]}"; do
        if [ $count -ge 5 ]; then break; fi  # 상위 5개만
        
        IFS=':' read -r attack duration iocs <<< "$attack_entry"
        echo -e "${GREEN}  • $attack: ${duration}s, ${iocs} IOCs${NC}" | tee -a "$MASTER_LOG"
        ((count++))
    done
    
    # 지도학습 데이터 요약
    if [ "$GENERATE_ML_DATA" = true ]; then
        echo -e "\n${CYAN}🤖 Machine Learning Data:${NC}" | tee -a "$MASTER_LOG"
        
        local ml_files=$(find "$SUPERVISED_DIR" -name "*.jsonl" -newer <(date -d "1 hour ago" +%Y-%m-%d\ %H:%M:%S) | wc -l)
        local total_samples=0
        
        for file in "$SUPERVISED_DIR"/features/attack_features_*.jsonl; do
            if [ -f "$file" ]; then
                local file_samples=$(wc -l < "$file" 2>/dev/null || echo 0)
                total_samples=$((total_samples + file_samples))
            fi
        done
        
        echo -e "${BLUE}  • Generated Files: $ml_files${NC}" | tee -a "$MASTER_LOG"
        echo -e "${BLUE}  • Total Samples: $total_samples${NC}" | tee -a "$MASTER_LOG"
        echo -e "${BLUE}  • Ready for Training: $([ $total_samples -gt 100 ] && echo "Yes" || echo "No (need more data)")${NC}" | tee -a "$MASTER_LOG"
    fi
    
    # 권장사항
    echo -e "\n${CYAN}💡 Recommendations:${NC}" | tee -a "$MASTER_LOG"
    
    if [ $SUCCESSFUL_ATTACKS -lt $((TOTAL_ATTACKS / 2)) ]; then
        echo -e "${YELLOW}  • Consider reviewing attack configurations${NC}" | tee -a "$MASTER_LOG"
        echo -e "${YELLOW}  • Check target system accessibility${NC}" | tee -a "$MASTER_LOG"
    fi
    
    if [ $TOTAL_ATTACKS -lt 10 ]; then
        echo -e "${YELLOW}  • Run more attacks for better ML training data${NC}" | tee -a "$MASTER_LOG"
    fi
    
    if [ "$GENERATE_ML_DATA" = true ] && [ $total_samples -gt 100 ]; then
        echo -e "${GREEN}  • Ready to start supervised learning pipeline${NC}" | tee -a "$MASTER_LOG"
        echo -e "${GREEN}  • Run: python3 supervised_learning_pipeline.py${NC}" | tee -a "$MASTER_LOG"
    fi
    
    echo -e "\n${CYAN}📁 Generated Files:${NC}" | tee -a "$MASTER_LOG"
    echo -e "${BLUE}  • Master Log: $MASTER_LOG${NC}" | tee -a "$MASTER_LOG"
    echo -e "${BLUE}  • Attack Logs: $LOG_DIR/${NC}" | tee -a "$MASTER_LOG"
    echo -e "${BLUE}  • Attack Output: $OUTPUT_DIR/${NC}" | tee -a "$MASTER_LOG"
    
    if [ "$GENERATE_ML_DATA" = true ]; then
        echo -e "${BLUE}  • ML Features: $SUPERVISED_DIR/features/${NC}" | tee -a "$MASTER_LOG"
    fi
    
    if [ "$ENABLE_CTI" = true ]; then
        echo -e "${BLUE}  • CTI Reports: $OUTPUT_DIR/cti_collection_*.json${NC}" | tee -a "$MASTER_LOG"
    fi
}

# 설정 파일 로드
load_config() {
    local config_file="$ATTACK_BASE_DIR/config/master_config.conf"
    
    if [ -f "$config_file" ]; then
        echo -e "${CYAN}[*] Loading configuration from $config_file...${NC}" | tee -a "$MASTER_LOG"
        source "$config_file"
        echo -e "${GREEN}[✓] Configuration loaded${NC}" | tee -a "$MASTER_LOG"
    else
        echo -e "${YELLOW}[!] No config file found, using defaults${NC}" | tee -a "$MASTER_LOG"
        
        # 기본 설정 파일 생성
        mkdir -p "$(dirname "$config_file")"
        cat > "$config_file" << 'EOF'
# DVD MTD Master Attack Runner Configuration

# Execution Settings
EXECUTION_MODE="sequential"    # sequential, parallel, priority, random
MAX_PARALLEL=3                 # Maximum parallel attacks
ATTACK_INTERVAL=5              # Seconds between attacks

# Feature Flags
ENABLE_LOGGING=true
GENERATE_ML_DATA=true
ENABLE_CTI=true

# Timeouts and Limits
ATTACK_TIMEOUT=300             # Seconds per attack
MAX_IOC_SIZE=10000            # Maximum IOC file size

# Network Settings
TARGET_NETWORK="192.168.1.0/24"
TARGET_DRONE_IP="192.168.1.100"
MAVLINK_PORT="14550"

# Output Settings
DETAILED_LOGS=true
JSON_OUTPUT=true
CSV_EXPORT=true
EOF
        
        echo -e "${GREEN}[✓] Default config created: $config_file${NC}" | tee -a "$MASTER_LOG"
    fi
}

# 대화형 메뉴
interactive_menu() {
    while true; do
        clear
        print_header
        
        echo -e "${BOLD}${CYAN}🎯 실행 옵션을 선택하세요:${NC}"
        echo ""
        echo -e "${BLUE}1.${NC} 전체 공격 순차 실행 (Sequential)"
        echo -e "${BLUE}2.${NC} 전체 공격 병렬 실행 (Parallel)"  
        echo -e "${BLUE}3.${NC} 우선순위 기반 실행 (Priority)"
        echo -e "${BLUE}4.${NC} 무작위 순서 실행 (Random)"
        echo -e "${BLUE}5.${NC} 카테고리별 실행 (Category-based)"
        echo -e "${BLUE}6.${NC} 난이도별 실행 (Difficulty-based)"
        echo -e "${BLUE}7.${NC} 개별 공격 실행 (Single Attack)"
        echo -e "${BLUE}8.${NC} 지도학습 파이프라인 실행"
        echo -e "${BLUE}9.${NC} 설정 변경"
        echo -e "${BLUE}10.${NC} 이전 결과 확인"
        echo -e "${RED}11.${NC} 종료"
        echo ""
        
        read -p "선택 (1-11): " choice
        
        case $choice in
            1)
                EXECUTION_MODE="sequential"
                echo -e "\n${CYAN}🔄 순차 실행 모드로 전체 공격을 시작합니다...${NC}"
                run_sequential_attacks
                ;;
            2)
                EXECUTION_MODE="parallel"
                echo -e "\n${CYAN}⚡ 병렬 실행 모드로 전체 공격을 시작합니다...${NC}"
                run_parallel_attacks
                ;;
            3)
                EXECUTION_MODE="priority"
                echo -e "\n${CYAN}🎯 우선순위 기반으로 공격을 시작합니다...${NC}"
                run_sequential_attacks
                ;;
            4)
                EXECUTION_MODE="random"
                echo -e "\n${CYAN}🎲 무작위 순서로 공격을 시작합니다...${NC}"
                run_sequential_attacks
                ;;
            5)
                echo -e "\n${CYAN}📂 카테고리별 실행${NC}"
                run_category_attacks
                ;;
            6)
                echo -e "\n${CYAN}📈 난이도별 실행${NC}"
                run_difficulty_attacks
                ;;
            7)
                echo -e "\n${CYAN}🎯 개별 공격 실행${NC}"
                run_single_attack_menu
                ;;
            8)
                echo -e "\n${CYAN}🤖 지도학습 파이프라인 실행${NC}"
                python3 "$ATTACK_BASE_DIR/../supervised_learning_pipeline.py"
                ;;
            9)
                echo -e "\n${CYAN}⚙️ 설정 변경${NC}"
                configure_settings
                ;;
            10)
                echo -e "\n${CYAN}📊 이전 결과 확인${NC}"
                show_previous_results
                ;;
            11)
                echo -e "\n${GREEN}👋 프로그램을 종료합니다.${NC}"
                exit 0
                ;;
            *)
                echo -e "\n${RED}❌ 잘못된 선택입니다.${NC}"
                ;;
        esac
        
        # 실행 후 결과 출력
        if [ $choice -ge 1 ] && [ $choice -le 7 ]; then
            collect_cti_data
            print_execution_summary
            
            echo ""
            read -p "Press Enter to continue..." 
        fi
    done
}

# 개별 공격 실행 메뉴
run_single_attack_menu() {
    echo "사용 가능한 공격들:"
    echo ""
    
    local attack_num=1
    local attack_list=()
    
    for category in "${!ATTACK_CATEGORIES[@]}"; do
        echo -e "${BOLD}${BLUE}$category:${NC}"
        
        for attack in ${ATTACK_CATEGORIES["$category"]}; do
            local difficulty=${ATTACK_DIFFICULTIES["$attack"]}
            local priority=${ATTACK_PRIORITIES["$attack"]}
            
            echo -e "${YELLOW}  $attack_num.${NC} $attack ${GRAY}($difficulty, Priority: $priority)${NC}"
            attack_list+=("$attack:$category")
            ((attack_num++))
        done
        echo ""
    done
    
    read -p "실행할 공격 번호 (1-${#attack_list[@]}): " selection
    
    if [ "$selection" -ge 1 ] && [ "$selection" -le "${#attack_list[@]}" ]; then
        local selected_entry=${attack_list[$((selection - 1))]}
        IFS=':' read -r attack_name category <<< "$selected_entry"
        
        echo -e "\n${CYAN}🎯 $attack_name 공격을 실행합니다...${NC}"
        execute_single_attack "$attack_name" "$category"
        
    else
        echo -e "${RED}❌ 잘못된 선택입니다.${NC}"
    fi
}

# 설정 변경
configure_settings() {
    echo "현재 설정:"
    echo "  • Execution Mode: $EXECUTION_MODE"
    echo "  • Max Parallel: $MAX_PARALLEL"
    echo "  • Attack Interval: ${ATTACK_INTERVAL}s"
    echo "  • Generate ML Data: $GENERATE_ML_DATA"
    echo "  • Enable CTI: $ENABLE_CTI"
    echo ""
    
    read -p "실행 모드 변경 (sequential/parallel/priority/random) [$EXECUTION_MODE]: " new_mode
    if [ -n "$new_mode" ]; then
        EXECUTION_MODE="$new_mode"
    fi
    
    read -p "병렬 실행 수 [$MAX_PARALLEL]: " new_parallel
    if [ -n "$new_parallel" ] && [ "$new_parallel" -ge 1 ]; then
        MAX_PARALLEL="$new_parallel"
    fi
    
    read -p "공격 간격 (초) [$ATTACK_INTERVAL]: " new_interval
    if [ -n "$new_interval" ] && [ "$new_interval" -ge 0 ]; then
        ATTACK_INTERVAL="$new_interval"
    fi
    
    read -p "ML 데이터 생성 (true/false) [$GENERATE_ML_DATA]: " new_ml
    if [ -n "$new_ml" ]; then
        GENERATE_ML_DATA="$new_ml"
    fi
    
    read -p "CTI 수집 (true/false) [$ENABLE_CTI]: " new_cti
    if [ -n "$new_cti" ]; then
        ENABLE_CTI="$new_cti"
    fi
    
    echo -e "\n${GREEN}✅ 설정이 업데이트되었습니다.${NC}"
}

# 이전 결과 확인
show_previous_results() {
    echo "최근 실행 결과들:"
    echo ""
    
    # 최근 로그 파일들 찾기
    local recent_logs=($(find "$LOG_DIR" -name "master_runner_*.log" -mtime -7 | sort -r | head -5))
    
    if [ ${#recent_logs[@]} -eq 0 ]; then
        echo -e "${YELLOW}최근 7일 내 실행 기록이 없습니다.${NC}"
        return
    fi
    
    for i in "${!recent_logs[@]}"; do
        local log_file=${recent_logs[$i]}
        local log_date=$(basename "$log_file" | sed 's/master_runner_\(.*\)\.log/\1/')
        local readable_date=$(date -d "${log_date:0:8} ${log_date:9:2}:${log_date:11:2}:${log_date:13:2}" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$log_date")
        
        echo -e "${BLUE}$((i+1)). $readable_date${NC}"
        
        # 간단한 요약 추출
        if [ -f "$log_file" ]; then
            local total=$(grep -c "Executing attack:" "$log_file" 2>/dev/null || echo "0")
            local success=$(grep -c "Attack completed successfully" "$log_file" 2>/dev/null || echo "0")
            local rate=0
            
            if [ "$total" -gt 0 ]; then
                rate=$((success * 100 / total))
            fi
            
            echo -e "${GRAY}   Total: $total, Success: $success, Rate: ${rate}%${NC}"
        fi
        echo ""
    done
    
    read -p "상세 내용을 볼 로그 번호 (Enter=건너뛰기): " log_choice
    
    if [ -n "$log_choice" ] && [ "$log_choice" -ge 1 ] && [ "$log_choice" -le "${#recent_logs[@]}" ]; then
        local selected_log=${recent_logs[$((log_choice - 1))]}
        echo -e "\n${CYAN}📄 로그 내용 (마지막 50줄):${NC}"
        echo ""
        tail -50 "$selected_log"
    fi
}

# 안전성 검사
safety_check() {
    echo -e "${CYAN}[*] Performing safety checks...${NC}" | tee -a "$MASTER_LOG"
    
    local safety_issues=()
    
    # 실제 드론 하드웨어 탐지
    if lsusb | grep -i "drone\|pixhawk\|px4\|ardupilot"; then
        safety_issues+=("REAL_HARDWARE_DETECTED")
        echo -e "${RED}[!] WARNING: Real drone hardware detected${NC}" | tee -a "$MASTER_LOG"
    fi
    
    # 프로덕션 네트워크 확인
    local current_network=$(ip route | grep default | awk '{print $3}' | head -1)
    if [[ "$current_network" =~ ^(10\.|172\.1[6-9]\.|172\.2[0-9]\.|172\.3[0-1]\.|192\.168\.) ]]; then
        echo -e "${GREEN}[✓] Private network detected: $current_network${NC}" | tee -a "$MASTER_LOG"
    else
        safety_issues+=("PUBLIC_NETWORK_DETECTED")
        echo -e "${YELLOW}[!] WARNING: Public network access detected${NC}" | tee -a "$MASTER_LOG"
    fi
    
    # 중요 프로세스 확인
    local critical_services=("ssh" "apache2" "nginx" "mysql" "postgresql")
    for service in "${critical_services[@]}"; do
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            safety_issues+=("CRITICAL_SERVICE_RUNNING:$service")
            echo -e "${YELLOW}[!] WARNING: Critical service running: $service${NC}" | tee -a "$MASTER_LOG"
        fi
    done
    
    # 안전성 평가
    if [ ${#safety_issues[@]} -eq 0 ]; then
        echo -e "${GREEN}[✓] Safety check passed - Environment appears safe${NC}" | tee -a "$MASTER_LOG"
        return 0
    else
        echo -e "${RED}[!] Safety concerns detected: ${#safety_issues[@]} issues${NC}" | tee -a "$MASTER_LOG"
        
        for issue in "${safety_issues[@]}"; do
            echo "SAFETY_ISSUE:$issue" >> "/tmp/safety_warnings.txt"
        done
        
        echo -e "${YELLOW}Continue execution? This could be dangerous!${NC}"
        read -p "Type 'CONFIRM' to proceed: " confirmation
        
        if [ "$confirmation" = "CONFIRM" ]; then
            echo -e "${YELLOW}[!] User confirmed - Proceeding with caution${NC}" | tee -a "$MASTER_LOG"
            return 0
        else
            echo -e "${RED}[×] Execution aborted for safety${NC}" | tee -a "$MASTER_LOG"
            return 1
        fi
    fi
}

# 진행률 표시
show_progress() {
    local current=$1
    local total=$2
    local attack_name=$3
    
    local percentage=$((current * 100 / total))
    local bar_length=40
    local filled_length=$((percentage * bar_length / 100))
    
    # 진행률 바 생성
    local bar=""
    for ((i=0; i<filled_length; i++)); do
        bar+="█"
    done
    for ((i=filled_length; i<bar_length; i++)); do
        bar+="░"
    done
    
    # 색상 결정
    local color=$BLUE
    if [ $percentage -ge 75 ]; then
        color=$GREEN
    elif [ $percentage -ge 50 ]; then
        color=$YELLOW
    fi
    
    echo -e "\r${color}Progress: [$bar] $percentage% ($current/$total) - Current: $attack_name${NC}"
}

# 실시간 상태 모니터링
monitor_execution() {
    while [ -n "$CURRENT_ATTACK" ]; do
        local runtime=$(($(date +%s) - START_TIME))
        local avg_duration=0
        
        if [ $TOTAL_ATTACKS -gt 0 ]; then
            local total_duration=0
            for attack in "${!ATTACK_DURATIONS[@]}"; do
                total_duration=$((total_duration + ${ATTACK_DURATIONS["$attack"]}))
            done
            avg_duration=$((total_duration / TOTAL_ATTACKS))
        fi
        
        echo -e "\r${CYAN}[Monitor] Runtime: ${runtime}s | Current: $CURRENT_ATTACK | Avg: ${avg_duration}s | Success: $SUCCESSFUL_ATTACKS/$TOTAL_ATTACKS${NC}"
        sleep 2
    done
}

# 자동 복구 시스템
auto_recovery() {
    local failed_attack=$1
    local failure_reason=$2
    
    echo -e "${YELLOW}[*] Attempting auto-recovery for $failed_attack...${NC}" | tee -a "$MASTER_LOG"
    
    case $failure_reason in
        "PERMISSION_DENIED")
            echo -e "${BLUE}[*] Attempting privilege escalation...${NC}" | tee -a "$MASTER_LOG"
            # 권한 관련 복구 시도
            ;;
        "CONNECTION_FAILED")
            echo -e "${BLUE}[*] Checking network connectivity...${NC}" | tee -a "$MASTER_LOG"
            # 네트워크 관련 복구 시도
            ;;
        "MISSING_DEPENDENCY")
            echo -e "${BLUE}[*] Installing missing dependencies...${NC}" | tee -a "$MASTER_LOG"
            # 의존성 설치 시도
            ;;
        *)
            echo -e "${YELLOW}[?] Unknown failure - Manual intervention required${NC}" | tee -a "$MASTER_LOG"
            ;;
    esac
}

# 메인 실행 함수
main() {
    # 시작 시간 기록
    START_TIME=$(date +%s)
    
    # 디렉토리 초기화
    initialize_directories
    
    # 설정 로드
    load_config
    
    # 헤더 출력
    print_header
    
    # 시스템 요구사항 확인
    echo -e "${CYAN}[*] Checking system requirements...${NC}"
    if ! check_system_requirements; then
        echo -e "${RED}[×] System requirements not met${NC}"
        exit 1
    fi
    
    # 안전성 검사
    if ! safety_check; then
        echo -e "${RED}[×] Safety check failed - Aborting${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}[✓] System ready for attack execution${NC}" | tee -a "$MASTER_LOG"
    echo "MASTER_RUNNER_START:$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$MASTER_LOG"
    
    # 실행 모드 확인
    if [ $# -eq 0 ]; then
        # 대화형 모드
        interactive_menu
    else
        # 명령행 인자 처리
        case $1 in
            "all-sequential")
                EXECUTION_MODE="sequential"
                run_sequential_attacks
                ;;
            "all-parallel")
                EXECUTION_MODE="parallel"
                run_parallel_attacks
                ;;
            "all-priority")
                EXECUTION_MODE="priority"
                run_sequential_attacks
                ;;
            "category")
                run_category_attacks "$2"
                ;;
            "difficulty")
                run_difficulty_attacks "$2"
                ;;
            "single")
                if [ -n "$2" ] && [ -n "$3" ]; then
                    execute_single_attack "$2" "$3"
                else
                    echo "Usage: $0 single <attack_name> <category>"
                    exit 1
                fi
                ;;
            "supervised")
                python3 "$ATTACK_BASE_DIR/../supervised_learning_pipeline.py"
                ;;
            "help"|"-h"|"--help")
                show_help
                ;;
            *)
                echo "Unknown command: $1"
                show_help
                exit 1
                ;;
        esac
        
        # 명령행 모드 후 결과 처리
        collect_cti_data
        print_execution_summary
    fi
    
    echo "MASTER_RUNNER_END:$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$MASTER_LOG"
}

# 도움말 출력
show_help() {
    echo "DVD MTD Master Attack Runner v$VERSION"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  all-sequential     Execute all attacks sequentially"
    echo "  all-parallel       Execute all attacks in parallel"
    echo "  all-priority       Execute all attacks by priority order"
    echo "  category <name>    Execute attacks from specific category"
    echo "  difficulty <level> Execute attacks of specific difficulty"
    echo "  single <name> <cat> Execute single attack"
    echo "  supervised         Run supervised learning pipeline"
    echo "  help, -h, --help   Show this help message"
    echo ""
    echo "Categories:"
    for category in "${!ATTACK_CATEGORIES[@]}"; do
        echo "  • $category"
    done
    echo ""
    echo "Difficulty Levels:"
    echo "  • BEGINNER"
    echo "  • INTERMEDIATE"
    echo "  • ADVANCED"
    echo ""
    echo "Examples:"
    echo "  $0                              # Interactive mode"
    echo "  $0 all-sequential               # Run all attacks sequentially"
    echo "  $0 category reconnaissance      # Run reconnaissance attacks"
    echo "  $0 difficulty BEGINNER          # Run beginner attacks"
    echo "  $0 single wifi_network_discovery reconnaissance"
    echo ""
    echo "Configuration:"
    echo "  Edit $ATTACK_BASE_DIR/config/master_config.conf"
    echo ""
    echo "Log Files:"
    echo "  Master log: $LOG_DIR/master_runner_YYYYMMDD_HHMMSS.log"
    echo "  Attack logs: $LOG_DIR/[category]/[attack]_YYYYMMDD_HHMMSS.log"
    echo ""
    echo "Output Files:"
    echo "  Attack output: $OUTPUT_DIR/"
    echo "  ML features: $SUPERVISED_DIR/features/"
    echo "  CTI reports: $OUTPUT_DIR/cti_collection_*.json"
}

# 신호 처리
cleanup() {
    echo -e "\n${YELLOW}[!] Interrupt signal received${NC}" | tee -a "$MASTER_LOG"
    
    # 실행 중인 공격 프로세스 정리
    if [ -n "$CURRENT_ATTACK" ]; then
        echo -e "${CYAN}[*] Cleaning up current attack: $CURRENT_ATTACK${NC}" | tee -a "$MASTER_LOG"
        
        # 관련 프로세스 종료
        pkill -f "$CURRENT_ATTACK" 2>/dev/null
    fi
    
    # 임시 파일 정리
    rm -f /tmp/*_iocs.txt /tmp/master_*.txt 2>/dev/null
    
    # 부분 실행 결과 요약
    if [ $TOTAL_ATTACKS -gt 0 ]; then
        echo -e "\n${CYAN}[*] Partial execution summary:${NC}" | tee -a "$MASTER_LOG"
        echo -e "${BLUE}  Completed: $TOTAL_ATTACKS attacks${NC}" | tee -a "$MASTER_LOG"
        echo -e "${GREEN}  Successful: $SUCCESSFUL_ATTACKS${NC}" | tee -a "$MASTER_LOG"
        echo -e "${RED}  Failed: $FAILED_ATTACKS${NC}" | tee -a "$MASTER_LOG"
        
        # 부분 CTI 수집
        collect_cti_data
    fi
    
    echo -e "${GREEN}[✓] Cleanup completed${NC}" | tee -a "$MASTER_LOG"
    echo "MASTER_RUNNER_INTERRUPTED:$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$MASTER_LOG"
    
    exit 130
}

# 신호 트랩 설정
trap cleanup SIGINT SIGTERM

# 스크립트가 직접 실행된 경우
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi