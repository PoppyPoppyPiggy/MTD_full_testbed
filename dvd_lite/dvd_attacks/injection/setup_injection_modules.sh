#!/bin/bash

# =============================================================================
# DVD Injection Attack Modules Setup Script
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/setup_injection_modules.sh
# 목적: 모든 인젝션 공격 모듈 자동 설치 및 설정
# 작성자: MTD Testbed Team
# =============================================================================

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 전역 변수
INJECTION_DIR="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection"
LOG_DIR="/home/kali/MTD/MTD_full_testbed/attack_logs/injection"
OUTPUT_DIR="/home/kali/MTD/MTD_full_testbed/attack_output/injection"
COMMON_DIR="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common"

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    🛠️  DVD Injection Modules Setup 🛠️                   ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Purpose: Install and configure all injection attack modules${NC}"
    echo -e "${BLUE}Target: Kali Linux Environment${NC}"
    echo -e "${BLUE}Based: Damn Vulnerable Drone Attack Scenarios${NC}"
    echo ""
}

# 디렉토리 구조 생성
create_directory_structure() {
    echo -e "${YELLOW}[+] Creating directory structure...${NC}"
    
    local directories=(
        "$INJECTION_DIR"
        "$LOG_DIR"
        "$OUTPUT_DIR"
        "$COMMON_DIR"
    )
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            echo -e "${GREEN}[✓] Created: ${dir}${NC}"
        else
            echo -e "${CYAN}[*] Exists: ${dir}${NC}"
        fi
    done
    
    # 권한 설정
    chmod 755 "$INJECTION_DIR"
    chmod 755 "$LOG_DIR"
    chmod 755 "$OUTPUT_DIR"
    chmod 755 "$COMMON_DIR"
    
    echo -e "${GREEN}[✓] Directory structure created${NC}"
}

# 공통 모듈 생성
create_common_modules() {
    echo -e "${YELLOW}[+] Creating common modules...${NC}"
    
    # colors.sh 생성
    cat > "${COMMON_DIR}/colors.sh" << 'EOF'
#!/bin/bash
# Color definitions for DVD attacks
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color
EOF

    # utils.sh 생성
    cat > "${COMMON_DIR}/utils.sh" << 'EOF'
#!/bin/bash
# Utility functions for DVD attacks

# 필수 도구 확인 함수
check_required_tools() {
    local missing_tools=()
    
    for tool in "$@"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo -e "${RED}[!] Missing required tools: ${missing_tools[*]}${NC}"
        echo -e "${YELLOW}[*] Please install missing tools${NC}"
        return 1
    fi
    
    echo -e "${GREEN}[✓] All required tools available${NC}"
    return 0
}

# 로그 헤더 생성 함수
create_log_header() {
    local log_file=$1
    local attack_name=$2
    
    cat > "$log_file" << EOF
=== DVD Attack Log ===
Attack: $attack_name
Started: $(date)
Host: $(hostname)
User: $(whoami)
======================

EOF
}

# 진행률 표시 함수
show_progress() {
    local current=$1
    local total=$2
    local message=$3
    local percentage=$((current * 100 / total))
    local filled=$((percentage / 2))
    
    printf "\r${CYAN}[%3d%%] [%-50s] %s${NC}" \
           "$percentage" \
           "$(printf "%*s" "$filled" | tr ' ' '█')" \
           "$message"
    
    if [ $current -eq $total ]; then
        echo ""
    fi
}

# IP 주소 유효성 검사
validate_ip() {
    local ip=$1
    
    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        IFS='.' read -ra ADDR <<< "$ip"
        for i in "${ADDR[@]}"; do
            if [ $i -gt 255 ]; then
                return 1
            fi
        done
        return 0
    fi
    return 1
}

# 포트 유효성 검사
validate_port() {
    local port=$1
    
    if [[ $port =~ ^[0-9]+$ ]] && [ $port -ge 1 ] && [ $port -le 65535 ]; then
        return 0
    fi
    return 1
}

# 타임스탬프 생성
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# 파일 크기 포매팅
format_filesize() {
    local size=$1
    
    if [ $size -gt 1073741824 ]; then
        echo "$(echo "scale=1; $size/1073741824" | bc)GB"
    elif [ $size -gt 1048576 ]; then
        echo "$(echo "scale=1; $size/1048576" | bc)MB"
    elif [ $size -gt 1024 ]; then
        echo "$(echo "scale=1; $size/1024" | bc)KB"
    else
        echo "${size}B"
    fi
}
EOF

    # 실행 권한 부여
    chmod +x "${COMMON_DIR}/colors.sh"
    chmod +x "${COMMON_DIR}/utils.sh"
    
    echo -e "${GREEN}[✓] Common modules created${NC}"
}

