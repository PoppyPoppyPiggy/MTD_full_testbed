#!/bin/bash

# =============================================================================
# Enhanced DVD Attack Tools Directory Structure Setup
# =============================================================================
# 파일: setup_directories.sh
# 목적: 전체 DVD 공격 테스트베드 디렉토리 구조 생성
# 작성자: MTD Testbed Team
# =============================================================================

echo "🔧 Enhanced DVD Attack Tools 디렉토리 구조 생성 중..."

# Base directory
BASE_DIR="/home/kali/MTD/MTD_full_testbed"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}📁 전체 디렉토리 구조 생성...${NC}"

# Create comprehensive directory structure
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/reconnaissance"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/protocol_tampering"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/denial_of_service"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/injection"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/exfiltration"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/firmware_attacks"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/common"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/core"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/registry"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/utils"

# Output directories
mkdir -p "$BASE_DIR/attack_logs/reconnaissance"
mkdir -p "$BASE_DIR/attack_logs/protocol_tampering"
mkdir -p "$BASE_DIR/attack_logs/denial_of_service"
mkdir -p "$BASE_DIR/attack_logs/injection"
mkdir -p "$BASE_DIR/attack_logs/exfiltration"
mkdir -p "$BASE_DIR/attack_logs/firmware_attacks"

mkdir -p "$BASE_DIR/attack_output/reconnaissance"
mkdir -p "$BASE_DIR/attack_output/protocol_tampering"
mkdir -p "$BASE_DIR/attack_output/denial_of_service"
mkdir -p "$BASE_DIR/attack_output/injection"
mkdir -p "$BASE_DIR/attack_output/exfiltration"
mkdir -p "$BASE_DIR/attack_output/firmware_attacks"

mkdir -p "$BASE_DIR/iocs"
mkdir -p "$BASE_DIR/reports"
mkdir -p "$BASE_DIR/temp"

echo -e "${GREEN}✅ 디렉토리 생성 완료:${NC}"
echo -e "${BLUE}├── $BASE_DIR/${NC}"
echo -e "${BLUE}│   ├── dvd_lite/dvd_attacks/${NC}"
echo -e "${BLUE}│   │   ├── reconnaissance/          ${YELLOW}# 정찰 공격${NC}"
echo -e "${BLUE}│   │   ├── protocol_tampering/      ${YELLOW}# 프로토콜 변조${NC}"
echo -e "${BLUE}│   │   ├── denial_of_service/       ${YELLOW}# 서비스 거부${NC}"
echo -e "${BLUE}│   │   ├── injection/               ${YELLOW}# 주입 공격${NC}"
echo -e "${BLUE}│   │   ├── exfiltration/            ${YELLOW}# 데이터 탈취${NC}"
echo -e "${BLUE}│   │   ├── firmware_attacks/        ${YELLOW}# 펌웨어 공격${NC}"
echo -e "${BLUE}│   │   ├── common/                  ${YELLOW}# 공통 유틸리티${NC}"
echo -e "${BLUE}│   │   ├── core/                    ${YELLOW}# 핵심 모듈${NC}"
echo -e "${BLUE}│   │   ├── registry/                ${YELLOW}# 공격 레지스트리${NC}"
echo -e "${BLUE}│   │   └── utils/                   ${YELLOW}# 도구 모음${NC}"
echo -e "${BLUE}│   ├── attack_logs/                 ${YELLOW}# 실행 로그${NC}"
echo -e "${BLUE}│   ├── attack_output/               ${YELLOW}# 결과 리포트${NC}"
echo -e "${BLUE}│   ├── iocs/                        ${YELLOW}# IOC 파일${NC}"
echo -e "${BLUE}│   ├── reports/                     ${YELLOW}# 종합 리포트${NC}"
echo -e "${BLUE}│   └── temp/                        ${YELLOW}# 임시 파일${NC}"

# Set proper permissions
echo -e "${CYAN}🔐 권한 설정...${NC}"
find "$BASE_DIR" -type d -exec chmod 755 {} \;
chmod 755 "$BASE_DIR"

