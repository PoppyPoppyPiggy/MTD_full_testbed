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
