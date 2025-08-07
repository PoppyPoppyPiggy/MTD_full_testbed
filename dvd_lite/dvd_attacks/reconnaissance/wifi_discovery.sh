#!/bin/bash
# wifi_discovery.sh - WiFi Network Discovery Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/wifi_discovery.sh
# Purpose: Pure WiFi network discovery attack execution

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="WiFi Network Discovery"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}         WiFi Network Discovery            ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_wifi_discovery() {
    local scan_duration=${1:-30}
    
    log_info "Starting WiFi discovery attack"
    log_info "Scan duration: ${scan_duration} seconds"
    
    # Monitor mode setup
    local monitor_iface
    monitor_iface=$(setup_monitor_mode)
    local setup_result=$?
    
    if [ $setup_result -ne 0 ] || [ -z "$monitor_iface" ]; then
        log_error "Failed to setup monitor mode"
        return 1
    fi
    
    log_success "Monitor mode active: $monitor_iface"
    
    # Network scanning
    perform_wifi_scan "$monitor_iface" "$scan_duration"
    local scan_result=$?
    
    # Cleanup
    cleanup_monitor_mode "$monitor_iface"
    
    if [ $scan_result -eq 0 ]; then
        log_success "WiFi discovery attack completed successfully"
        return 0
    else
        log_error "WiFi discovery attack failed"
        return 1
    fi
}

perform_wifi_scan() {
    local monitor_iface="$1"
    local scan_duration="$2"
    
    log_info "Scanning WiFi networks..."
    echo -e "${YELLOW}Scanning for $scan_duration seconds...${NC}"
    
    local timestamp=$(date +%s)
    local temp_scan="/tmp/wifi_scan_$timestamp"
    
    # Start airodump-ng scan
    airodump-ng "$monitor_iface" \
        --write-interval 1 \
        --output-format csv \
        --write "$temp_scan" >/dev/null 2>&1 &
    
    local scan_pid=$!
    
    # Progress indicator
    for ((i=1; i<=scan_duration; i++)); do
        echo -ne "\rScanning... [$i/$scan_duration]"
        sleep 1
    done
    echo ""
    
    # Stop scan
    kill $scan_pid 2>/dev/null
    pkill airodump-ng 2>/dev/null
    sleep 2
    
    # Process results
    process_scan_results "$temp_scan"
    local process_result=$?
    
    # Cleanup temp files
    rm -f "$temp_scan"* 2>/dev/null
    
    return $process_result
}

process_scan_results() {
    local scan_prefix="$1"
    local csv_file="${scan_prefix}-01.csv"
    
    # Find actual CSV file
    if [ ! -f "$csv_file" ]; then
        csv_file=$(find /tmp -name "wifi_scan_*.csv" -type f -newermt "2 minutes ago" | head -1)
    fi
    
    if [ -z "$csv_file" ] || [ ! -f "$csv_file" ] || [ ! -s "$csv_file" ]; then
        log_warning "No scan results found"
        return 1
    fi
    
    log_info "Processing scan results: $csv_file"
    
    # Parse CSV and display results
    parse_and_display_networks "$csv_file"
    return $?
}