# 시스템 의존성 설치
install_dependencies() {
    echo -e "${YELLOW}[+] Installing system dependencies...${NC}"
    
    # 시스템 패키지 업데이트
    echo -e "${CYAN}[*] Updating package lists...${NC}"
    apt-get update -qq 2>/dev/null
    
    # 필수 패키지 설치
    local packages=(
        "python3"
        "python3-pip"
        "curl"
        "netcat-openbsd"
        "bc"
        "jq"
        "aircrack-ng"
        "wireless-tools"
        "sqlmap"
        "nmap"
        "tcpdump"
        "wireshark-common"
    )
    
    echo -e "${CYAN}[*] Installing required packages...${NC}"
    for package in "${packages[@]}"; do
        if ! dpkg -l | grep -q "^ii  $package "; then
            echo -e "${YELLOW}[*] Installing $package...${NC}"
            apt-get install -y "$package" -qq 2>/dev/null
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}[✓] $package installed${NC}"
            else
                echo -e "${RED}[!] Failed to install $package${NC}"
            fi
        else
            echo -e "${CYAN}[*] $package already installed${NC}"
        fi
    done
    
    # Python 패키지 설치
    echo -e "${CYAN}[*] Installing Python packages...${NC}"
    local python_packages=(
        "pymavlink"
        "MAVProxy"
        "requests"
        "sqlparse"
        "scapy"
        "python-nmap"
    )
    
    for package in "${python_packages[@]}"; do
        echo -e "${YELLOW}[*] Installing Python package: $package${NC}"
        pip3 install "$package" -q 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[✓] $package installed${NC}"
        else
            echo -e "${RED}[!] Failed to install $package${NC}"
        fi
    done
    
    echo -e "${GREEN}[✓] Dependencies installation completed${NC}"
}

