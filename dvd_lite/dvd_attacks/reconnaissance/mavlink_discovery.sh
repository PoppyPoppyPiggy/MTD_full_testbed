#!/bin/bash
# mavlink_discovery.sh - MAVLink Service Discovery Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/mavlink_discovery.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="MAVLink Service Discovery"
LOG_FILE="$(get_log_dir)/mavlink_discovery.log"

# DVD Target IPs
TARGETS=(
    "10.13.0.2:flight-controller"
    "10.13.0.3:companion-computer"
    "10.13.0.4:ground-control-station"
    "10.13.0.5:simulator"
)

# Common MAVLink ports
MAVLINK_PORTS=(14550 14551 14552 5760 5762 5763)

print_attack_banner() {
    echo -e "${CYAN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║      MAVLink Service Discovery       ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════╝${NC}"
}

execute_attack() {
    log_info "Starting MAVLink Service Discovery"
    
    local discovered_services=()
    local ioc_file="/tmp/mavlink_iocs.txt"
    > "$ioc_file"
    
    for target_info in "${TARGETS[@]}"; do
        local ip=$(echo "$target_info" | cut -d: -f1)
        local name=$(echo "$target_info" | cut -d: -f2)
        
        log_info "Scanning $name ($ip)..."
        
        scan_mavlink_ports "$ip" "$name" "$ioc_file"
    done
    
    # Summary
    local total_services=$(grep -c "MAVLINK_SERVICE" "$ioc_file" 2>/dev/null || echo "0")
    log_success "MAVLink discovery completed. Found $total_services services"
    
    if [ "$total_services" -gt 0 ]; then
        echo -e "${GREEN}[+] Discovered services:${NC}"
        grep "MAVLINK_SERVICE" "$ioc_file" | while read ioc; do
            echo -e "${CYAN}   $ioc${NC}"
        done
    fi
    
    return 0
}

scan_mavlink_ports() {
    local target_ip="$1"
    local target_name="$2" 
    local ioc_file="$3"
    
    for port in "${MAVLINK_PORTS[@]}"; do
        echo -ne "\r   Testing $target_ip:$port..."
        
        # UDP port test (MAVLink is primarily UDP)
        if timeout 3 nc -u -z "$target_ip" "$port" 2>/dev/null; then
            echo -e "\r${GREEN}[+] Port $port/UDP open on $target_ip${NC}"
            
            # Test MAVLink communication
            test_mavlink_communication "$target_ip" "$port" "$target_name" "$ioc_file"
        fi
        
        # Also test TCP for some MAVLink implementations
        if timeout 3 nc -z "$target_ip" "$port" 2>/dev/null; then
            echo -e "\r${GREEN}[+] Port $port/TCP open on $target_ip${NC}"
            echo "MAVLINK_TCP_PORT:$target_ip:$port" >> "$ioc_file"
        fi
    done
    echo -e "\r$(printf '%50s' ' ')\r"
}

test_mavlink_communication() {
    local ip="$1"
    local port="$2"
    local name="$3"
    local ioc_file="$4"
    
    # Generate MAVLink test script
    cat > "/tmp/mavlink_test_${ip}_${port}.py" << PYEOF
#!/usr/bin/env python3
import socket
import struct
import sys

def create_mavlink_heartbeat():
    """Create MAVLink 2.0 HEARTBEAT message"""
    # Payload: type, autopilot, base_mode, custom_mode(4), system_status, mavlink_version
    payload = struct.pack('<BBBBBBBB',
        6,    # MAV_TYPE_GCS
        0,    # MAV_AUTOPILOT_GENERIC
        0,    # base_mode
        0, 0, 0, 0,  # custom_mode (4 bytes)
        3     # MAV_STATE_STANDBY
    )
    
    # MAVLink 2.0 header: STX, len, incompat_flags, compat_flags, seq, sysid, compid, msgid(3)
    header = struct.pack('<BBBBBBBB',
        0xFD,  # STX
        len(payload),  # payload length
        0,     # incompat flags
        0,     # compat flags
        1,     # sequence
        255,   # system ID (GCS)
        0,     # component ID
        0      # message ID (HEARTBEAT) - first byte
    ) + struct.pack('<BB', 0, 0)  # message ID remaining bytes
    
    return header + payload

def test_mavlink_udp(host, port):
    """Test MAVLink UDP communication"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        
        heartbeat = create_mavlink_heartbeat()
        sock.sendto(heartbeat, (host, port))
        
        try:
            data, addr = sock.recvfrom(1024)
            response_len = len(data)
            
            # Basic MAVLink validation
            if response_len >= 10:
                if data[0] == 0xFD:  # MAVLink 2.0
                    print(f"MAVLINK_2_RESPONSE:{response_len}:{host}:{port}")
                elif data[0] == 0xFE:  # MAVLink 1.0
                    print(f"MAVLINK_1_RESPONSE:{response_len}:{host}:{port}")
                else:
                    print(f"UNKNOWN_RESPONSE:{response_len}:{host}:{port}")
            else:
                print(f"SHORT_RESPONSE:{response_len}:{host}:{port}")
                
        except socket.timeout:
            print(f"NO_RESPONSE:{host}:{port}")
        
        sock.close()
    except Exception as e:
        print(f"ERROR:{host}:{port}:{e}")

if __name__ == "__main__":
    test_mavlink_udp("$ip", $port)
PYEOF
    
    # Run MAVLink test
    local result=$(python3 "/tmp/mavlink_test_${ip}_${port}.py" 2>/dev/null)
    
    if [[ "$result" == *"RESPONSE"* ]]; then
        echo -e "${GREEN}[+] MAVLink service confirmed: $ip:$port ($name)${NC}"
        echo "MAVLINK_SERVICE:$ip:$port:$name" >> "$ioc_file"
        echo "$result" >> "$ioc_file"
        
        # Additional service fingerprinting
        identify_mavlink_service "$port" "$name" "$ioc_file"
    else
        echo -e "${YELLOW}[!] No MAVLink response from $ip:$port${NC}"
    fi
    
    # Cleanup
    rm -f "/tmp/mavlink_test_${ip}_${port}.py"
}

identify_mavlink_service() {
    local port="$1"
    local name="$2"
    local ioc_file="$3"
    
    case "$port" in
        14550)
            echo "MAVLINK_SERVICE_TYPE:PRIMARY_GCS:$port" >> "$ioc_file"
            ;;
        14551) 
            echo "MAVLINK_SERVICE_TYPE:SECONDARY_GCS:$port" >> "$ioc_file"
            ;;
        5760)
            echo "MAVLINK_SERVICE_TYPE:SITL_TCP:$port" >> "$ioc_file"
            ;;
        *)
            echo "MAVLINK_SERVICE_TYPE:UNKNOWN:$port" >> "$ioc_file"
            ;;
    esac
}

# Main execution
main() {
    print_attack_banner
    
    check_required_tools "nc" "python3"
    
    execute_attack "$@"
}

main "$@"