parse_and_display_networks() {
    local csv_file="$1"
    
    python3 << PYEOF
import csv
import sys

def parse_wifi_networks(filename):
    try:
        with open('$csv_file', 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if not content.strip():
            print("Empty scan results")
            return False
        
        lines = content.split('\n')
        ap_section = []
        
        # Find AP section
        for i, line in enumerate(lines):
            if 'BSSID' in line and ('First time seen' in line or 'channel' in line):
                for j in range(i, len(lines)):
                    current_line = lines[j].strip()
                    if current_line == '' or 'Station MAC' in current_line:
                        break
                    ap_section.append(lines[j])
                break
        
        if len(ap_section) <= 1:
            print("No access points found")
            return False
        
        reader = csv.DictReader(ap_section)
        drone_networks = []
        all_networks = []
        
        for row in reader:
            try:
                essid = (row.get('ESSID', '') or row.get(' ESSID', '')).strip()
                bssid = (row.get('BSSID', '') or row.get(' BSSID', '')).strip()
                channel = (row.get('channel', '') or row.get(' channel', '')).strip()
                privacy = (row.get('Privacy', '') or row.get(' Privacy', '')).strip()
                power = (row.get('Power', '') or row.get(' Power', '')).strip()
                
                if bssid:
                    network = {
                        'essid': essid if essid else 'Hidden',
                        'bssid': bssid,
                        'channel': channel if channel else 'N/A',
                        'privacy': privacy if privacy else 'N/A',
                        'power': power if power else 'N/A'
                    }
                    
                    all_networks.append(network)
                    
                    # Check for drone/DVD related networks
                    drone_keywords = ['drone', 'dvd', 'ardupilot', 'mavlink', 'wifi', 'quadcopter', 'uav', 'Drone_Wifi']
                    if any(keyword.lower() in essid.lower() for keyword in drone_keywords):
                        drone_networks.append(network)
                
            except Exception:
                continue
        
        # Display results
        print(f"\\n📡 Networks discovered: {len(all_networks)}")
        
        if drone_networks:
            print(f"\\n🎯 Drone/DVD networks found: {len(drone_networks)}")
            for net in drone_networks:
                print(f"   • {net['essid']} ({net['bssid']}) [CH:{net['channel']}] [PWR:{net['power']}] [{net['privacy']}]")
        
        print(f"\\n📋 All networks:")
        for i, net in enumerate(all_networks[:10], 1):
            print(f"   {i}. {net['essid']} ({net['bssid']}) [CH:{net['channel']}] [{net['privacy']}]")
        
        if len(all_networks) > 10:
            print(f"   ... and {len(all_networks)-10} more networks")
        
        return True
        
    except Exception as e:
        print(f"Error processing scan results: {e}")
        return False

if parse_wifi_networks('$csv_file'):
    sys.exit(0)
else:
    sys.exit(1)
PYEOF
    
    return $?
}

setup_monitor_mode() {
    # Check for existing monitor interface
    local monitor_iface=$(iwconfig 2>/dev/null | grep "Mode:Monitor" | awk '{print $1}' | head -1)
    
    if [ -n "$monitor_iface" ]; then
        echo "$monitor_iface"
        return 0
    fi
    
    # DVD environment check
    if iwconfig wlan0mon 2>/dev/null | grep -q "Mode:Monitor"; then
        echo "wlan0mon"
        return 0
    fi
    
    # Find WiFi interface
    local wifi_iface=$(iwconfig 2>/dev/null | grep "IEEE 802.11" | awk '{print $1}' | head -1)
    
    if [ -z "$wifi_iface" ]; then
        if ip link show wlan0 >/dev/null 2>&1; then
            wifi_iface="wlan0"
        else
            log_error "No WiFi interface found"
            return 1
        fi
    fi
    
    log_info "Setting up monitor mode on $wifi_iface"
    
    # Try direct monitor mode setup (for DVD environment)
    if [ "$wifi_iface" = "wlan0" ]; then
        if ip link set "$wifi_iface" down 2>/dev/null && \
           iw "$wifi_iface" set type monitor 2>/dev/null && \
           ip link set "$wifi_iface" up 2>/dev/null; then
            echo "$wifi_iface"
            return 0
        fi
    fi
    
    # Try airmon-ng
    if command -v airmon-ng >/dev/null 2>&1; then
        # Only kill processes if not in DVD environment
        if ! pgrep -f "dvd\|docker" >/dev/null; then
            sudo airmon-ng check kill >/dev/null 2>&1
        fi
        
        sudo airmon-ng start "$wifi_iface" >/dev/null 2>&1
        
        monitor_iface=$(iwconfig 2>/dev/null | grep "Mode:Monitor" | awk '{print $1}' | head -1)
        if [ -n "$monitor_iface" ]; then
            echo "$monitor_iface"
            return 0
        fi
    fi
    
    return 1
}

cleanup_monitor_mode() {
    local monitor_iface="$1"
    
    # Stop any running processes
    pkill airodump-ng 2>/dev/null
    
    # Restore interface if it's not wlan0mon (DVD default)
    if [ "$monitor_iface" != "wlan0mon" ] && [ -n "$monitor_iface" ]; then
        log_info "Restoring interface: $monitor_iface"
        
        # Try to restore to managed mode
        if iwconfig "$monitor_iface" mode managed 2>/dev/null; then
            log_info "Interface restored to managed mode"
        fi
    fi
}

# Main execution function
main() {
    print_attack_banner
    
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Check required tools
    local required_tools=("python3")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    # Optional tools warning
    local optional_tools=("airmon-ng" "airodump-ng" "iwconfig" "iw")
    local missing_optional=()
    
    for tool in "${optional_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_optional+=("$tool")
        fi
    done
    
    if [ ${#missing_optional[@]} -gt 0 ]; then
        log_warning "Some wireless tools missing: ${missing_optional[*]}"
        log_info "Install with: sudo apt-get install aircrack-ng wireless-tools iw"
    fi
    
    # Execute attack
    execute_wifi_discovery "$@"
    exit $?
}

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi