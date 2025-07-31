#!/bin/bash
# utils.sh - Common utilities for DVD attack tools

# Load colors if not already loaded
if [ -z "$RED" ]; then
    source "$(dirname "${BASH_SOURCE[0]}")/colors.sh"
fi

# Base directories
ATTACK_BASE_DIR="/home/kali/MTD/MTD_full_testbed"
LOG_DIR="$ATTACK_BASE_DIR/attack_logs"
OUTPUT_DIR="$ATTACK_BASE_DIR/attack_output"
IOC_DIR="$ATTACK_BASE_DIR/iocs"

# Create directories if they don't exist
create_directories() {
    mkdir -p "$LOG_DIR" "$OUTPUT_DIR" "$IOC_DIR"
    chmod 755 "$LOG_DIR" "$OUTPUT_DIR" "$IOC_DIR"
}

# Initialize directories
create_directories

# Logging functions
log_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[INFO]${NC} $message"
    if [ -n "$LOG_FILE" ]; then
        echo "[$timestamp] [INFO] $message" >> "$LOG_FILE"
    fi
}

log_success() {
    local message="$1" 
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[SUCCESS]${NC} $message"
    if [ -n "$LOG_FILE" ]; then
        echo "[$timestamp] [SUCCESS] $message" >> "$LOG_FILE"
    fi
}

log_warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARNING]${NC} $message"
    if [ -n "$LOG_FILE" ]; then
        echo "[$timestamp] [WARNING] $message" >> "$LOG_FILE"
    fi
}

log_error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR]${NC} $message"
    if [ -n "$LOG_FILE" ]; then
        echo "[$timestamp] [ERROR] $message" >> "$LOG_FILE"
    fi
}

# Directory getters - FIXED FUNCTIONS
get_log_dir() {
    echo "$LOG_DIR"
}

get_output_dir() {
    echo "$OUTPUT_DIR"
}

get_ioc_dir() {
    echo "$IOC_DIR"
}

# Tool checking function
check_required_tools() {
    local missing_tools=()
    
    for tool in "$@"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        return 1
    fi
    
    return 0
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        return 1
    fi
    return 0
}

# Network interface functions
get_wireless_interface() {
    local wifi_iface=$(iwconfig 2>/dev/null | grep "IEEE 802.11" | awk '{print $1}' | head -1)
    if [ -n "$wifi_iface" ]; then
        echo "$wifi_iface"
        return 0
    fi
    
    # Check for common interface names
    for iface in wlan0 wlan1 wifi0; do
        if ip link show "$iface" >/dev/null 2>&1; then
            echo "$iface"
            return 0
        fi
    done
    
    return 1
}

get_monitor_interface() {
    local monitor_iface=$(iwconfig 2>/dev/null | grep "Mode:Monitor" | awk '{print $1}' | head -1)
    if [ -n "$monitor_iface" ]; then
        echo "$monitor_iface"
        return 0
    fi
    
    # Check for DVD environment
    if iwconfig wlan0mon 2>/dev/null | grep -q "Mode:Monitor"; then
        echo "wlan0mon"
        return 0
    fi
    
    return 1
}

# DVD environment detection
is_dvd_environment() {
    # Check for DVD containers
    if docker ps 2>/dev/null | grep -q "dvd\|drone"; then
        return 0
    fi
    
    # Check for DVD network interfaces
    if ip addr show | grep -q "10.13.0\|192.168.13"; then
        return 0
    fi
    
    # Check for DVD wireless interfaces
    if iwconfig 2>/dev/null | grep -q "wlan0mon"; then
        return 0
    fi
    
    return 1
}

# Time utilities
get_timestamp() {
    date '+%Y%m%d_%H%M%S'
}

get_iso_timestamp() {
    date -Iseconds
}
