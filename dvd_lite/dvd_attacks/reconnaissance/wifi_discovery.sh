#!/bin/bash
# wifi_discovery.sh - WiFi Network Discovery Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/wifi_discovery.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="WiFi Network Discovery"
LOG_FILE="$(get_log_dir)/wifi_discovery.log"

print_attack_banner() {
    echo -e "${CYAN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        WiFi Network Discovery        ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════╝${NC}"
}

execute_attack() {
    log_info "Starting WiFi Network Discovery"
    
    # Monitor mode setup
    setup_monitor_mode
    local monitor_iface="$?"
    
    if [ -z "$monitor_iface" ]; then
        log_error "Failed to setup monitor mode"
        return 1
    fi
    
    # Network scanning
    local scan_duration=${1:-30}
    log_info "Scanning for $scan_duration seconds..."
    
    local output_prefix="$(get_output_dir)/wifi_scan_$(date +%s)"
    
    timeout "$scan_duration" airodump-ng "$monitor_iface" \
        --write-interval 1 \
        --output-format csv \
        --write "$output_prefix" >/dev/null 2>&1 &
    
    local scan_pid=$!
    
    # Progress indicator
    for ((i=1; i<=scan_duration; i++)); do
        echo -ne "\rScanning... [$i/$scan_duration]"
        sleep 1
    done
    echo ""
    
    # Kill scan process
    kill $scan_pid 2>/dev/null
    pkill airodump-ng 2>/dev/null
    
    # Parse results
    parse_wifi_results "$output_prefix-01.csv"
    
    log_success "WiFi discovery completed"
    return 0
}

parse_wifi_results() {
    local csv_file="$1"
    
    if [ ! -f "$csv_file" ]; then
        log_error "Scan results not found: $csv_file"
        return 1
    fi
    
    # Python parser for CSV results
    cat > "/tmp/wifi_parser.py" << 'PYEOF'
#!/usr/bin/env python3
import sys
import csv
import re

def parse_wifi_csv(filename):
    try:
        with open(filename, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        ap_section = []
        
        # Find AP section
        for i, line in enumerate(lines):
            if 'BSSID' in line and 'First time seen' in line:
                for j in range(i, len(lines)):
                    if lines[j].strip() == '' or 'Station MAC' in lines[j]:
                        break
                    ap_section.append(lines[j])
                break
        
        if len(ap_section) <= 1:
            print("No access points found")
            return
        
        # Parse AP data
        reader = csv.DictReader(ap_section)
        dvd_networks = []
        all_networks = []
        
        for row in reader:
            try:
                essid = row.get('ESSID', '').strip()
                bssid = row.get('BSSID', '').strip()
                channel = row.get(' channel', 'N/A').strip()
                privacy = row.get(' Privacy', 'N/A').strip()
                power = row.get(' Power', 'N/A').strip()
                
                if essid and bssid:
                    network_info = {
                        'essid': essid,
                        'bssid': bssid, 
                        'channel': channel,
                        'privacy': privacy,
                        'power': power
                    }
                    
                    all_networks.append(network_info)
                    
                    # Check for DVD-related networks
                    dvd_keywords = ['drone', 'dvd', 'ardupilot', 'mavlink', 'wifi', 'quadcopter', 'uav']
                    if any(keyword in essid.lower() for keyword in dvd_keywords):
                        dvd_networks.append(network_info)
                        print(f"🎯 DVD-RELATED: {essid} ({bssid}) [CH:{channel}] [PWR:{power}] [{privacy}]")
                    
            except Exception as e:
                continue
        
        # Display all networks
        print(f"\n📡 Total networks found: {len(all_networks)}")
        for net in all_networks:
            print(f"   {net['essid']} ({net['bssid']}) [CH:{net['channel']}] [{net['privacy']}]")
        
        # Generate IOCs
        ioc_file = '/tmp/wifi_iocs.txt'
        with open(ioc_file, 'w') as f:
            for net in dvd_networks:
                f.write(f"WIFI_NETWORK:{net['essid']}:{net['bssid']}\n")
                f.write(f"WIFI_CHANNEL:{net['channel']}\n")
                f.write(f"WIFI_ENCRYPTION:{net['privacy']}\n")
        
        print(f"\n✅ IOCs saved to: {ioc_file}")
        print(f"🎯 DVD-related networks: {len(dvd_networks)}")
        
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        return False
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 wifi_parser.py <csv_file>")
        sys.exit(1)
    
    parse_wifi_csv(sys.argv[1])
PYEOF
    
    python3 "/tmp/wifi_parser.py" "$csv_file"
}

setup_monitor_mode() {
    # Check for existing monitor interface
    local monitor_iface=$(iwconfig 2>/dev/null | grep "Mode:Monitor" | awk '{print $1}' | head -1)
    
    if [ -n "$monitor_iface" ]; then
        echo "$monitor_iface"
        return 0
    fi
    
    # Find available WiFi interface
    local wifi_iface=$(iwconfig 2>/dev/null | grep "IEEE 802.11" | awk '{print $1}' | head -1)
    
    if [ -z "$wifi_iface" ]; then
        log_error "No WiFi interface found"
        return 1
    fi
    
    log_info "Setting up monitor mode on $wifi_iface"
    
    # Kill interfering processes
    sudo airmon-ng check kill >/dev/null 2>&1
    
    # Start monitor mode
    sudo airmon-ng start "$wifi_iface" >/dev/null 2>&1
    
    # Get monitor interface name
    monitor_iface=$(iwconfig 2>/dev/null | grep "Mode:Monitor" | awk '{print $1}' | head -1)
    
    if [ -n "$monitor_iface" ]; then
        echo "$monitor_iface"
        return 0
    else
        return 1
    fi
}

# Main execution
main() {
    print_attack_banner
    
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Check required tools
    check_required_tools "airmon-ng" "airodump-ng" "python3"
    
    execute_attack "$@"
}

main "$@"