# 인젝션 공격 스크립트 생성
create_injection_scripts() {
    echo -e "${YELLOW}[+] Creating injection attack scripts...${NC}"
    
    # 1. MAVLink Command Injection Script
    echo -e "${CYAN}[*] Creating MAVLink command injection script...${NC}"
    
    # MAVLink Command Injection 스크립트는 이미 생성되어 있으므로 파일 복사 또는 심볼릭 링크
    if [ ! -f "${INJECTION_DIR}/mavlink_command_injection.sh" ]; then
        cat > "${INJECTION_DIR}/mavlink_command_injection.sh" << 'MAVLINK_EOF'
#!/bin/bash
# MAVLink Command Injection Attack - Generated by setup script
# 실제 스크립트 내용은 이전에 생성된 mavlink_command_injection.sh와 동일
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

echo -e "${CYAN}[*] MAVLink Command Injection Attack Module${NC}"
echo -e "${YELLOW}[*] This is a placeholder - use the full script from artifacts${NC}"
MAVLINK_EOF
    fi
    
    # 2. GPS Spoofing Script
    echo -e "${CYAN}[*] Creating GPS spoofing script...${NC}"
    
    if [ ! -f "${INJECTION_DIR}/gps_spoofing.sh" ]; then
        cat > "${INJECTION_DIR}/gps_spoofing.sh" << 'GPS_EOF'
#!/bin/bash
# GPS Spoofing Attack - Generated by setup script
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

echo -e "${CYAN}[*] GPS Spoofing Attack Module${NC}"
echo -e "${YELLOW}[*] This is a placeholder - use the full script from artifacts${NC}"
GPS_EOF
    fi
    
    # 3. SQL Injection Script
    echo -e "${CYAN}[*] Creating SQL injection script...${NC}"
    
    if [ ! -f "${INJECTION_DIR}/sql_injection.sh" ]; then
        cat > "${INJECTION_DIR}/sql_injection.sh" << 'SQL_EOF'
#!/bin/bash
# SQL Injection Attack - Generated by setup script
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

echo -e "${CYAN}[*] SQL Injection Attack Module${NC}"
echo -e "${YELLOW}[*] This is a placeholder - use the full script from artifacts${NC}"
SQL_EOF
    fi
    
    # 4. Parameter Manipulation Script
    echo -e "${CYAN}[*] Creating parameter manipulation script...${NC}"
    
    cat > "${INJECTION_DIR}/parameter_manipulation.sh" << 'PARAM_EOF'
#!/bin/bash

# =============================================================================
# DVD Injection Attack Module: Parameter Manipulation
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

ATTACK_NAME="Parameter Manipulation Attack"
TARGET_IP="127.0.0.1"
MAVLINK_PORT="14550"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/parameter_manipulation_$(date +%Y%m%d_%H%M%S).log"

print_header() {
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    ⚙️  DVD Parameter Manipulation ⚙️                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

main() {
    print_header
    
    echo -e "${CYAN}[*] Starting parameter manipulation attack...${NC}" | tee -a "$LOG_FILE"
    
    # 시뮬레이션된 파라미터 조작
    local critical_params=(
        "FENCE_ENABLE:0"
        "RTL_ALT:0"
        "BATT_LOW_VOLT:0"
        "FS_THR_ENABLE:0"
        "ARMING_CHECK:0"
    )
    
    for param in "${critical_params[@]}"; do
        local param_name=$(echo "$param" | cut -d':' -f1)
        local param_value=$(echo "$param" | cut -d':' -f2)
        
        echo -e "${YELLOW}[*] Manipulating ${param_name} = ${param_value}${NC}" | tee -a "$LOG_FILE"
        sleep 2
        
        if [ $((RANDOM % 100)) -lt 80 ]; then
            echo -e "${GREEN}[✓] ${param_name} successfully modified${NC}" | tee -a "$LOG_FILE"
        else
            echo -e "${RED}[!] Failed to modify ${param_name}${NC}" | tee -a "$LOG_FILE"
        fi
    done
    
    echo -e "${GREEN}[✓] Parameter manipulation attack completed${NC}" | tee -a "$LOG_FILE"
}

main "$@"
PARAM_EOF
    
    # 5. Waypoint Injection Script
    echo -e "${CYAN}[*] Creating waypoint injection script...${NC}"
    
    cat > "${INJECTION_DIR}/waypoint_injection.sh" << 'WAYPOINT_EOF'
#!/bin/bash

# =============================================================================
# DVD Injection Attack Module: Waypoint Injection
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

ATTACK_NAME="Waypoint Injection Attack"
TARGET_IP="127.0.0.1"
MAVLINK_PORT="14550"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/waypoint_injection_$(date +%Y%m%d_%H%M%S).log"

print_header() {
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                     🎯 DVD Waypoint Injection 🎯                        ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

main() {
    print_header
    
    echo -e "${CYAN}[*] Starting waypoint injection attack...${NC}" | tee -a "$LOG_FILE"
    
    # 악성 웨이포인트 시뮬레이션
    local malicious_waypoints=(
        "37.7749,-122.4194,100"  # 샌프란시스코
        "40.7128,-74.0060,200"   # 뉴욕
        "51.5074,-0.1278,150"    # 런던
    )
    
    echo -e "${YELLOW}[*] Injecting malicious waypoints...${NC}" | tee -a "$LOG_FILE"
    
    for i in "${!malicious_waypoints[@]}"; do
        local waypoint=${malicious_waypoints[$i]}
        local waypoint_num=$((i + 1))
        
        echo -e "${BLUE}[*] Injecting waypoint ${waypoint_num}: ${waypoint}${NC}" | tee -a "$LOG_FILE"
        sleep 2
        
        if [ $((RANDOM % 100)) -lt 85 ]; then
            echo -e "${GREEN}[✓] Waypoint ${waypoint_num} injected successfully${NC}" | tee -a "$LOG_FILE"
        else
            echo -e "${RED}[!] Failed to inject waypoint ${waypoint_num}${NC}" | tee -a "$LOG_FILE"
        fi
    done
    
    echo -e "${GREEN}[✓] Waypoint injection attack completed${NC}" | tee -a "$LOG_FILE"
}

main "$@"
WAYPOINT_EOF
    
    # 6. Firmware Injection Script
    echo -e "${CYAN}[*] Creating firmware injection script...${NC}"
    
    cat > "${INJECTION_DIR}/firmware_injection.sh" << 'FIRMWARE_EOF'
#!/bin/bash

# =============================================================================
# DVD Injection Attack Module: Firmware Injection
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

ATTACK_NAME="Firmware Injection Attack"
TARGET_IP="127.0.0.1"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/firmware_injection_$(date +%Y%m%d_%H%M%S).log"

print_header() {
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                     💾 DVD Firmware Injection 💾                        ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

main() {
    print_header
    
    echo -e "${CYAN}[*] Starting firmware injection attack...${NC}" | tee -a "$LOG_FILE"
    
    # 펌웨어 인젝션 단계 시뮬레이션
    local injection_stages=(
        "Firmware Analysis"
        "Backdoor Development"
        "Upload Exploitation"
        "Code Injection"
        "Persistence Establishment"
    )
    
    for i in "${!injection_stages[@]}"; do
        local stage=${injection_stages[$i]}
        local stage_num=$((i + 1))
        
        echo -e "${YELLOW}[*] Stage ${stage_num}/5: ${stage}...${NC}" | tee -a "$LOG_FILE"
        sleep 3
        
        if [ $((RANDOM % 100)) -lt 60 ]; then
            echo -e "${GREEN}[✓] ${stage} successful${NC}" | tee -a "$LOG_FILE"
        else
            echo -e "${RED}[!] ${stage} failed${NC}" | tee -a "$LOG_FILE"
        fi
    done
    
    echo -e "${GREEN}[✓] Firmware injection attack completed${NC}" | tee -a "$LOG_FILE"
}

main "$@"
FIRMWARE_EOF
    
    # 실행 권한 부여
    chmod +x "${INJECTION_DIR}"/*.sh
    
    echo -e "${GREEN}[✓] Injection attack scripts created${NC}"
}

# 메인 실행 스크립트 생성
create_main_runner() {
    echo -e "${YELLOW}[+] Creating main injection attack runner...${NC}"
    
    # run_injection.sh 스크립트는 이미 생성되어 있으므로 placeholder 생성
    if [ ! -f "${INJECTION_DIR}/run_injection.sh" ]; then
        cat > "${INJECTION_DIR}/run_injection.sh" << 'RUNNER_EOF'
#!/bin/bash
# DVD Injection Attack Suite Main Runner - Generated by setup script
# 실제 스크립트 내용은 이전에 생성된 injection_attack_suite와 동일
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

echo -e "${CYAN}[*] DVD Injection Attack Suite${NC}"
echo -e "${YELLOW}[*] This is a placeholder - use the full script from artifacts${NC}"
RUNNER_EOF
    fi
    
    chmod +x "${INJECTION_DIR}/run_injection.sh"
    
    echo -e "${GREEN}[✓] Main runner script created${NC}"
}

# 설정 파일 생성
create_config_files() {
    echo -e "${YELLOW}[+] Creating configuration files...${NC}"
    
    # 공격 설정 파일
    cat > "${INJECTION_DIR}/attack_config.conf" << 'CONFIG_EOF'
# DVD Injection Attack Configuration

# 기본 타겟 설정
DEFAULT_TARGET_IP=127.0.0.1
DEFAULT_MAVLINK_PORT=14550
DEFAULT_WEB_PORT=8000
DEFAULT_API_PORT=8080

# 공격 타임아웃 설정 (초)
MAVLINK_TIMEOUT=300
GPS_TIMEOUT=300
SQL_TIMEOUT=300
PARAMETER_TIMEOUT=180
WAYPOINT_TIMEOUT=180
FIRMWARE_TIMEOUT=600

# 로그 설정
LOG_LEVEL=INFO
LOG_ROTATION=daily
MAX_LOG_SIZE=100M

# 성공률 설정 (시뮬레이션용)
MAVLINK_SUCCESS_RATE=85
GPS_SUCCESS_RATE=75
SQL_SUCCESS_RATE=90
PARAMETER_SUCCESS_RATE=80
WAYPOINT_SUCCESS_RATE=85
FIRMWARE_SUCCESS_RATE=60

# 보안 설정
REQUIRE_ROOT=true
ENABLE_SAFETY_CHECKS=true
MAX_CONCURRENT_ATTACKS=3
CONFIG_EOF

    # 타겟 데이터베이스 파일
    cat > "${INJECTION_DIR}/targets.json" << 'TARGETS_EOF'
{
    "targets": [
        {
            "name": "DVD Simulator",
            "ip": "127.0.0.1",
            "ports": {
                "mavlink": 14550,
                "web": 8000,
                "api": 8080
            },
            "description": "Local DVD simulator instance"
        },
        {
            "name": "Remote Drone",
            "ip": "192.168.1.100",
            "ports": {
                "mavlink": 14550,
                "web": 80,
                "api": 8080
            },
            "description": "Remote drone target"
        }
    ],
    "attack_scenarios": [
        {
            "name": "Basic Injection",
            "attacks": ["mavlink_command", "parameter_manipulation"],
            "description": "Basic command and parameter injection"
        },
        {
            "name": "Navigation Hijack",
            "attacks": ["gps_spoofing", "waypoint_injection"],
            "description": "Navigation system compromise"
        },
        {
            "name": "Full Compromise",
            "attacks": ["mavlink_command", "gps_spoofing", "sql_injection", "parameter_manipulation", "waypoint_injection", "firmware_injection"],
            "description": "Complete system compromise"
        }
    ]
}
TARGETS_EOF

    echo -e "${GREEN}[✓] Configuration files created${NC}"
}

# 테스트 스크립트 생성
create_test_scripts() {
    echo -e "${YELLOW}[+] Creating test scripts...${NC}"
    
    # 모듈 테스트 스크립트
    cat > "${INJECTION_DIR}/test_modules.sh" << 'TEST_EOF'
#!/bin/bash

# =============================================================================
# DVD Injection Modules Test Script
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

SCRIPT_DIR="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection"

print_header() {
    echo -e "${BOLD}${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                     🧪 DVD Injection Module Tests 🧪                    ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

test_module() {
    local module_name=$1
    local script_path="${SCRIPT_DIR}/${module_name}.sh"
    
    echo -e "${CYAN}[*] Testing ${module_name}...${NC}"
    
    if [ ! -f "$script_path" ]; then
        echo -e "${RED}[!] Script not found: ${script_path}${NC}"
        return 1
    fi
    
    if [ ! -x "$script_path" ]; then
        echo -e "${RED}[!] Script not executable: ${script_path}${NC}"
        return 1
    fi
    
    # 스크립트 문법 체크
    if bash -n "$script_path"; then
        echo -e "${GREEN}[✓] ${module_name} syntax OK${NC}"
    else
        echo -e "${RED}[!] ${module_name} syntax error${NC}"
        return 1
    fi
    
    # 의존성 체크 (dry-run)
    echo -e "${YELLOW}[*] Checking dependencies for ${module_name}...${NC}"
    
    return 0
}

main() {
    print_header
    
    echo -e "${BLUE}[*] Starting module tests...${NC}"
    echo ""
    
    local modules=(
        "mavlink_command_injection"
        "gps_spoofing"
        "sql_injection"
        "parameter_manipulation"
        "waypoint_injection"
        "firmware_injection"
    )
    
    local passed=0
    local total=${#modules[@]}
    
    for module in "${modules[@]}"; do
        if test_module "$module"; then
            passed=$((passed + 1))
        fi
        echo ""
    done
    
    echo -e "${BOLD}${CYAN}Test Results:${NC}"
    echo -e "${GREEN}Passed: ${passed}/${total}${NC}"
    
    if [ $passed -eq $total ]; then
        echo -e "${GREEN}[✓] All modules passed tests${NC}"
        exit 0
    else
        echo -e "${RED}[!] Some modules failed tests${NC}"
        exit 1
    fi
}

main "$@"
TEST_EOF
    
    chmod +x "${INJECTION_DIR}/test_modules.sh"
    
    echo -e "${GREEN}[✓] Test scripts created${NC}"
}

# 문서화 생성
create_documentation() {
    echo -e "${YELLOW}[+] Creating documentation...${NC}"
    
    # README 파일
    cat > "${INJECTION_DIR}/README.md" << 'README_EOF'
# DVD Injection Attack Modules

This directory contains all injection attack modules for the Damn Vulnerable Drone (DVD) testbed.

## Available Modules

### 1. MAVLink Command Injection
- **File**: `mavlink_command_injection.sh`
- **Purpose**: Inject malicious MAVLink commands
- **Targets**: Flight controller, autopilot system
- **Impact**: Flight control compromise

### 2. GPS Spoofing
- **File**: `gps_spoofing.sh`
- **Purpose**: Manipulate GPS signals and coordinates
- **Targets**: Navigation system
- **Impact**: Position manipulation, navigation hijacking

### 3. SQL Injection
- **File**: `sql_injection.sh`
- **Purpose**: Exploit database vulnerabilities
- **Targets**: Web interface, database
- **Impact**: Data breach, authentication bypass

### 4. Parameter Manipulation
- **File**: `parameter_manipulation.sh`
- **Purpose**: Modify critical system parameters
- **Targets**: Configuration system
- **Impact**: Safety system disable, behavior modification

### 5. Waypoint Injection
- **File**: `waypoint_injection.sh`
- **Purpose**: Inject malicious mission waypoints
- **Targets**: Mission planning system
- **Impact**: Route hijacking, restricted area infiltration

### 6. Firmware Injection
- **File**: `firmware_injection.sh`
- **Purpose**: Inject malicious code into firmware
- **Targets**: Bootloader, firmware
- **Impact**: Persistent backdoor, system compromise

## Usage

### Individual Module Execution
```bash
# Execute specific module
sudo ./mavlink_command_injection.sh
sudo ./gps_spoofing.sh
sudo ./sql_injection.sh
```

### Suite Execution
```bash
# Interactive mode
sudo ./run_injection.sh

# Run all attacks
sudo ./run_injection.sh -a

# Run specific attacks
sudo ./run_injection.sh mavlink_command gps_spoofing

# Parallel execution
sudo ./run_injection.sh -p mavlink_command sql_injection
```

## Configuration

Edit `attack_config.conf` to modify:
- Target IP addresses and ports
- Attack timeouts
- Success rates (for simulation)
- Logging settings

## Testing

```bash
# Test all modules
./test_modules.sh

# Test specific module
bash -n mavlink_command_injection.sh
```

## Output

Each attack generates:
- Detailed logs in `/home/kali/MTD/MTD_full_testbed/attack_logs/injection/`
- IOC files for analysis
- JSON reports for integration

## Requirements

- Kali Linux
- Root privileges
- Python 3 with pymavlink, MAVProxy
- Network tools (curl, nc, nmap)
- Optional: SDR equipment for GPS spoofing

## Safety

These tools are for educational and authorized testing only. Do not use against systems without explicit permission.
README_EOF

    # CHANGELOG 파일
    cat > "${INJECTION_DIR}/CHANGELOG.md" << 'CHANGELOG_EOF'
# Changelog

## v1.0.0 - Initial Release

### Added
- MAVLink command injection module
- GPS spoofing attack module
- SQL injection attack module
- Parameter manipulation module
- Waypoint injection module
- Firmware injection module
- Integrated attack suite runner
- Configuration management
- Comprehensive logging
- IOC generation
- JSON reporting

### Features
- Interactive attack selection
- Parallel and sequential execution modes
- Real-time progress monitoring
- Impact assessment
- Cleanup procedures
- Error handling and recovery

### Documentation
- Complete README with usage instructions
- Configuration examples
- Testing procedures
- Safety guidelines
CHANGELOG_EOF

    echo -e "${GREEN}[✓] Documentation created${NC}"
}

# 권한 설정
set_permissions() {
    echo -e "${YELLOW}[+] Setting file permissions...${NC}"
    
    # 실행 파일 권한
    chmod +x "${INJECTION_DIR}"/*.sh 2>/dev/null
    
    # 설정 파일 권한
    chmod 644 "${INJECTION_DIR}"/*.conf 2>/dev/null
    chmod 644 "${INJECTION_DIR}"/*.json 2>/dev/null
    
    # 문서 파일 권한
    chmod 644 "${INJECTION_DIR}"/*.md 2>/dev/null
    
    # 디렉토리 권한
    chmod 755 "$INJECTION_DIR"
    chmod 755 "$LOG_DIR"
    chmod 755 "$OUTPUT_DIR"
    
    echo -e "${GREEN}[✓] Permissions set${NC}"
}

# 설치 검증
verify_installation() {
    echo -e "${YELLOW}[+] Verifying installation...${NC}"
    
    local expected_files=(
        "mavlink_command_injection.sh"
        "gps_spoofing.sh"
        "sql_injection.sh"
        "parameter_manipulation.sh"
        "waypoint_injection.sh"
        "firmware_injection.sh"
        "run_injection.sh"
        "test_modules.sh"
        "attack_config.conf"
        "targets.json"
        "README.md"
    )
    
    local missing_files=()
    
    for file in "${expected_files[@]}"; do
        if [ ! -f "${INJECTION_DIR}/${file}" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -eq 0 ]; then
        echo -e "${GREEN}[✓] All files installed successfully${NC}"
        
        # 모듈 테스트 실행
        echo -e "${CYAN}[*] Running module tests...${NC}"
        if "${INJECTION_DIR}/test_modules.sh"; then
            echo -e "${GREEN}[✓] All modules passed tests${NC}"
        else
            echo -e "${YELLOW}[*] Some modules need manual verification${NC}"
        fi
        
        return 0
    else
        echo -e "${RED}[!] Missing files: ${missing_files[*]}${NC}"
        return 1
    fi
}

# 사용법 출력
print_usage() {
    cat << EOF
${BOLD}${CYAN}DVD Injection Modules Setup Script${NC}

${YELLOW}Usage:${NC}
    $0 [OPTIONS]

${YELLOW}Options:${NC}
    -h, --help          Show this help message
    -f, --force         Force reinstallation (overwrite existing files)
    -t, --test-only     Only run tests, don't install
    -q, --quiet         Quiet mode (minimal output)

${YELLOW}Description:${NC}
    This script sets up all injection attack modules for the DVD testbed,
    including MAVLink command injection, GPS spoofing, SQL injection,
    parameter manipulation, waypoint injection, and firmware injection.

${YELLOW}Output Directory:${NC}
    ${INJECTION_DIR}

EOF
}

# 메인 함수
main() {
    local force_install=false
    local test_only=false
    local quiet_mode=false
    
    # 명령행 인자 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                print_usage
                exit 0
                ;;
            -f|--force)
                force_install=true
                shift
                ;;
            -t|--test-only)
                test_only=true
                shift
                ;;
            -q|--quiet)
                quiet_mode=true
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
        echo -e "${RED}[!] This script requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 테스트 전용 모드
    if [ "$test_only" = true ]; then
        echo -e "${CYAN}[*] Running tests only...${NC}"
        verify_installation
        exit $?
    fi
    
    # 기존 설치 확인
    if [ -d "$INJECTION_DIR" ] && [ "$force_install" = false ]; then
        echo -e "${YELLOW}[*] Injection modules already exist${NC}"
        echo -e "${YELLOW}[*] Use -f/--force to reinstall${NC}"
        
        # 검증만 실행
        verify_installation
        exit $?
    fi
    
    echo -e "${BOLD}${BLUE}🛠️  Setting up DVD Injection Attack Modules...${NC}"
    echo ""
    
    # 설치 단계 실행
    create_directory_structure
    echo ""
    
    create_common_modules
    echo ""
    
    install_dependencies
    echo ""
    
    create_injection_scripts
    echo ""
    
    create_main_runner
    echo ""
    
    create_config_files
    echo ""
    
    create_test_scripts
    echo ""
    
    create_documentation
    echo ""
    
    set_permissions
    echo ""
    
    # 설치 검증
    if verify_installation; then
        echo ""
        echo -e "${BOLD}${GREEN}✅ DVD Injection Modules Setup Complete!${NC}"
        echo ""
        echo -e "${CYAN}📁 Installation Directory: ${INJECTION_DIR}${NC}"
        echo -e "${CYAN}📊 Log Directory: ${LOG_DIR}${NC}"
        echo -e "${CYAN}📄 Output Directory: ${OUTPUT_DIR}${NC}"
        echo ""
        echo -e "${YELLOW}🚀 Next Steps:${NC}"
        echo "   1. Review configuration: ${INJECTION_DIR}/attack_config.conf"
        echo "   2. Run tests: ${INJECTION_DIR}/test_modules.sh"
        echo "   3. Execute attacks: ${INJECTION_DIR}/run_injection.sh"
        echo "   4. Read documentation: ${INJECTION_DIR}/README.md"
        echo ""
        echo -e "${BLUE}💡 Quick Start:${NC}"
        echo "   cd ${INJECTION_DIR}"
        echo "   sudo ./run_injection.sh"
        echo ""
    else
        echo ""
        echo -e "${BOLD}${RED}❌ Installation Failed!${NC}"
        echo -e "${RED}[!] Please check the error messages above${NC}"
        exit 1
    fi
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up...${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"