# Create common colors.sh if not exists
if [ ! -f "$BASE_DIR/dvd_lite/dvd_attacks/common/colors.sh" ]; then
    echo -e "${YELLOW}📝 공통 colors.sh 생성...${NC}"
    cat > "$BASE_DIR/dvd_lite/dvd_attacks/common/colors.sh" << 'EOF'
#!/bin/bash
# Color definitions for DVD Attack Tools

# Regular Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'

# Bold Colors
BOLD_RED='\033[1;31m'
BOLD_GREEN='\033[1;32m'
BOLD_YELLOW='\033[1;33m'
BOLD_BLUE='\033[1;34m'
BOLD_PURPLE='\033[1;35m'
BOLD_CYAN='\033[1;36m'

# Special formatting
BOLD='\033[1m'
DIM='\033[2m'
UNDERLINE='\033[4m'
BLINK='\033[5m'
REVERSE='\033[7m'
HIDDEN='\033[8m'

# Reset
NC='\033[0m' # No Color / Reset

# Background Colors
BG_RED='\033[41m'
BG_GREEN='\033[42m'
BG_YELLOW='\033[43m'
BG_BLUE='\033[44m'
BG_PURPLE='\033[45m'
BG_CYAN='\033[46m'
BG_WHITE='\033[47m'
EOF
    chmod +x "$BASE_DIR/dvd_lite/dvd_attacks/common/colors.sh"
fi

# Create common utils.sh if not exists  
if [ ! -f "$BASE_DIR/dvd_lite/dvd_attacks/common/utils.sh" ]; then
    echo -e "${YELLOW}📝 공통 utils.sh 생성...${NC}"
    cat > "$BASE_DIR/dvd_lite/dvd_attacks/common/utils.sh" << 'EOF'
#!/bin/bash
# Common utility functions for DVD Attack Tools

# Load colors
source "$(dirname "${BASH_SOURCE[0]}")/colors.sh"

# Logging function
log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        "INFO")
            echo -e "${BLUE}[INFO]${NC} ${timestamp} - $message"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - $message"
            ;;
        "WARNING")
            echo -e "${YELLOW}[WARNING]${NC} ${timestamp} - $message"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} ${timestamp} - $message"
            ;;
        "DEBUG")
            echo -e "${PURPLE}[DEBUG]${NC} ${timestamp} - $message"
            ;;
        *)
            echo -e "${WHITE}[LOG]${NC} ${timestamp} - $message"
            ;;
    esac
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_message "ERROR" "This script requires root privileges"
        log_message "INFO" "Please run: sudo $0"
        exit 1
    fi
}

# Check required tools
check_required_tools() {
    local tools=("$@")
    local missing_tools=()
    
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_message "WARNING" "Missing required tools: ${missing_tools[*]}"
        log_message "INFO" "Installing missing tools..."
        
        apt-get update -qq
        apt-get install -y "${missing_tools[@]}"
        
        if [ $? -eq 0 ]; then
            log_message "SUCCESS" "All tools installed successfully"
        else
            log_message "ERROR" "Failed to install required tools"
            return 1
        fi
    fi
    
    return 0
}

# Generate random string
generate_random_string() {
    local length=${1:-8}
    tr -dc A-Za-z0-9 </dev/urandom | head -c "$length"
}

# Get current timestamp
get_timestamp() {
    date '+%Y%m%d_%H%M%S'
}

# Progress bar function
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))
    
    printf "\r${CYAN}Progress: [%-${width}s] %d%% (%d/%d)${NC}" \
           "$(printf "%*s" "$filled" | tr ' ' '█')" \
           "$percentage" "$current" "$total"
    
    if [ "$current" -eq "$total" ]; then
        echo ""
    fi
}

# Wait with spinner
wait_with_spinner() {
    local duration=$1
    local message=${2:-"Please wait"}
    local spinner='|/-\'
    
    for ((i=0; i<duration; i++)); do
        printf "\r${YELLOW}%s %c${NC}" "$message" "${spinner:$((i%4)):1}"
        sleep 1
    done
    echo ""
}

