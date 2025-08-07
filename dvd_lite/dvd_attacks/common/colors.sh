#!/bin/bash
# DVD Common Colors - 공통 색상 정의

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
UNDERLINE='\033[4m'
NC='\033[0m' # No Color

# 로그 함수들
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_attack() {
    echo -e "${RED}[⚔️ ]${NC} $1"
}

log_target() {
    echo -e "${CYAN}[🎯]${NC} $1"
}

# 헤더 출력 함수
print_attack_header() {
    local attack_name="$1"
    echo -e "${BOLD}${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════════════╗"
    echo "║                      $attack_name"
    echo "╚═══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}
#!/bin/bash

# =============================================================================
# DVD Attack Framework - Colors and Styling Module
# =============================================================================
# 파일: dvd_lite/dvd_attacks/common/colors.sh
# 목적: 공격 스크립트용 색상 및 스타일 정의
# 작성자: MTD Testbed Team
# =============================================================================

# ANSI 색상 코드 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# 스타일 정의
BOLD='\033[1m'
DIM='\033[2m'
UNDERLINE='\033[4m'
BLINK='\033[5m'
REVERSE='\033[7m'
HIDDEN='\033[8m'

# 배경색 정의
BG_BLACK='\033[40m'
BG_RED='\033[41m'
BG_GREEN='\033[42m'
BG_YELLOW='\033[43m'
BG_BLUE='\033[44m'
BG_PURPLE='\033[45m'
BG_CYAN='\033[46m'
BG_WHITE='\033[47m'

# 상태별 색상 매핑
SUCCESS_COLOR="$GREEN"
ERROR_COLOR="$RED"
WARNING_COLOR="$YELLOW"
INFO_COLOR="$BLUE"
HIGHLIGHT_COLOR="$CYAN"
CRITICAL_COLOR="$BOLD$RED"

# 공격 타입별 색상
RECON_COLOR="$BLUE"
PROTOCOL_COLOR="$PURPLE"
DOS_COLOR="$RED"
INJECTION_COLOR="$YELLOW"
EXFIL_COLOR="$CYAN"
FIRMWARE_COLOR="$BOLD$RED"

# =============================================================================
# 출력 함수들
# =============================================================================

# 일반 출력 함수
print_colored() {
    local color="$1"
    local message="$2"
    echo -e "${color}${message}${NC}"
}

# 성공 메시지 출력
print_success() {
    local message="$1"
    echo -e "${SUCCESS_COLOR}[✓] ${message}${NC}"
}

# 오류 메시지 출력  
print_error() {
    local message="$1"
    echo -e "${ERROR_COLOR}[✗] ${message}${NC}"
}

# 경고 메시지 출력
print_warning() {
    local message="$1"
    echo -e "${WARNING_COLOR}[⚠] ${message}${NC}"
}

# 정보 메시지 출력
print_info() {
    local message="$1"
    echo -e "${INFO_COLOR}[ℹ] ${message}${NC}"
}

# 강조 메시지 출력
print_highlight() {
    local message="$1"
    echo -e "${HIGHLIGHT_COLOR}[★] ${message}${NC}"
}

# 중요 메시지 출력
print_critical() {
    local message="$1"
    echo -e "${CRITICAL_COLOR}[‼] ${message}${NC}"
}

# =============================================================================
# 공격 헤더 출력 함수들
# =============================================================================

# 기본 공격 헤더 출력
print_attack_header() {
    local title="$1"
    local width=80
    
    echo ""
    echo -e "${BOLD}${CYAN}$(printf '═%.0s' $(seq 1 $width))${NC}"
    echo -e "${BOLD}${CYAN}║$(printf '%*s' $(((width-${#title}-2)/2)) '')${title}$(printf '%*s' $(((width-${#title}-2)/2)) '')║${NC}"
    echo -e "${BOLD}${CYAN}$(printf '═%.0s' $(seq 1 $width))${NC}"
    echo ""
}

# 정찰 공격 헤더
print_recon_header() {
    local title="$1"
    echo -e "${BOLD}${RECON_COLOR}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      🔍 $title 🔍                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 프로토콜 조작 공격 헤더
print_protocol_header() {
    local title="$1"
    echo -e "${BOLD}${PROTOCOL_COLOR}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      🔧 $title 🔧                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# DoS 공격 헤더
print_dos_header() {
    local title="$1"
    echo -e "${BOLD}${DOS_COLOR}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      ⚡ $title ⚡                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 주입 공격 헤더
print_injection_header() {
    local title="$1"
    echo -e "${BOLD}${INJECTION_COLOR}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      💉 $title 💉                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 데이터 탈취 공격 헤더
print_exfil_header() {
    local title="$1"
    echo -e "${BOLD}${EXFIL_COLOR}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      📡 $title 📡                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 펌웨어 공격 헤더
print_firmware_header() {
    local title="$1"
    echo -e "${BOLD}${FIRMWARE_COLOR}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      🛡️ $title 🛡️                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# =============================================================================
# 진행 상황 표시 함수들
# =============================================================================

# 진행 바 출력
print_progress() {
    local current="$1"
    local total="$2"
    local message="$3"
    local percent=$((current * 100 / total))
    local filled=$((current * 50 / total))
    
    printf "\r${INFO_COLOR}[%3d%%] [" "$percent"
    printf "%*s" $filled | tr ' ' '█'
    printf "%*s" $((50 - filled)) | tr ' ' '░'
    printf "] %s${NC}" "$message"
    
    if [ "$current" -eq "$total" ]; then
        echo ""
    fi
}

# 스피너 애니메이션
show_spinner() {
    local pid=$1
    local message="$2"
    local spin_chars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    
    while kill -0 $pid 2>/dev/null; do
        printf "\r${INFO_COLOR}[%s] %s${NC}" "${spin_chars:$i:1}" "$message"
        i=$(((i + 1) % ${#spin_chars}))
        sleep 0.1
    done
    printf "\r"
}

# =============================================================================
# 상태 표시 함수들
# =============================================================================

# 공격 단계 표시
print_attack_step() {
    local step_num="$1"
    local total_steps="$2"
    local step_name="$3"
    
    echo -e "${BOLD}${YELLOW}📋 Step $step_num/$total_steps: $step_name${NC}"
}

# 타겟 정보 표시
print_target_info() {
    local target="$1"
    local description="$2"
    
    echo -e "${HIGHLIGHT_COLOR}🎯 Target: $target${NC}"
    if [ -n "$description" ]; then
        echo -e "${GRAY}   Description: $description${NC}"
    fi
}

# 공격 결과 요약 표시
print_attack_summary() {
    local attack_name="$1"
    local status="$2"
    local duration="$3"
    local ioc_count="$4"
    
    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}                              Attack Summary                               ${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════════════════${NC}"
    
    if [ "$status" = "success" ]; then
        print_success "Attack: $attack_name"
    else
        print_error "Attack: $attack_name"
    fi
    
    echo -e "${INFO_COLOR}⏱️  Duration: $duration seconds${NC}"
    echo -e "${INFO_COLOR}🔍 IOCs Generated: $ioc_count${NC}"
    echo ""
}

# =============================================================================
# 테이블 출력 함수들
# =============================================================================

# 테이블 헤더 출력
print_table_header() {
    local -a headers=("$@")
    local width=20
    
    printf "${BOLD}${BLUE}┌"
    for ((i=0; i<${#headers[@]}; i++)); do
        printf "$(printf '─%.0s' $(seq 1 $width))"
        if [ $i -lt $((${#headers[@]} - 1)) ]; then
            printf "┬"
        fi
    done
    printf "┐${NC}\n"
    
    printf "${BOLD}${BLUE}│"
    for header in "${headers[@]}"; do
        printf "%-${width}s│" "$header"
    done
    printf "${NC}\n"
    
    printf "${BOLD}${BLUE}├"
    for ((i=0; i<${#headers[@]}; i++)); do
        printf "$(printf '─%.0s' $(seq 1 $width))"
        if [ $i -lt $((${#headers[@]} - 1)) ]; then
            printf "┼"
        fi
    done
    printf "┤${NC}\n"
}

# 테이블 행 출력
print_table_row() {
    local -a columns=("$@")
    local width=20
    
    printf "│"
    for column in "${columns[@]}"; do
        printf "%-${width}s│" "$column"
    done
    printf "\n"
}

# 테이블 푸터 출력
print_table_footer() {
    local column_count="$1"
    local width=20
    
    printf "${BLUE}└"
    for ((i=0; i<column_count; i++)); do
        printf "$(printf '─%.0s' $(seq 1 $width))"
        if [ $i -lt $((column_count - 1)) ]; then
            printf "┴"
        fi
    done
    printf "┘${NC}\n"
}

# =============================================================================
# 유틸리티 함수들
# =============================================================================

# 타임스탬프 출력
timestamp() {
    echo -e "${GRAY}[$(date '+%Y-%m-%d %H:%M:%S')]${NC}"
}

# 시뮬레이션 대기 (점진적 출력)
simulation_wait() {
    local min_time="$1"
    local max_time="$2"
    local wait_time=$((min_time + RANDOM % (max_time - min_time + 1)))
    
    for ((i=0; i<wait_time; i++)); do
        printf "${GRAY}.${NC}"
        sleep 1
    done
    echo ""
}

# DVD 로고 출력
print_dvd_logo() {
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║ ██████╗ ██╗   ██╗██████╗      █████╗ ████████╗████████╗ █████╗  ██████╗██╗║"
    echo "║ ██╔══██╗██║   ██║██╔══██╗    ██╔══██╗╚══██╔══╝╚══██╔══╝██╔══██╗██╔════╝██║║"
    echo "║ ██║  ██║██║   ██║██║  ██║    ███████║   ██║      ██║   ███████║██║     ██║║"
    echo "║ ██║  ██║╚██╗ ██╔╝██║  ██║    ██╔══██║   ██║      ██║   ██╔══██║██║     ██║║"
    echo "║ ██████╔╝ ╚████╔╝ ██████╔╝    ██║  ██║   ██║      ██║   ██║  ██║╚██████╗██║║"
    echo "║ ╚═════╝   ╚═══╝  ╚═════╝     ╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝║"
    echo "║                   Damn Vulnerable Drone Attack Framework                  ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 경고 메시지 출력
print_legal_warning() {
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                              ⚠️  WARNING ⚠️                               ║"
    echo "║                                                                           ║"
    echo "║  This tool is for educational and authorized testing purposes ONLY!       ║"
    echo "║  Unauthorized access to computer systems is illegal.                      ║"
    echo "║  Users are responsible for compliance with applicable laws.               ║"
    echo "║                                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

# 성공/실패 아이콘
SUCCESS_ICON="✓"
FAILURE_ICON="✗" 
WARNING_ICON="⚠"
INFO_ICON="ℹ"
CRITICAL_ICON="‼"
TARGET_ICON="🎯"
ATTACK_ICON="⚔️"
SHIELD_ICON="🛡️"