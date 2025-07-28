#!/bin/bash
# utils.sh - Common utilities for DVD attack tools
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# Directories
ATTACK_BASE_DIR="/home/kali/MTD/MTD_full_testbed"
LOG_DIR="$ATTACK_BASE_DIR/attack_logs"
OUTPUT_DIR="$ATTACK_BASE_DIR/attack_output"
IOC_DIR="$ATTACK_BASE_DIR/iocs"

# Create directories
mkdir -p "$LOG_DIR" "$OUTPUT_DIR" "$IOC_DIR"

# Logging functions
log_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[INFO]${NC} $message"
    echo "[$timestamp] [INFO] $message" >> "$LOG_FILE"
}

log_success() {
    local message="$1" 
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[SUCCESS]${NC} $message"
    echo "[$timestamp] [SUCCESS] $message" >> "$LOG_FILE"
}

log_warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARNING]${NC} $message"
    echo "[$timestamp] [WARNING] $message" >> "$LOG_FILE"
}

log_error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR]${NC} $message"
    echo "[$timestamp] [ERROR] $message" >> "$LOG_FILE"
}

# Directory getters
get_log_dir() {
    echo "$LOG_DIR"
}

get_output_dir() {
    echo "$OUTPUT_DIR"
}

get_ioc_dir() {
    echo "$IOC_DIR"
}

# Tool checking
check_required_tools() {
    local missing_tools=()
    
    for tool in "$@"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Install with: sudo apt install ${missing_tools[*]}"
        exit 1
    fi
}

# Network utilities
is_port_open() {
    local host="$1"
    local port="$2"
    local protocol="${3:-tcp}"
    
    if [ "$protocol" == "udp" ]; then
        timeout 3 nc -u -z "$host" "$port" 2>/dev/null
    else
        timeout 3 nc -z "$host" "$port" 2>/dev/null
    fi
}

# IOC management
save_ioc() {
    local ioc="$1"
    local attack_name="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$timestamp] [$attack_name] $ioc" >> "$IOC_DIR/all_iocs.txt"
}

# Attack result formatting
print_attack_result() {
    local attack_name="$1"
    local result="$2"
    local details="$3"
    
    echo -e "${CYAN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           Attack Result               ║${NC}"
    echo -e "${CYAN}╠═══════════════════════════════════════╣${NC}"
    echo -e "${CYAN}║ Attack: ${WHITE}$attack_name${CYAN}$(printf '%*s' $((25-${#attack_name})) '')║${NC}"
    
    if [[ "$result" == "SUCCESS" ]]; then
        echo -e "${CYAN}║ Result: ${GREEN}$result${CYAN}$(printf '%*s' $((25-${#result})) '')║${NC}"
    else
        echo -e "${CYAN}║ Result: ${RED}$result${CYAN}$(printf '%*s' $((25-${#result})) '')║${NC}"
    fi
    
    echo -e "${CYAN}╚═══════════════════════════════════════╝${NC}"
    
    if [ -n "$details" ]; then
        echo -e "${YELLOW}Details:${NC} $details"
    fi
}