# Check network connectivity
check_connectivity() {
    local target=$1
    local port=${2:-22}
    
    if timeout 3 nc -z "$target" "$port" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Create IOC entry
create_ioc() {
    local category=$1
    local description=$2
    local timestamp=$(date +%s)
    
    echo "${category}:${description}_${timestamp}"
}

# Cleanup function
cleanup_temp_files() {
    local temp_dir="/home/kali/MTD/MTD_full_testbed/temp"
    
    if [ -d "$temp_dir" ]; then
        find "$temp_dir" -type f -mtime +1 -delete 2>/dev/null
        log_message "INFO" "Cleaned up temporary files"
    fi
}

# Check DVD system status
check_dvd_status() {
    local targets=(
        "10.13.0.5:22"    # Simulator
        "10.13.0.2:22"    # Flight Controller  
        "10.13.0.3:22"    # Companion Computer
        "10.13.0.4:22"    # Ground Control
        "10.13.0.6:14550" # QGroundControl
    )
    
    local names=(
        "Simulator"
        "Flight Controller" 
        "Companion Computer"
        "Ground Control"
        "QGroundControl"
    )
    
    echo -e "${BOLD}${CYAN}🔍 DVD System Status Check${NC}"
    echo "=========================="
    
    for i in "${!targets[@]}"; do
        local target="${targets[$i]}"
        local name="${names[$i]}"
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        if check_connectivity "$ip" "$port"; then
            echo -e "${GREEN}✅ ${name} (${target})${NC}"
        else
            echo -e "${RED}❌ ${name} (${target})${NC}"
        fi
    done
    echo ""
}
EOF
    chmod +x "$BASE_DIR/dvd_lite/dvd_attacks/common/utils.sh"
fi

echo ""
echo -e "${GREEN}🎯 다음 단계:${NC}"
echo -e "${YELLOW}1. 공격 스크립트 배치:${NC}"
echo "   • Protocol Tampering: $BASE_DIR/dvd_lite/dvd_attacks/protocol_tampering/"
echo "   • Reconnaissance: $BASE_DIR/dvd_lite/dvd_attacks/reconnaissance/"
echo "   • Denial of Service: $BASE_DIR/dvd_lite/dvd_attacks/denial_of_service/"
echo "   • Injection Attacks: $BASE_DIR/dvd_lite/dvd_attacks/injection/"
echo "   • Data Exfiltration: $BASE_DIR/dvd_lite/dvd_attacks/exfiltration/"
echo "   • Firmware Attacks: $BASE_DIR/dvd_lite/dvd_attacks/firmware_attacks/"
echo ""
echo -e "${YELLOW}2. 메인 실행 스크립트:${NC}"
echo "   • $BASE_DIR/quick_start.sh (전체 공격 스위트)"
echo "   • $BASE_DIR/run_all_attacks.sh (자동화된 실행)"
echo "   • $BASE_DIR/view_results.sh (결과 조회)"
echo ""
echo -e "${YELLOW}3. 실행 권한 부여:${NC}"
echo "   chmod +x $BASE_DIR/*.sh"
echo "   find $BASE_DIR/dvd_lite/dvd_attacks -name '*.sh' -exec chmod +x {} \\;"
echo ""
echo -e "${YELLOW}4. 실행 예시:${NC}"
echo "   sudo $BASE_DIR/quick_start.sh                    # 빠른 시작"
echo "   sudo $BASE_DIR/run_all_attacks.sh               # 전체 공격"
echo "   sudo $BASE_DIR/dvd_lite/dvd_attacks/protocol_tampering/run_protocol_tampering.sh"
echo ""
echo -e "${GREEN}✅ Enhanced 디렉토리 구조 생성 완료!${NC}"
echo -e "${CYAN}📋 생성된 구조:${NC}"
echo "   • 6개 공격 카테고리 디렉토리"
echo "   • 공통 유틸리티 및 색상 정의"
echo "   • 로그 및 출력 디렉토리"
echo "   • 임시 파일 및 리포트 디렉토리"
echo ""
echo -e "${BOLD}${PURPLE}🚀 이제 enhanced_quick_start.sh를 실행하여 전체 테스트를 시작하세요!${NC}"